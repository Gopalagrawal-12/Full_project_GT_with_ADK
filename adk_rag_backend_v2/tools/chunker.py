"""
tools/chunker.py
-------------------
Splits documents into retrieval-sized chunks for the vector pipeline.

Two strategies, selected via ChunkingConfig.use_semantic_splitting:

  DoclingHybridChunker  Token-aware, structure-preserving (headings, tables,
                        code blocks), contextualized chunks. Best quality,
                        but pulls in `docling` + `transformers` (heavy deps).
                        Imported lazily so this module — and the rest of the
                        app — still loads fine if those aren't installed;
                        you only pay the cost (and get a clear error) if you
                        actually try to use semantic chunking.

  SimpleChunker          Paragraph-aware sliding window, zero extra deps.
                        Used automatically as a fallback if Docling isn't
                        available, or explicitly via use_semantic_splitting=False.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("adk_rag.tools.chunker")


@dataclass
class ChunkingConfig:
    """Configuration for chunking. Domain-agnostic — works for any document type."""

    chunk_size: int = 1000            # Target characters per chunk (SimpleChunker)
    chunk_overlap: int = 200          # Character overlap between chunks (SimpleChunker)
    max_chunk_size: int = 2000
    min_chunk_size: int = 100
    use_semantic_splitting: bool = True   # Prefer DoclingHybridChunker when available
    preserve_structure: bool = True
    max_tokens: int = 512             # Token budget per chunk (DoclingHybridChunker)

    def __post_init__(self) -> None:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if self.min_chunk_size <= 0:
            raise ValueError("min_chunk_size must be positive")


@dataclass
class DocumentChunk:
    """A single chunk, ready to be embedded and stored."""

    content: str
    index: int
    start_char: int
    end_char: int
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: Optional[int] = None
    embedding: Optional[list[float]] = None  # populated later by tools/embedder.py

    def __post_init__(self) -> None:
        if self.token_count is None:
            self.token_count = max(1, len(self.content) // 4)  # rough char->token estimate


class DoclingHybridChunker:
    """
    Wraps Docling's HybridChunker: token-aware, respects document structure,
    and contextualizes each chunk with its heading hierarchy — meaningfully
    better retrieval quality than naive splitting, at the cost of the
    docling/transformers dependency.
    """

    def __init__(self, config: ChunkingConfig, tokenizer_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.config = config
        try:
            from transformers import AutoTokenizer
            from docling.chunking import HybridChunker
        except ImportError as exc:
            raise RuntimeError(
                "DoclingHybridChunker requires the optional `docling` and "
                "`transformers` packages. Install them (`pip install docling "
                "transformers`) or set use_semantic_splitting=False to use the "
                "dependency-free SimpleChunker instead."
            ) from exc

        logger.info("Initializing tokenizer: %s", tokenizer_model_id)
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_model_id)
        self.chunker = HybridChunker(
            tokenizer=self.tokenizer,
            max_tokens=config.max_tokens,
            merge_peers=True,
        )
        logger.info("HybridChunker initialized (max_tokens=%d)", config.max_tokens)

    async def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[dict[str, Any]] = None,
        docling_doc: Optional[Any] = None,
    ) -> list[DocumentChunk]:
        if not content.strip():
            return []

        base_metadata = {"title": title, "source": source, "chunk_method": "hybrid", **(metadata or {})}

        if docling_doc is None:
            logger.warning("No DoclingDocument provided, using simple chunking fallback")
            return _simple_fallback_chunk(content, base_metadata, self.config, self.tokenizer)

        try:
            chunks = list(self.chunker.chunk(dl_doc=docling_doc))
            document_chunks: list[DocumentChunk] = []
            current_pos = 0

            for i, chunk in enumerate(chunks):
                text = self.chunker.contextualize(chunk=chunk)
                token_count = len(self.tokenizer.encode(text))
                start_char = current_pos
                end_char = start_char + len(text)

                document_chunks.append(
                    DocumentChunk(
                        content=text.strip(),
                        index=i,
                        start_char=start_char,
                        end_char=end_char,
                        metadata={**base_metadata, "total_chunks": len(chunks), "has_context": True},
                        token_count=token_count,
                    )
                )
                current_pos = end_char

            logger.info("Created %d chunks using HybridChunker", len(document_chunks))
            return document_chunks

        except Exception:
            logger.exception("HybridChunker failed, falling back to simple chunking")
            return _simple_fallback_chunk(content, base_metadata, self.config, self.tokenizer)


class SimpleChunker:
    """Paragraph-aware sliding-window chunker. No external dependencies."""

    def __init__(self, config: ChunkingConfig):
        self.config = config

    async def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[dict[str, Any]] = None,
        **_ignored: Any,  # accepts and ignores e.g. docling_doc for interface parity
    ) -> list[DocumentChunk]:
        if not content.strip():
            return []

        base_metadata = {"title": title, "source": source, "chunk_method": "simple", **(metadata or {})}
        paragraphs = re.split(r"\n\s*\n", content)

        chunks: list[DocumentChunk] = []
        current_chunk = ""
        current_pos = 0
        chunk_index = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            candidate = f"{current_chunk}\n\n{paragraph}" if current_chunk else paragraph
            if len(candidate) <= self.config.chunk_size:
                current_chunk = candidate
                continue

            if current_chunk:
                chunks.append(_make_chunk(current_chunk, chunk_index, current_pos, base_metadata.copy()))
                current_pos += len(current_chunk)
                chunk_index += 1
            current_chunk = paragraph

        if current_chunk:
            chunks.append(_make_chunk(current_chunk, chunk_index, current_pos, base_metadata.copy()))

        for c in chunks:
            c.metadata["total_chunks"] = len(chunks)
        return chunks


def _make_chunk(content: str, index: int, start_pos: int, metadata: dict[str, Any]) -> DocumentChunk:
    return DocumentChunk(
        content=content.strip(), index=index, start_char=start_pos, end_char=start_pos + len(content), metadata=metadata
    )


def _simple_fallback_chunk(
    content: str, base_metadata: dict[str, Any], config: ChunkingConfig, tokenizer: Any
) -> list[DocumentChunk]:
    """Sliding-window fallback used by DoclingHybridChunker when it can't run."""
    chunks: list[DocumentChunk] = []
    chunk_size, overlap = config.chunk_size, config.chunk_overlap
    start, chunk_index = 0, 0

    while start < len(content):
        end = start + chunk_size
        if end >= len(content):
            chunk_text, end = content[start:], len(content)
        else:
            chunk_end = end
            for i in range(end, max(start + config.min_chunk_size, end - 200), -1):
                if i < len(content) and content[i] in ".!?\n":
                    chunk_end = i + 1
                    break
            chunk_text, end = content[start:chunk_end], chunk_end

        if chunk_text.strip():
            token_count = len(tokenizer.encode(chunk_text)) if tokenizer else max(1, len(chunk_text) // 4)
            chunks.append(
                DocumentChunk(
                    content=chunk_text.strip(),
                    index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata={**base_metadata, "chunk_method": "simple_fallback"},
                    token_count=token_count,
                )
            )
            chunk_index += 1
        start = end - overlap

    for c in chunks:
        c.metadata["total_chunks"] = len(chunks)
    return chunks


def create_chunker(config: ChunkingConfig):
    """Factory: DoclingHybridChunker if requested (falls back gracefully), else SimpleChunker."""
    if config.use_semantic_splitting:
        try:
            return DoclingHybridChunker(config)
        except RuntimeError as exc:
            logger.warning("%s Falling back to SimpleChunker.", exc)
            return SimpleChunker(config)
    return SimpleChunker(config)
