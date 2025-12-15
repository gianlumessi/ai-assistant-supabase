# backend/routers/chat.py
from __future__ import annotations

import io
import os
import re
from typing import Optional, List, Tuple
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl
from supabase import create_client
from fastapi.responses import StreamingResponse
import time
import json
from urllib.parse import urlparse
from collections import defaultdict, deque



# -------- Config --------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BUCKET = os.getenv("STORAGE_BUCKET_DOCS", "documents")
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "10"))
MAX_FILES_PER_QUERY = int(os.getenv("MAX_FILES_PER_QUERY", "5"))

# Service-role client (backend-only; never expose to browsers)
svc = create_client(SUPABASE_URL, SERVICE_ROLE)

router = APIRouter(prefix="/chat", tags=["chat"])

_RATE = defaultdict(deque)  # key -> timestamps
RATE_WINDOW_SEC = 60
RATE_MAX_REQ = 20  # per (website_id + ip) per minute


# -------- Models --------
class ChatQueryIn(BaseModel):
    website_id: str = Field(..., description="Tenant/website UUID")
    question: str = Field(..., min_length=3, max_length=4000)

class ChatAnswerOut(BaseModel):
    answer: str
    used_files: list[str] = []
    tokens_context: int | None = None

class ChatStreamIn(BaseModel):
    website_id: str = Field(..., description="Website UUID")
    session_id: str = Field(..., description="Chat session ID from the widget")
    visitor_id: str = Field(..., description="Visitor ID (chat_user_id) from the widget")
    message: str = Field(..., min_length=1, max_length=4000)
    page_url: Optional[HttpUrl] = None


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

def _origin_host(origin: str | None) -> str | None:
    if not origin:
        return None
    try:
        return urlparse(origin).hostname
    except Exception:
        return None

def _is_origin_allowed(website_id: str, origin: str | None) -> bool:
    """
    Allow only requests coming from the website's domain.
    """
    host = _origin_host(origin)
    if not host:
        return False

    res = (
        svc.from_("websites")
        .select("domain")
        .eq("id", website_id)
        .limit(1)
        .execute()
    )
    row = (res.data or [{}])[0]
    domain = (row.get("domain") or "").strip().lower()

    # basic normalize: allow exact match or www. variant
    host = host.lower()
    if host == domain:
        return True
    if domain.startswith("www.") and host == domain[4:]:
        return True
    if host.startswith("www.") and host[4:] == domain:
        return True
    return False

def _rate_limited(website_id: str, ip: str | None) -> bool:
    if not ip:
        ip = "unknown"
    key = f"{website_id}:{ip}"
    q = _RATE[key]
    now = time.time()

    # drop old
    while q and (now - q[0]) > RATE_WINDOW_SEC:
        q.popleft()

    if len(q) >= RATE_MAX_REQ:
        return True

    q.append(now)
    return False

