"""
Retrieval logic for the chatbot.

Selects the most relevant document chunks for a user question using
semantic similarity (OpenAI embeddings) plus light lexical boosting.
Designed to work with the existing schema:

document_chunks(
  id,
  document_id,
  website_id,
  chunk_index,
  content,
  embedding
)

No reranking, no DB migrations required.
"""

from __future__ import annotations

import os
import math
import re
import time
from typing import List, Tuple, Dict, Any

from openai import OpenAI
from backend.core.supabase_client import get_supabase
from backend.core.logging_config import get_logger
from backend.core.exceptions import EmbeddingError, RetrievalError, DatabaseError
from backend.core.config import config

import ast
import json

logger = get_logger(__name__)

# ----------------------------
# OpenAI embeddings (same style as _generate_answer)
# ----------------------------

_EMBED_MODEL = "text-embedding-3-small"
_client = None


def _get_openai_client() -> OpenAI:
    """Get or create OpenAI client with proper configuration."""
    global _client
    if _client is None:
        api_key = config.get_openai_api_key()
        _client = OpenAI(api_key=api_key)
    return _client


def embed_query(text: str, max_retries: int = 3) -> List[float]:
    """
    Generate embeddings for a query using OpenAI with retry logic.

    Args:
        text: Query text to embed
        max_retries: Maximum number of retry attempts for transient failures

    Returns:
        List of embedding floats

    Raises:
        EmbeddingError: If embedding generation fails after all retries
    """
    if not text or not text.strip():
        raise EmbeddingError("Cannot embed empty query")

    client = _get_openai_client()

    for attempt in range(max_retries):
        try:
            start_time = time.time()
            resp = client.embeddings.create(
                model=_EMBED_MODEL,
                input=text,
            )
            duration = time.time() - start_time

            if not resp.data or len(resp.data) == 0:
                raise EmbeddingError("OpenAI returned empty embedding response")

            embedding = resp.data[0].embedding
            logger.debug(f'Query embedding generated in {duration:.2f}s (length={len(embedding)})')
            return embedding

        except Exception as e:
            is_last_attempt = attempt == max_retries - 1
            logger.warning(
                f'Query embedding attempt {attempt + 1}/{max_retries} failed: {str(e)}',
                exc_info=is_last_attempt
            )

            if is_last_attempt:
                raise EmbeddingError(
                    f'Failed to generate query embedding after {max_retries} attempts',
                    details={'error': str(e), 'query_length': len(text)}
                )

            # Exponential backoff: 2^attempt seconds
            backoff_time = 2 ** attempt
            logger.debug(f'Retrying in {backoff_time}s...')
            time.sleep(backoff_time)


# ----------------------------
# Scoring helpers
# ----------------------------

_WORD_RE = re.compile(r"[a-z]{3,}")
_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that",
    "your", "you", "are", "was", "were", "have", "has",
}


def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def lexical_score(question: str, text: str) -> float:
    q_tokens = [
        t for t in _WORD_RE.findall(question.lower())
        if t not in _STOPWORDS
    ]
    if not q_tokens:
        return 0.0

    text_tokens = set(_WORD_RE.findall(text.lower()))
    hits = sum(1 for t in set(q_tokens) if t in text_tokens)
    return hits / len(set(q_tokens))


# ----------------------------
# Retrieval
# ----------------------------

def _fetch_chunks(website_id: str, limit: int = 1200) -> List[Dict[str, Any]]:
    """
    Fetch document chunks for a website from the database.

    Args:
        website_id: Website ID to filter chunks
        limit: Maximum number of chunks to fetch

    Returns:
        List of chunk dictionaries

    Raises:
        DatabaseError: If database query fails
    """
    if not website_id:
        raise RetrievalError('website_id is required')

    try:
        start_time = time.time()
        supabase = get_supabase()
        res = (
            supabase.table("document_chunks")
            .select("id,document_id,chunk_index,content,embedding")
            .eq("website_id", website_id)
            .limit(limit)
            .execute()
        )
        duration = time.time() - start_time

        chunks = res.data or []
        logger.info(
            f'Fetched {len(chunks)} chunks for website {website_id} in {duration:.2f}s'
        )
        return chunks

    except Exception as e:
        logger.error(f'Failed to fetch chunks for website {website_id}: {str(e)}')
        raise DatabaseError(
            'Failed to fetch document chunks',
            details={'website_id': website_id, 'error': str(e)}
        )


