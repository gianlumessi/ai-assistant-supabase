# backend/routers/chat.py
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl
from supabase import create_client
from fastapi.responses import StreamingResponse
from urllib.parse import urlparse
from collections import defaultdict, deque
from backend.services.retrieval import gather_context
from backend.core.logging_config import get_logger
from backend.core.config import config
from backend.core.exceptions import RetrievalError, DatabaseError
import io, re, json, os, time, uuid, logging


# -------- Config --------
# Get configuration from validated config
try:
    SUPABASE_URL, _, SERVICE_ROLE = config.get_supabase_config()
except Exception:
    # Fallback for initialization
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SERVICE_ROLE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

BUCKET = os.getenv("STORAGE_BUCKET_DOCS", "documents")
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "10"))
MAX_FILES_PER_QUERY = int(os.getenv("MAX_FILES_PER_QUERY", "5"))

# Service-role client (backend-only; never expose to browsers)
svc = create_client(SUPABASE_URL, SERVICE_ROLE) if SUPABASE_URL and SERVICE_ROLE else None

router = APIRouter(prefix="/chat", tags=["chat"])
log = get_logger(__name__)

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

#TODO: remove the below after successful testing and use checks below
#_site_id_re = re.compile(r"^[A-Za-z0-9_-]{3,64}$") #for testing
#def _validate_website_id(website_id: str) -> None:
#    if not _site_id_re.match(website_id):
#        raise HTTPException(status_code=400, detail="Invalid website_id format")

_uuid_re = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)

def _validate_uuid(value: str, field_name: str) -> None:
    if not _uuid_re.match(value or ""):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")

