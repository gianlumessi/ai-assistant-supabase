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
from typing import List, Tuple, Dict, Any

from openai import OpenAI
from backend.core.supabase_client import get_supabase

import ast
import json

# ----------------------------
# OpenAI embeddings (same style as _generate_answer)
# ----------------------------

_EMBED_MODEL = "text-embedding-3-small"

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def embed_query(text: str) -> List[float]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")

    resp = _client.embeddings.create(
        model=_EMBED_MODEL,
        input=text,
    )
    return resp.data[0].embedding


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
    supabase = get_supabase()
    res = (
        supabase.table("document_chunks")
        .select("id,document_id,chunk_index,content,embedding")
        .eq("website_id", website_id)
        .limit(limit)
        .execute()
    )
    return res.data or []


def _coerce_embedding(emb):
    if emb is None:
        return None
    if isinstance(emb, list):
        return emb
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
    return None


def gather_context(
    website_id: str,
    question: str,
    top_n: int = 8,
) -> Tuple[str, List[str]]:
    """
    Returns:
      - context string to pass into _generate_answer()
      - list of document_ids used
    """

    query_emb = embed_query(question)
    chunks = _fetch_chunks(website_id)

    scored = []
    for c in chunks:
        content = c.get("content") or ""
        emb = _coerce_embedding(c.get("embedding"))

        if not content.strip() or not emb:
            continue

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

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]

    context = "\n\n".join(
        f"[document {c['document_id']} – chunk {c['chunk_index']}]\n{c['content']}"
        for c in top
    )

    used_docs = list({c["document_id"] for c in top})

    return context, used_docs
