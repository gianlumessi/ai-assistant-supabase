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
import time
from typing import List

from openai import OpenAI
from backend.core.supabase_client import get_supabase
from backend.core.logging_config import get_logger
from backend.core.exceptions import EmbeddingError, IngestionError, DatabaseError
from backend.core.config import config

logger = get_logger(__name__)

# Use the same API key pattern as _generate_answer()
_client = None
_EMBED_MODEL = "text-embedding-3-small"


def _get_openai_client() -> OpenAI:
    """Get or create OpenAI client with proper configuration."""
    global _client
    if _client is None:
        api_key = config.get_openai_api_key()
        _client = OpenAI(api_key=api_key)
    return _client


def embed_text(text: str, max_retries: int = 3) -> List[float]:
    """
    Generate embeddings for text using OpenAI with retry logic.

    Args:
        text: Text to embed
        max_retries: Maximum number of retry attempts for transient failures

    Returns:
        List of embedding floats

    Raises:
        EmbeddingError: If embedding generation fails after all retries
    """
    if not text or not text.strip():
        raise EmbeddingError("Cannot embed empty text")

    client = _get_openai_client()

    for attempt in range(max_retries):
        try:
            start_time = time.time()
            resp = client.embeddings.create(model=_EMBED_MODEL, input=text)
            duration = time.time() - start_time

            if not resp.data or len(resp.data) == 0:
                raise EmbeddingError("OpenAI returned empty embedding response")

            embedding = resp.data[0].embedding
            logger.info(f'Generated embedding in {duration:.2f}s (length={len(embedding)})')
            return embedding

        except Exception as e:
            is_last_attempt = attempt == max_retries - 1
            logger.warning(
                f'Embedding attempt {attempt + 1}/{max_retries} failed: {str(e)}',
                exc_info=is_last_attempt
            )

            if is_last_attempt:
                raise EmbeddingError(
                    f'Failed to generate embedding after {max_retries} attempts',
                    details={'error': str(e), 'text_length': len(text)}
                )

            # Exponential backoff: 2^attempt seconds
            backoff_time = 2 ** attempt
            logger.info(f'Retrying in {backoff_time}s...')
            time.sleep(backoff_time)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """
    Split text into overlapping chunks for processing.

    Args:
        text: Text to chunk
        chunk_size: Number of words per chunk
        overlap: Number of words to overlap between chunks

    Returns:
        List of text chunks

    Raises:
        IngestionError: If parameters are invalid or text is empty
    """
    if not text or not text.strip():
        logger.warning('Attempted to chunk empty text')
        return []

    if overlap >= chunk_size:
        raise IngestionError(
            f'Overlap ({overlap}) must be smaller than chunk_size ({chunk_size})'
        )

    if chunk_size <= 0:
        raise IngestionError(f'chunk_size must be positive, got {chunk_size}')

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap

    logger.info(f'Chunked text into {len(chunks)} chunks (words={len(words)}, chunk_size={chunk_size}, overlap={overlap})')
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

    Args:
        website_id: Website ID for document scoping
        text: Text content to ingest
        document_id: Optional document ID (generates UUID if not provided)
        file_name: Name of the source file
        storage_path: Path in storage bucket
        mime_type: MIME type of the document

    Returns:
        The document_id used

    Raises:
        IngestionError: If ingestion fails
        DatabaseError: If database operations fail
    """
    if not website_id:
        raise IngestionError('website_id is required')

    if not text or not text.strip():
        raise IngestionError('Cannot ingest empty text')

    doc_id = document_id or str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        f'Starting ingestion: document_id={doc_id}, website_id={website_id}, '
        f'file_name={file_name}, text_length={len(text)}'
    )

    try:
        supabase = get_supabase()

        # 1) Create documents row (required for FK)
        try:
            supabase.table("documents").insert({
                "id": doc_id,
                "website_id": website_id,
                "file_name": file_name,
                "storage_path": storage_path,
                "mime_type": mime_type,
                "status": "ready",
            }).execute()
            logger.info(f'Document record created: {doc_id}')
        except Exception as e:
            logger.error(f'Failed to create document record: {str(e)}')
            raise DatabaseError(
                'Failed to create document record',
                details={'document_id': doc_id, 'error': str(e)}
            )

        # 2) Chunk the text
        try:
            chunks = chunk_text(text)
            if not chunks:
                logger.warning(f'No chunks generated for document {doc_id}')
                return doc_id
        except Exception as e:
            logger.error(f'Failed to chunk text: {str(e)}')
            # Clean up document record on failure
            try:
                supabase.table("documents").delete().eq("id", doc_id).execute()
            except Exception:
                pass
            raise IngestionError(
                'Failed to chunk text',
                details={'document_id': doc_id, 'error': str(e)}
            )

        # 3) Generate embeddings and prepare rows
        rows = []
        failed_chunks = []

        for i, chunk in enumerate(chunks):
            try:
                embedding = embed_text(chunk)
                rows.append({
                    "website_id": website_id,
                    "document_id": doc_id,
                    "chunk_index": i,
                    "content": chunk,
                    "embedding": embedding,
                })
            except EmbeddingError as e:
                logger.error(f'Failed to embed chunk {i}/{len(chunks)}: {str(e)}')
                failed_chunks.append(i)
                # Continue processing other chunks

        if failed_chunks:
            logger.warning(
                f'Failed to embed {len(failed_chunks)}/{len(chunks)} chunks for document {doc_id}'
            )

        # 4) Insert chunks into database
        if rows:
            try:
                supabase.table("document_chunks").insert(rows).execute()
                logger.info(f'Inserted {len(rows)} chunks for document {doc_id}')
            except Exception as e:
                logger.error(f'Failed to insert chunks: {str(e)}')
                # Clean up document record on failure
                try:
                    supabase.table("documents").delete().eq("id", doc_id).execute()
                except Exception:
                    pass
                raise DatabaseError(
                    'Failed to insert document chunks',
                    details={'document_id': doc_id, 'chunks_count': len(rows), 'error': str(e)}
                )
        else:
            logger.error(f'No valid chunks to insert for document {doc_id}')
            # Clean up document record
            try:
                supabase.table("documents").delete().eq("id", doc_id).execute()
            except Exception:
                pass
            raise IngestionError(
                'All chunks failed to generate embeddings',
                details={'document_id': doc_id, 'total_chunks': len(chunks)}
            )

        duration = time.time() - start_time
        logger.info(
            f'Ingestion completed: document_id={doc_id}, chunks={len(rows)}, '
            f'failed_chunks={len(failed_chunks)}, duration={duration:.2f}s'
        )

        return doc_id

    except (IngestionError, DatabaseError):
        raise
    except Exception as e:
        logger.exception(f'Unexpected error during ingestion: {str(e)}')
        raise IngestionError(
            'Unexpected error during document ingestion',
            details={'document_id': doc_id, 'error': str(e)}
        )