def _validate_website_id(website_id: str) -> None:
    _validate_uuid(website_id, "website_id")



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
    Ensures visitor_id is set on the chat row.
    Returns chat.id (uuid as string).
    """
    existing = (
        svc.from_("chats")
        .select("id, visitor_id")
        .eq("website_id", website_id)
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    data = existing.data or []
    if data:
        chat_id = data[0]["id"]
        existing_visitor = data[0].get("visitor_id")

        # If visitor_id was previously missing, backfill it
        if not existing_visitor and visitor_id:
            svc.table("chats").update({"visitor_id": visitor_id}).eq("id", chat_id).execute()

        return chat_id

    # Create new chat WITH visitor_id
    insert_res = (
        svc.table("chats")
        .insert(
            {
                "website_id": website_id,
                "session_id": session_id,
                "visitor_id": visitor_id,
                # started_at default is handled by DB
            }
        )
        .execute()
    )

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
    If the answer isn't in the context, say there is not enough information.

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
    _validate_uuid(payload.visitor_id, "visitor_id")
    _validate_uuid(payload.session_id, "session_id")

    context, used_files = gather_context(payload.website_id, payload.message)
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

    return ChatAnswerOut(answer=answer, used_files=used_files, tokens_context=len(context) if context else 0)

def _fetch_recent_messages(chat_id: str, limit: int = 16):
    res = (
        svc.table("messages")
        .select("role,content,created_at")
        .eq("chat_id", chat_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    rows.reverse()  # chronological
    return [{"role": r["role"], "content": r["content"]} for r in rows]


@router.post("/stream")
def chat_stream(payload: ChatStreamIn, request: Request):
    """
    Streaming endpoint for the website chat bubble (REAL OpenAI token streaming).
    SSE events:
      - token: {"text": "...", "seq": n}
      - final: {"message": "...", "used_files": [...], "tokens_context": n, "latency_ms": n, "usage": {...}, "request_id": "..."}
               OR {"error": {...}, "request_id": "..."}
      - end: {}
    """
    request_id = str(uuid.uuid4())

    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\n" f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _error_payload(code: str, message: str, retryable: bool) -> dict:
        return {
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "request_id": request_id,
            },
            "request_id": request_id,
        }

    def _sse_error_response(code: str, message: str, status_code: int, retryable: bool):
        def error_stream():
            yield _sse("final", _error_payload(code, message, retryable))
            yield _sse("end", {})
        return StreamingResponse(error_stream(), media_type="text/event-stream", status_code=status_code)

    # ---- Early validation / guardrails (must return a proper SSE final+end) ----
    try:
        _validate_website_id(payload.website_id)

        origin = request.headers.get("origin")
        if not _is_origin_allowed(payload.website_id, origin):
            return _sse_error_response(
                "INVALID_ORIGIN",
                "Origin not allowed for this website.",
                status_code=403,
                retryable=False,
            )

        ip = request.client.host if request.client else None
        if _rate_limited(payload.website_id, ip):
            return _sse_error_response(
                "RATE_LIMITED",
                "Rate limit exceeded. Please try again shortly.",
                status_code=429,
                retryable=True,
            )

        # 1) Context (do not fail the whole request if retrieval breaks)
        try:
            context, used_files = gather_context(payload.website_id, payload.message)
        except Exception:
            log.exception("Context retrieval failed request_id=%s website_id=%s", request_id, payload.website_id)
            context, used_files = "", []
        tokens_context = len(context) if context else 0

        # 2) Chat + store user message (best-effort)
        chat_id = _get_or_create_chat(
            website_id=payload.website_id,
            session_id=payload.session_id,
            visitor_id=payload.visitor_id,
        )

        history = _fetch_recent_messages(chat_id, limit=20)
        history = [m for m in history if m.get("role") in ("user", "assistant")]

        try:
            _insert_message(chat_id, role="user", content=payload.message)
        except Exception:
            log.exception("Failed to persist user message request_id=%s chat_id=%s", request_id, chat_id)

    except HTTPException as e:
        msg = e.detail if isinstance(e.detail, str) else "Request failed."
        # Most HTTPExceptions here are non-retryable client issues
        return _sse_error_response("HTTP_ERROR", msg, status_code=e.status_code, retryable=False)
    except Exception:
        log.exception("Pre-stream failure request_id=%s", request_id)
        return _sse_error_response(
            "INTERNAL",
            "Unexpected error while handling the request.",
            status_code=500,
            retryable=True,
        )

    # ---- SSE generator (must always emit final then end) ----
    def event_stream():
        start_ts = time.perf_counter()
        full_answer_parts: list[str] = []
        usage = None

        try:
            api_key = os.getenv("OPENAI_API_KEY")

            # Build messages (system + optional context + history + user)
            max_ctx = 6000
            ctx = (context or "")[:max_ctx]

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Answer using the provided context and "
                        "the conversation history. If the answer is not supported, say you "
                        "do not have enough information to answer the question and advise "
                        "the user to message the website owner."
                    ),
                }
            ]
            if ctx:
                messages.append({"role": "system", "content": f"Context for answering:\n\n{ctx}"})
            messages.extend(history)
            messages.append({"role": "user", "content": payload.message})

            # If no API key, fallback to non-stream generation, but keep SSE contract
            if not api_key:
                answer = _generate_answer(payload.message, context)
                answer = (answer or "").strip()
                if answer:
                    full_answer_parts.append(answer)
                    yield _sse("token", {"text": answer, "seq": 1})
                # usage stays None

            else:
                from openai import OpenAI

                # Add timeout to reduce hang risk (MVP-safe)
                client = OpenAI(api_key=api_key)

                seq = 0
                stream = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.2,
                    stream=True,
                    stream_options={"include_usage": True},
                    # OpenAI python supports request-level timeout via http client settings in some versions;
                    # keep this if supported in your installed version:
                    timeout=60,
                )

                for chunk in stream:
                    # Usage appears at the end (no delta)
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
                    yield _sse("token", {"text": text, "seq": seq})

            full_answer = "".join(full_answer_parts).strip()
            latency_ms = int((time.perf_counter() - start_ts) * 1000)

            # Persist assistant message best-effort
            try:
                if full_answer:
                    _insert_message(chat_id, role="assistant", content=full_answer)
            except Exception:
                log.exception("Failed to persist assistant message request_id=%s chat_id=%s", request_id, chat_id)

            final_payload = {
                "message": full_answer,
                "used_files": used_files,
                "tokens_context": tokens_context,
                "latency_ms": latency_ms,
                "usage": usage,
                "request_id": request_id,
            }
            yield _sse("final", final_payload)

        except Exception:
            log.exception("Stream error request_id=%s chat_id=%s", request_id, chat_id)
            yield _sse(
                "final",
                _error_payload(
                    code="STREAM_ERROR",
                    message="Error while generating the response. Please try again.",
                    retryable=True,
                ),
            )
        finally:
            yield _sse("end", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")

