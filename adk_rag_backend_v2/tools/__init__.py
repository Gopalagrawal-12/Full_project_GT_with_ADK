"""
tools package
--------------
Pure infrastructure tools (no agent/LLM logic). Each tool lives in its own
module and is imported directly by the agent/graph-node that needs it.

  schema_tool.py           fetch_schema_overview()          -- cheap, broad grounding
                            fetch_schema_relevant_detail()    -- expensive, entity-filtered grounding
  sql_execution_tool.py     execute_sql()                       -- SQL branch
  chunker.py                 create_chunker()                    -- vector ingestion
  embedder.py                  create_embedder()                   -- vector ingestion + query embedding
  vector_search_tool.py         vector_search()                     -- vector/RAG branch
"""

from tools.chunker import ChunkingConfig, DocumentChunk, create_chunker
from tools.embedder import create_embedder
from tools.schema_tool import fetch_schema_overview, fetch_schema_relevant_detail
from tools.sql_execution_tool import execute_sql
from tools.vector_search_tool import vector_search

__all__ = [
    "fetch_schema_overview",
    "fetch_schema_relevant_detail",
    "execute_sql",
    "vector_search",
    "create_chunker",
    "create_embedder",
    "ChunkingConfig",
    "DocumentChunk",
]
