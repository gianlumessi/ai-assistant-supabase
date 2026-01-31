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
from backend.core.config import config
from backend.core.logging_config import setup_logging

WEBSITE_ID = '8d0ab061-29ee-4fc6-be98-252f808b6d37'  # mercantidicalabria.com
BUCKET = "documents"
PATH = "mercanti_di_calabria/mercantidicalabria_faq.txt"


def main():
    # Initialize configuration
    print("Validating configuration...")
    config.validate_and_load()

    # Setup logging
    setup_logging(use_json=False, level='INFO')

    print(f"Downloading file from storage: {PATH}")
    supabase = get_supabase()

    # Download from Storage
    data = supabase.storage.from_(BUCKET).download(PATH)
    text = data.decode("utf-8", errors="replace")

    print(f"Downloaded {len(text)} characters")
    print(f"Ingesting for website: {WEBSITE_ID}")
    print("Generating embeddings and creating chunks...")
    print("(This may take 30-60 seconds depending on file size)")

    doc_id = ingest_text_into_chunks(
        website_id=WEBSITE_ID,
        text=text,
        file_name=PATH.split('/')[-1],  # Extract filename from path
        storage_path=PATH,
        mime_type="text/plain",
    )

    print("=" * 60)
    print("✅ INGESTION SUCCESSFUL!")
    print("=" * 60)
    print(f"Document ID: {doc_id}")
    print(f"Website ID: {WEBSITE_ID}")
    print("\nNext steps:")
    print("1. Verify in Supabase: SELECT COUNT(*) FROM document_chunks WHERE website_id = '{}'".format(WEBSITE_ID))
    print("2. Test the chatbot on your website!")
    print("=" * 60)


if __name__ == "__main__":
    main()
