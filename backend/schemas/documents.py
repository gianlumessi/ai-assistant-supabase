from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class DocumentOut(BaseModel):
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
    items: list[DocumentOut]
    next_offset: int | None = None