def _get_or_create_chat(website_id: str, session_id: str, visitor_id: str) -> str:
    """
    Find a chat for (website_id, session_id) or create one.
    Returns chat.id (uuid as string).
    """
    # Try to find existing chat
    existing = (
        svc.from_("chats")
        .select("id")
        .eq("website_id", website_id)
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    data = existing.data or []
    if data:
        return data[0]["id"]

    # Create new chat
    insert_res = (
        svc.table("chats")
        .insert(
            {
                "website_id": website_id,
                "session_id": session_id,
                #"visitor_id": visitor_id,
                # let DB default started_at
            }
        )
        .execute()
    )

    # If insert returned the row, use it
    if insert_res.data:
        return insert_res.data[0]["id"]

    # Fallback: re-select
    created = (
        svc.from_("chats")
        .select("id")
        .eq("website_id", website_id)
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    return created.data[0]["id"]

def _insert_message(chat_id: str, role: str, content: str) -> str:
    """
    Insert a message row linked to a chat.
    """
    res = (
        svc.table("messages")
        .insert(
            {
                "chat_id": chat_id,
                "role": role,
                "content": content,
            }
        )
        .execute()
    )

    return res.data[0]["id"] if res.data else ""

def _storage_prefix(website_id: str) -> str:
    """
    Returns the storage folder for this website.
    Prefer websites.public_key (e.g. 'gianluca_website'), else fallback to UUID.
    """
    res = (
        svc.from_("websites")
        .select("public_key")
        .eq("id", website_id)
        .limit(1)
        .execute()
    )
    row = (res.data or [{}])[0]
    return row.get("public_key") or website_id


def _list_site_files(website_id: str) -> List[dict]:
    """
    List objects under documents/{website_id}/
    Returns a list of objects with .name and .metadata if available.
    """
    prefix = _storage_prefix(website_id)
    # Supabase Storage lists by prefix via .list(path=..., options=...)
    # We default to top-level under the website folder.
    objects = svc.storage.from_(BUCKET).list(path=prefix, options={"limit": 1000})
    # objects is a list of dicts like {"name": "folder_or_file", "id": "...", "metadata": {...}}
    # We must qualify to full path "website_id/name"
    for o in objects:
        o["full_path"] = f"{prefix}/{o['name']}"
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

@router.post("/stream")
def chat_stream(payload: ChatStreamIn, request: Request):
    """
    Streaming endpoint for the website chat bubble (REAL OpenAI token streaming).
    """
    def _sse_error(code: str, message: str, status_code: int = 200):
        def error_stream():
            payload_err = {"error": {"code": code, "message": message}}
            yield "event: final\n"
            yield f"data: {json.dumps(payload_err)}\n\n"
            yield "event: end\n"
            yield "data: {}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream", status_code=status_code)

    try:
        _validate_website_id(payload.website_id)

        origin = request.headers.get("origin")
        if not _is_origin_allowed(payload.website_id, origin):
            return _sse_error("INVALID_ORIGIN", "Origin not allowed for this website", status_code=403)

        ip = request.client.host if request.client else None
        if _rate_limited(payload.website_id, ip):
            return _sse_error("RATE_LIMITED", "Rate limit exceeded", status_code=429)

        # 1) Context
        context, used_files = _gather_context(payload.website_id, payload.message)
        tokens_context = len(context) if context else 0

        # 2) Chat + store user message (do this before streaming)
        chat_id = _get_or_create_chat(
            website_id=payload.website_id,
            session_id=payload.session_id,
            visitor_id=payload.visitor_id,  # ok if ignored in DB for now
        )
        _insert_message(chat_id, role="user", content=payload.message)

        # 3) SSE generator with real OpenAI stream
        def event_stream():
            start_ts = time.perf_counter()
            full_answer_parts: list[str] = []

            try:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    # Fallback: no streaming possible
                    answer = _generate_answer(payload.message, context)
                    full_answer_parts.append(answer)

                    # stream as a single token chunk
                    yield "event: token\n"
                    yield f"data: {json.dumps({'text': answer, 'seq': 1})}\n\n"
                    usage = None

                else:
                    from openai import OpenAI

                    client = OpenAI(api_key=api_key)

                    max_ctx = 6000
                    ctx = (context or "")[:max_ctx]

                    system_msg = (
                        "You are a helpful assistant. Answer using ONLY the context provided. "
                        "If the answer isn't in the context, say you don't have enough information."
                    )
                    user_msg = f"Question:\n{payload.message}\n\nContext:\n{ctx}"

                    seq = 0
                    usage = None

                    stream = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        temperature=0.2,
                        stream=True,
                        stream_options={"include_usage": True},
                    )

                    for chunk in stream:
                        # Some chunks contain usage (at the end) without delta content
                        if getattr(chunk, "usage", None) is not None:
                            usage = {
                                "prompt_tokens": chunk.usage.prompt_tokens,
                                "completion_tokens": chunk.usage.completion_tokens,
                                "total_tokens": chunk.usage.total_tokens,
                            }
                            continue

                        delta = chunk.choices[0].delta
                        text = getattr(delta, "content", None)
                        if not text:
                            continue

                        full_answer_parts.append(text)
                        seq += 1

                        yield "event: token\n"
                        yield f"data: {json.dumps({'text': text, 'seq': seq})}\n\n"

                full_answer = "".join(full_answer_parts).strip()
                latency_ms = int((time.perf_counter() - start_ts) * 1000)

                # Store assistant message after streaming completes
                _insert_message(chat_id, role="assistant", content=full_answer)

                final_payload = {
                    "message": full_answer,
                    "used_files": used_files,
                    "tokens_context": tokens_context,
                    "latency_ms": latency_ms,
                    "usage": usage,
                }

                yield "event: final\n"
                yield f"data: {json.dumps(final_payload)}\n\n"

            except Exception:
                payload_err = {
                    "error": {
                        "code": "STREAM_ERROR",
                        "message": "Error while generating/streaming response",
                    }
                }
                yield "event: final\n"
                yield f"data: {json.dumps(payload_err)}\n\n"

            finally:
                yield "event: end\n"
                yield "data: {}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except HTTPException as e:
        msg = e.detail if isinstance(e.detail, str) else "Request failed"
        return _sse_error("HTTP_ERROR", msg, status_code=e.status_code)

    except Exception:
        return _sse_error("INTERNAL", "Unexpected error while handling chat request", status_code=200)

