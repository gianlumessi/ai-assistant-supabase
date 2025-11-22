# backend/routers/chat.py
from __future__ import annotations

import io
import os
import re
from typing import Optional, List, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

# -------- Config --------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BUCKET = os.getenv("STORAGE_BUCKET_DOCS", "documents")
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "10"))
MAX_FILES_PER_QUERY = int(os.getenv("MAX_FILES_PER_QUERY", "5"))

# Service-role client (backend-only; never expose to browsers)
svc = create_client(SUPABASE_URL, SERVICE_ROLE)

router = APIRouter(prefix="/chat", tags=["chat"])

# -------- Models --------
class ChatQueryIn(BaseModel):
    website_id: str = Field(..., description="Tenant/website UUID")
    question: str = Field(..., min_length=3, max_length=4000)

class ChatAnswerOut(BaseModel):
    answer: str
    used_files: list[str] = []
    tokens_context: int | None = None

# -------- Utils --------
'''
_uuvid_re = re.compile(r"^[0-9a-fA-F-]{36}$")

def _validate_website_id(website_id: str) -> None:
    if not _uuid_re.match(website_id):
        raise HTTPException(status_code=400, detail="Invalid website_id format")
'''

################## To be removed after testing #####################
#TODO: remove the below after successful testing and use the block above
# allow letters, numbers, underscore, dash; length 3–64
_site_id_re = re.compile(r"^[A-Za-z0-9_-]{3,64}$") #for testing
def _validate_website_id(website_id: str) -> None:
    if not _site_id_re.match(website_id):
        raise HTTPException(status_code=400, detail="Invalid website_id format")
################## To be removed after testing #####################


def _list_site_files(website_id: str) -> List[dict]:
    """
    List objects under documents/{website_id}/
    Returns a list of objects with .name and .metadata if available.
    """
    # Supabase Storage lists by prefix via .list(path=..., options=...)
    # We default to top-level under the website folder.
    objects = svc.storage.from_(BUCKET).list(path=website_id, options={"limit": 1000})
    # objects is a list of dicts like {"name": "folder_or_file", "id": "...", "metadata": {...}}
    # We must qualify to full path "website_id/name"
    for o in objects:
        o["full_path"] = f"{website_id}/{o['name']}"
    return objects

def _download_object(path: str) -> bytes:
    data = svc.storage.from_(BUCKET).download(path)
    if isinstance(data, bytes):
        return data
    # supabase-py may return dict with data
    return data.get("data", b"")

def _is_pdf(name: str) -> bool:
    return name.lower().endswith(".pdf")

def _is_text(name: str) -> bool:
    return name.lower().endswith(".txt")

def _extract_text(name: str, blob: bytes) -> str:
    """
    Minimal text extraction:
      - .txt: decode utf-8 (fallback latin-1)
      - .pdf: try PyPDF2 if installed; otherwise return empty string
    """
    if _is_text(name):
        try:
            return blob.decode("utf-8")
        except UnicodeDecodeError:
            return blob.decode("latin-1", errors="ignore")

    if _is_pdf(name):
        try:
            # Lazy import to avoid hard dependency if you don't need PDFs
            import PyPDF2  # pip install pypdf2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(blob))
            out = []
            for page in pdf_reader.pages:
                try:
                    out.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(out)
        except Exception:
            # PDF library missing or failed; skip gracefully
            return ""

    # Unsupported types are skipped (you can add DOCX, HTML, etc. later)
    return ""


def _overlaps(question: str, text: str) -> bool:
    """Relevance filter: pick only the parts that look related to the question, don't select the whole file.
    Quick check: does the question share any words with this text?"""
    words = re.findall(r"[A-Za-z]{3,}", question.lower())
    common = {"the", "and", "for", "with", "from", "this", "that", "your", "you"}
    words = [w for w in words if w not in common]
    text_l = text.lower()
    return any(w in text_l for w in words[:8])  # check first few keywords


def _gather_context(website_id: str, question: str) -> Tuple[str, list[str]]:
    """
    Pull up to MAX_FILES_PER_QUERY files under the website folder,
    each capped by MAX_FILE_MB, and return concatenated text + file list.
    """
    objs = _list_site_files(website_id)
    selected = []
    text_parts = []
    for o in objs:
        if len(selected) >= MAX_FILES_PER_QUERY:
            break
        # Skip folders
        if o.get("metadata", {}).get("mimetype") is None and "." not in o["name"]:
            continue

        full_path = o["full_path"]
        try:
            blob = _download_object(full_path)
        except Exception:
            continue
        if len(blob) > MAX_FILE_MB * 1024 * 1024:
            continue

        text = _extract_text(o["name"], blob)

        if text.strip() and _overlaps(question, text):
            text_parts.append(f"\n\n--- FILE: {o['name']} ---\n{text}")
            selected.append(full_path)

    return ("\n".join(text_parts).strip(), selected)



''' This was a placeholder function
def _generate_answer(question: str, context: str) -> str:
    """
    Placeholder answer generator.
    Replace this with your LLM call (OpenAI, Claude, etc.),
    e.g., send `question` and `context` as system/user messages.
    """
    if not context:
        return "I couldn't find relevant content for this website yet. Please add documents."
    # Naive heuristic for now
    return (
        "Based on the website's documents, here's a concise answer:\n\n"
        f"Q: {question}\n"
        "A: (Draft) The documents mention:\n"
        f"{context[:1200]}{'...' if len(context) > 1200 else ''}\n\n"
        "— Replace this with your LLM call for a real answer."
    )
'''

def _generate_answer(question: str, context: str) -> str:
    """
    Real answer generator using OpenAI Chat Completions.
    Truncates context to avoid over-long prompts.
    """
    import os
    import textwrap
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Fallback to placeholder if key not set
        return (
            "I couldn't access an LLM right now. "
            "Set OPENAI_API_KEY or keep using the draft answer."
        )

    # keep context ~6k chars max to control cost/latency
    max_ctx = 6000
    ctx = context[:max_ctx]

    client = OpenAI(api_key=api_key)
    prompt = textwrap.dedent(f"""
    You are a helpful assistant. Answer using ONLY the context below.
    If the answer isn't in the context, say you don't have enough information.

    Question:
    {question}

    Context:
    {ctx}
    """)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return resp.choices[0].message.content.strip()


# -------- Routes --------
@router.post("/query", response_model=ChatAnswerOut)
def chat_query(payload: ChatQueryIn) -> ChatAnswerOut:
    """
    Main chatbot endpoint (MVP).
    - Uses SERVICE ROLE to read files under documents/{website_id}
    - Extracts text (txt/pdf) and builds a context string
    - Generates an answer (placeholder for now)
    - (Optional) logs chat to DB (commented below)
    """
    _validate_website_id(payload.website_id)

    context, used = _gather_context(payload.website_id, payload.question)
    answer = _generate_answer(payload.question, context)

    # Optional: Log chat & message (service role bypasses RLS)
    # You can uncomment and adapt if your schema has these columns.
    # chat_res = svc.table("chats").insert({
    #     "website_id": payload.website_id,
    #     "source": "web",  # or "widget"
    # }).select("id").single().execute()
    # chat_id = chat_res.data["id"]
    # svc.table("messages").insert([
    #     {"chat_id": chat_id, "role": "user", "content": payload.question},
    #     {"chat_id": chat_id, "role": "assistant", "content": answer},
    # ]).execute()

    return ChatAnswerOut(answer=answer, used_files=used, tokens_context=len(context) if context else 0)
