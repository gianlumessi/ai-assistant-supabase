"""
One-off ingestion script for local testing.

Downloads a document from Supabase Storage, extracts its text, splits it into
chunks, generates embeddings, and populates the document_chunks table for a
given website_id.

Intended for development/testing to validate the retrieval pipeline before
wiring ingestion into the document upload API.
"""

import os

from backend.core.supabase_client import get_supabase
from backend.services.ingest import ingest_text_into_chunks

WEBSITE_ID = 'dd5234b0-a3b0-4c34-b9e7-cdc1aa92528b'#os.getenv("TEST_WEBSITE_ID")  # set this in env
BUCKET = "documents"
PATH = "gianluca_website/faq_test.txt"     # your storage path inside the bucket


def main():
    supabase = get_supabase()

    # Download from Storage
    data = supabase.storage.from_(BUCKET).download(PATH)
    text = data.decode("utf-8", errors="replace")

    doc_id = ingest_text_into_chunks(
        website_id=WEBSITE_ID,
        text=text,
        file_name="faq_test.txt",
        storage_path=PATH,
        mime_type="text/plain",
    )

    print("Ingested OK. document_id =", doc_id)


if __name__ == "__main__":
    main()
