import os
import warnings
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_supabase(privileged: bool = True) -> Client:
    # ⚠️ Temporary reminder: defaulting to privileged=True for now
    if privileged:
        warnings.warn(
            "get_supabase() is using the SERVICE_ROLE_KEY by default — "
            "update this later to use user/tenant-level keys instead.",
            UserWarning
        )

    key = SUPABASE_SERVICE_ROLE_KEY if privileged else SUPABASE_ANON_KEY
    if not SUPABASE_URL or not key:
        raise RuntimeError("Supabase URL or Key missing. Check .env file.")
    return create_client(SUPABASE_URL, key)