def _coerce_embedding(emb) -> List[float] | None:
    """
    Convert embedding from database to list of floats.

    Args:
        emb: Embedding in various formats (list, string, etc.)

    Returns:
        List of floats or None if conversion fails
    """
    if emb is None:
        return None

    if isinstance(emb, list):
        try:
            return [float(x) for x in emb]
        except (ValueError, TypeError):
            logger.warning('Failed to convert embedding list elements to float')
            return None

    if isinstance(emb, str):
        # Often returned like: "[0.1, 0.2, ...]"
        try:
            v = ast.literal_eval(emb)
            if isinstance(v, list):
                return [float(x) for x in v]
        except Exception:
            pass

        # Fallback if it's JSON
        try:
            v = json.loads(emb)
            if isinstance(v, list):
                return [float(x) for x in v]
        except Exception:
            pass

        logger.debug(f'Failed to parse embedding string (length={len(emb)})')

    return None


def gather_context(
    website_id: str,
    question: str,
    top_n: int = 8,
) -> Tuple[str, List[str]]:
    """
    Gather relevant context for a question using semantic and lexical search.

    Args:
        website_id: Website ID to search within
        question: User's question
        top_n: Number of top chunks to return

    Returns:
        Tuple of (context string, list of document IDs used)

    Raises:
        RetrievalError: If retrieval fails
    """
    if not website_id:
        raise RetrievalError('website_id is required')

    if not question or not question.strip():
        raise RetrievalError('question cannot be empty')

    start_time = time.time()
    logger.info(
        f'Gathering context for website {website_id}, '
        f'question_length={len(question)}, top_n={top_n}'
    )

    try:
        # Generate query embedding
        query_emb = embed_query(question)

        # Fetch chunks from database
        chunks = _fetch_chunks(website_id)

        if not chunks:
            logger.warning(f'No chunks found for website {website_id}')
            return "", []

        # Score and rank chunks
        scored = []
        invalid_chunks = 0

        for c in chunks:
            content = c.get("content") or ""
            emb = _coerce_embedding(c.get("embedding"))

            if not content.strip() or not emb:
                invalid_chunks += 1
                continue

            try:
                sem = cosine_similarity(query_emb, emb)
                lex = lexical_score(question, content)

                # Semantic dominates; lexical boosts exact matches
                score = 0.85 * sem + 0.15 * lex

                scored.append({
                    "document_id": c["document_id"],
                    "chunk_index": c["chunk_index"],
                    "content": content,
                    "score": score,
                })
            except Exception as e:
                logger.warning(f'Failed to score chunk {c.get("id")}: {str(e)}')
                invalid_chunks += 1
                continue

        if invalid_chunks > 0:
            logger.warning(
                f'Skipped {invalid_chunks}/{len(chunks)} invalid chunks for website {website_id}'
            )

        if not scored:
            logger.warning(f'No valid chunks to score for website {website_id}')
            return "", []

        # Sort by score and select top chunks
        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:top_n]

        # Build context string
        context = "\n\n".join(
            f"[document {c['document_id']} – chunk {c['chunk_index']}]\n{c['content']}"
            for c in top
        )

        # Extract unique document IDs
        used_docs = list({c["document_id"] for c in top})

        duration = time.time() - start_time
        logger.info(
            f'Context gathered: top_chunks={len(top)}, unique_docs={len(used_docs)}, '
            f'context_length={len(context)}, duration={duration:.2f}s, '
            f'top_score={top[0]["score"]:.4f if top else 0}'
        )

        return context, used_docs

    except (EmbeddingError, DatabaseError, RetrievalError):
        raise
    except Exception as e:
        logger.exception(f'Unexpected error during context gathering: {str(e)}')
        raise RetrievalError(
            'Unexpected error during context retrieval',
            details={'website_id': website_id, 'error': str(e)}
        )
