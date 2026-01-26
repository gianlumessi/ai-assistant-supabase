import io
import os
import uuid
import hashlib
from typing import Tuple
from supabase import create_client

from backend.core.logging_config import get_logger
from backend.core.exceptions import StorageError, ConfigurationError
from backend.core.config import config

logger = get_logger(__name__)

# Get configuration from validated config
try:
    SUPABASE_URL, _, SUPABASE_SERVICE_ROLE_KEY = config.get_supabase_config()
except Exception:
    # Fallback for backward compatibility during initialization
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

BUCKET = os.getenv("STORAGE_BUCKET_DOCS", "documents")

_service_client = None
_bucket_created = False


def _get_service_client():
    """Get or create service client with proper error handling."""
    global _service_client
    if _service_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise ConfigurationError('Supabase configuration missing for storage service')
        _service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _service_client

def ensure_bucket_once() -> None:
    """
    Ensure storage bucket exists (idempotent).

    Raises:
        StorageError: If bucket creation fails unexpectedly
    """
    global _bucket_created
    if _bucket_created:
        return

    try:
        client = _get_service_client()
        # idempotent create; will raise if exists — ignore
        client.storage.create_bucket(BUCKET, {"public": False})
        logger.info(f'Storage bucket created: {BUCKET}')
    except Exception as e:
        error_msg = str(e).lower()
        # Ignore "already exists" errors
        if 'already exists' in error_msg or 'duplicate' in error_msg:
            logger.debug(f'Storage bucket already exists: {BUCKET}')
        else:
            logger.warning(f'Bucket creation attempt returned error (may be benign): {str(e)}')

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
    """
    Upload bytes to Supabase Storage.

    Args:
        user_client: Supabase client (user-scoped for RLS)
        website_id: Website ID for path organization
        original_name: Original filename
        data: File data as bytes
        mime_type: MIME type of the file

    Returns:
        Tuple of (storage_path, size_bytes, sha256_hash)

    Raises:
        StorageError: If upload fails
    """
    if not website_id:
        raise StorageError('website_id is required')

    if not original_name:
        raise StorageError('original_name is required')

    if not data:
        raise StorageError('Cannot upload empty file')

    if len(data) > 50 * 1024 * 1024:  # 50 MB limit
        raise StorageError(
            f'File too large: {len(data)} bytes (max 50 MB)',
            details={'size': len(data), 'filename': original_name}
        )

    try:
        ensure_bucket_once()
        path = build_object_path(website_id, original_name)
        sha256 = hash_bytes_sha256(data)

        logger.info(
            f'Uploading file: website_id={website_id}, filename={original_name}, '
            f'size={len(data)} bytes, mime_type={mime_type}, path={path}'
        )

        # Use user-scoped client to enforce storage RLS
        user_client.storage.from_(BUCKET).upload(path, io.BytesIO(data), {
            "contentType": mime_type,
            "upsert": False,
        })

        logger.info(
            f'File uploaded successfully: path={path}, sha256={sha256[:16]}...'
        )

        return path, len(data), sha256

    except StorageError:
        raise
    except Exception as e:
        logger.error(
            f'File upload failed: website_id={website_id}, filename={original_name}, '
            f'error={str(e)}'
        )
        raise StorageError(
            f'Failed to upload file: {str(e)}',
            details={
                'website_id': website_id,
                'filename': original_name,
                'size': len(data),
                'error': str(e)
            }
        )
