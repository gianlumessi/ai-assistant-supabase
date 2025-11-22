"""
backend/routers/documents.py

This module provides routes for website owners to manage their chatbot documents.
It connects the FastAPI backend to Supabase Storage and the `public.documents` table.

Function	        Purpose
upload_document()	Uploads a new file (owner-only).
list_documents()	Lists documents for a website (owner-only).
get_download_url()	Creates a short-lived download link (owner-only).
delete_document()	Removes both the file and its record (owner-only).

This router gives your backend complete document management for website owners while respecting the RLS and storage policies you set up earlier.

"""

import io
import os
import uuid
import hashlib
from typing import Optional
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel

# =========================
# Configuration
# =========================
# Bucket name in Supabase Storage
BUCKET = os.getenv("STORAGE_BUCKET_DOCS", "documents")
# Optional file size limit (25 MB by default)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))

router = APIRouter(prefix="/documents", tags=["documents"])


# =========================
# Dependencies
# =========================
async def get_website_id(x_website_id: Optional[str] = Header(None, alias="X-Website-Id")) -> str:
    """
    Extracts the website ID from the X-Website-Id header.
    Every request must include this, because it identifies which website (tenant)
    the operation applies to.
    """
    if not x_website_id:
        raise HTTPException(status_code=400, detail="Missing X-Website-Id header")
    return x_website_id


def _require_request(request: Optional[Request]) -> Request:
    """
    Ensures that the request contains the Supabase client injected by
    the authentication middleware. Without it, RLS cannot apply properly.
    """
    if request is None or not getattr(request.state, "supabase", None):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Supabase client missing. Make sure Auth middleware is enabled."
        )
    return request


# =========================
# Pydantic Schemas (Response models)
# =========================
class DocumentOut(BaseModel):
    """Model for a single document returned to the frontend."""
    id: str
    website_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    checksum_sha256: str
    created_by: Optional[str] = None
    created_at: datetime


class DocumentListOut(BaseModel):
    """Model for listing documents with pagination."""
    items: list[DocumentOut]
    next_offset: Optional[int] = None


# =========================
# Utility functions
# =========================
def _safe_filename(name: str) -> str:
    """Sanitize filenames to avoid slashes or weird characters."""
    return name.replace("/", "-").strip()


def _sha256(data: bytes) -> str:
    """Compute SHA256 checksum of uploaded bytes (for file integrity)."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _object_path(website_id: str, original_name: str) -> str:
    """Generate a unique file path under {website_id}/{uuid}_{filename}."""
    return f"{website_id}/{uuid.uuid4()}_{_safe_filename(original_name)}"


def _get_signed_url_dict_value(d: dict) -> Optional[str]:
    """Extract signed URL from Supabase client response (handles version differences)."""
    return d.get("signedURL") or d.get("signed_url") or d.get("data", {}).get("signedURL") or d.get("data", {}).get("signed_url")


# =========================
# Routes
# =========================

@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request,
    website_id: str = Depends(get_website_id),
    file: UploadFile = File(...),
):
    """
    Upload a new file for a specific website.
    1. Uploads to Supabase Storage
    2. Inserts metadata in public.documents
    Both steps are protected by RLS (owner-only).
    """
    request = _require_request(request)
    client = request.state.supabase

    # Validate file
    if not file.filename:
        raise HTTPException(400, "Missing filename")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")

    mime_type = file.content_type or "application/octet-stream"
    path = _object_path(website_id, file.filename)

    # Step 1: Upload to storage
    try:
        client.storage.from_(BUCKET).upload(
            path,
            io.BytesIO(raw),
            {"contentType": mime_type, "upsert": False},
        )
    except Exception as e:
        raise HTTPException(403, f"Storage upload failed: {str(e)}")

    # Step 2: Add metadata record in public.documents
    doc_row = {
        "website_id": website_id,
        "file_name": file.filename,
        "mime_type": mime_type,
        "size_bytes": len(raw),
        "storage_path": path,
        "checksum_sha256": _sha256(raw),
        "created_by": getattr(getattr(request.state, "user", None), "user_id", None),
    }

    try:
        resp = client.table("documents").insert(doc_row).select("*").single().execute()
    except Exception as e:
        # Cleanup the uploaded file if DB insert fails
        try:
            client.storage.from_(BUCKET).remove([path])
        except Exception:
            pass
        raise HTTPException(403, f"DB insert failed: {str(e)}")

    if not resp or not getattr(resp, "data", None):
        raise HTTPException(500, "Failed to insert document row")

    return resp.data


@router.get("", response_model=DocumentListOut)
async def list_documents(
    request: Request,
    website_id: str = Depends(get_website_id),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    """List all documents for the given website (RLS owner-only)."""
    request = _require_request(request)
    client = request.state.supabase

    q = (
        client.table("documents")
        .select("*")
        .eq("website_id", website_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    resp = q.execute()
    items = resp.data or []
    next_offset = offset + limit if len(items) == limit else None
    return {"items": items, "next_offset": next_offset}


@router.get("/{doc_id}/download_url")
async def get_download_url(
    request: Request,
    doc_id: str = Path(...),
    website_id: str = Depends(get_website_id),
    expires_in_seconds: int = Query(120, ge=30, le=3600),
):
    """Generate a short-lived signed URL to download a file (owner-only)."""
    request = _require_request(request)
    client = request.state.supabase

    row = (
        client.table("documents")
        .select("id, website_id, storage_path")
        .eq("id", doc_id)
        .eq("website_id", website_id)
        .single()
        .execute()
    )
    if not row or not row.data:
        raise HTTPException(404, "Document not found")

    path = row.data["storage_path"]
    signed = client.storage.from_(BUCKET).create_signed_url(path, expires_in_seconds)
    url = _get_signed_url_dict_value(signed)
    if not url:
        raise HTTPException(500, "Failed to create signed URL")
    return {"url": url, "expires_in": expires_in_seconds}


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    request: Request,
    doc_id: str = Path(...),
    website_id: str = Depends(get_website_id),
):
    """Delete both the file and its metadata record (owner-only)."""
    request = _require_request(request)
    client = request.state.supabase

    # Step 1: Get document row (RLS enforces ownership)
    res = (
        client.table("documents")
        .select("id, website_id, storage_path")
        .eq("id", doc_id)
        .eq("website_id", website_id)
        .single()
        .execute()
    )
    if not res or not res.data:
        raise HTTPException(404, "Document not found")

    path = res.data["storage_path"]

    # Step 2: Delete storage file
    try:
        client.storage.from_(BUCKET).remove([path])
    except Exception as e:
        msg = str(e)
        if "not found" not in msg.lower():
            raise HTTPException(403, f"Failed to delete storage object: {msg}")

    # Step 3: Delete DB row
    client.table("documents").delete().eq("id", doc_id).eq("website_id", website_id).execute()
    return
