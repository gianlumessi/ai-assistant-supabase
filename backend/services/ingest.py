"""
Document ingestion pipeline.

This module runs at upload/admin time:
- extracts text (already provided by caller in this minimal version)
- chunks text
- creates embeddings via OpenAI
- writes rows to document_chunks

Chat queries NEVER download files and NEVER re-embed content.
"""

from __future__ import annotations

import os
import uuid
from typing import List

from openai import OpenAI
from backend.core.supabase_client import get_supabase

# Use the same API key pattern as _generate_answer()
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_EMBED_MODEL = "text-embedding-3-small"


def embed_text(text: str) -> List[float]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")
    resp = _client.embeddings.create(model=_EMBED_MODEL, input=text)
    return resp.data[0].embedding


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    words = text.split()
    chunks = []
    start = 0

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap

    return chunks


def ingest_text_into_chunks(
    website_id: str,
    text: str,
    document_id: str | None = None,
    file_name: str = "faq_test.txt",
    storage_path: str = "",
    mime_type: str = "text/plain",
) -> str:
    """
    Ingest a plain text string into documents + document_chunks.
    Returns the document_id used.
    """
    supabase = get_supabase()

    doc_id = document_id or str(uuid.uuid4())

    # 1) Create documents row (required for FK)
    supabase.table("documents").insert({
        "id": doc_id,
        "website_id": website_id,
        "file_name": file_name,
        "storage_path": storage_path,
        "mime_type": mime_type,
        "status": "ready",
    }).execute()

    # 2) Insert chunks
    chunks = chunk_text(text)
    rows = []
    for i, chunk in enumerate(chunks):
        rows.append({
            "website_id": website_id,
            "document_id": doc_id,
            "chunk_index": i,
            "content": chunk,
            "embedding": embed_text(chunk),
        })

    if rows:
        supabase.table("document_chunks").insert(rows).execute()

    return doc_id

