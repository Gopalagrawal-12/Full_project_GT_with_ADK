"""
services/vector_ingestion_service.py
-----------------------------------------
Turns raw document bytes into searchable chunks in `documents`/`chunks`
(pgvector). This is the API-driven counterpart to a CLI ingestion script:
same chunk -> embed -> store pipeline, but taking bytes from an upload
instead of walking a local folder, and reporting progress into an
IngestionStatusResponse instead of printing to stdout.

Supported formats:
  - Plain text: .md, .markdown, .txt (read directly)
  - Anything else (.pdf, .docx, .pptx, .xlsx, .html, ...): attempted via
    Docling if installed; falls back to a clear error asking for a
    supported/plain-text format otherwise. See tools/chunker.py for the
    same lazy-import pattern.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from tools.chunker import ChunkingConfig, DocumentChunk, create_chunker
from tools.embedder import create_embedder
from utils.db_pool import get_pool

logger = logging.getLogger("adk_rag.services.vector_ingestion_service")

_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
_DOCLING_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".html", ".htm"}


def _extract_title(content: str, file_name: str) -> str:
    for line in content.split("\n")[:10]:
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return os.path.splitext(file_name)[0]


def _read_bytes_to_markdown(file_name: str, file_bytes: bytes) -> tuple[str, Optional[Any]]:
    """
    Converts uploaded bytes to markdown text (+ an optional DoclingDocument
    for HybridChunker). Text formats are decoded directly; everything else
    goes through Docling if it's installed.
    """
    ext = os.path.splitext(file_name)[1].lower()

    if ext in _TEXT_EXTENSIONS or ext == "":
        try:
            return file_bytes.decode("utf-8"), None
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1"), None

    if ext in _DOCLING_EXTENSIONS:
        try:
            import tempfile

            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                f"'{ext}' files require the optional `docling` package "
                "(`pip install docling`). Upload a .md/.txt file instead, or "
                "install docling to enable rich document parsing."
            ) from exc

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            return result.document.export_to_markdown(), result.document
        finally:
            os.unlink(tmp_path)

    raise RuntimeError(f"Unsupported file type '{ext}'. Supported: {sorted(_TEXT_EXTENSIONS | _DOCLING_EXTENSIONS)}")


class VectorIngestionPipeline:
    """Chunk -> embed -> store pipeline for one document at a time."""

    def __init__(self, chunking_config: Optional[ChunkingConfig] = None):
        self.chunker_config = chunking_config or ChunkingConfig()
        self.chunker = create_chunker(self.chunker_config)
        self.embedder = create_embedder()

    async def ingest_bytes(
        self,
        file_name: str,
        file_bytes: bytes,
        dataset_label: Optional[str] = None,
        progress_cb: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Runs the full pipeline for one uploaded file and returns a summary
        dict (document_id, chunks_created, errors).
        """

        def _progress(step: str, pct: float) -> None:
            if progress_cb:
                progress_cb(step, pct)

        _progress("parsing_file", 10.0)
        content, docling_doc = _read_bytes_to_markdown(file_name, file_bytes)
        title = _extract_title(content, file_name)

        _progress("chunking", 30.0)
        chunks: list[DocumentChunk] = await self.chunker.chunk_document(
            content=content,
            title=title,
            source=file_name,
            metadata={"file_size": len(file_bytes), "ingested_at": datetime.now(timezone.utc).isoformat()},
            docling_doc=docling_doc,
        )
        if not chunks:
            raise ValueError(f"No chunks produced for '{file_name}' (empty or unparseable content).")

        _progress("embedding", 55.0)
        embedded_chunks = await self.embedder.embed_chunks(chunks)

        _progress("storing", 80.0)
        document_id = await self._save_to_postgres(title, file_name, content, embedded_chunks, dataset_label)

        _progress("done", 100.0)
        return {"document_id": document_id, "title": title, "chunks_created": len(embedded_chunks)}

    async def _save_to_postgres(
        self,
        title: str,
        source: str,
        content: str,
        chunks: list[DocumentChunk],
        dataset_label: Optional[str],
    ) -> str:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                document_id = await conn.fetchval(
                    """
                    INSERT INTO documents (title, source, content, dataset_label, metadata)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    RETURNING id::text
                    """,
                    title, source, content, dataset_label, json.dumps({"chunk_count": len(chunks)}),
                )

                for chunk in chunks:
                    embedding_literal = (
                        "[" + ",".join(map(str, chunk.embedding)) + "]" if chunk.embedding else None
                    )
                    await conn.execute(
                        """
                        INSERT INTO chunks (document_id, content, embedding, chunk_index, token_count, metadata)
                        VALUES ($1::uuid, $2, $3::vector, $4, $5, $6::jsonb)
                        """,
                        document_id, chunk.content, embedding_literal, chunk.index,
                        chunk.token_count, json.dumps(chunk.metadata, default=str),
                    )
        return document_id
