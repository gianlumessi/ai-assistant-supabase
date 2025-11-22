import io
import os
import uuid
import hashlib
from typing import Tuple
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BUCKET = os.getenv("STORAGE_BUCKET_DOCS", "documents")

_service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

_bucket_created = False

def ensure_bucket_once() -> None:
    global _bucket_created
    if _bucket_created:
        return
    try:
        # idempotent create; will raise if exists — ignore
        _service_client.storage.create_bucket(BUCKET, {"public": False})
    except Exception:
        pass
    _bucket_created = True


def safe_filename(name: str) -> str:
    # extremely simple sanitization; customize if needed
    return name.replace("/", "-")


def hash_bytes_sha256(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def build_object_path(website_id: str, original_name: str) -> str:
    return f"{website_id}/{uuid.uuid4()}_{safe_filename(original_name)}"


def upload_bytes(user_client, website_id: str, original_name: str, data: bytes, mime_type: str) -> Tuple[str, int, str]:
    """Uploads to Supabase Storage with the *caller* client (end-user JWT once Step 2 is enabled).
    Returns (path, size_bytes, sha256).
    """
    ensure_bucket_once()
    path = build_object_path(website_id, original_name)
    # Use user-scoped client to enforce storage RLS (Step 2). For Step 1, user_client may be a service client when testing.
    user_client.storage.from_(BUCKET).upload(path, io.BytesIO(data), {
        "contentType": mime_type,
        "upsert": False,
    })
    return path, len(data), hash_bytes_sha256(data)
