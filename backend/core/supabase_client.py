import os
import warnings
from dotenv import load_dotenv
from supabase import create_client, Client

from backend.core.logging_config import get_logger
from backend.core.exceptions import ConfigurationError

load_dotenv()

logger = get_logger(__name__)

# Try to get from config, fallback to env vars
try:
    from backend.core.config import config
    SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY = config.get_supabase_config()
except Exception:
    # Fallback for initialization before config is loaded
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def get_supabase(privileged: bool = True) -> Client:
    """
    Get a Supabase client with appropriate permissions.

    Args:
        privileged: If True, uses SERVICE_ROLE_KEY (bypasses RLS).
                   If False, uses ANON_KEY (RLS applies).

    Returns:
        Supabase client instance

    Raises:
        ConfigurationError: If Supabase configuration is missing
    """
    # ⚠️ Temporary reminder: defaulting to privileged=True for now
    if privileged:
        warnings.warn(
            "get_supabase() is using the SERVICE_ROLE_KEY by default — "
            "update this later to use user/tenant-level keys instead.",
            UserWarning
        )

    key = SUPABASE_SERVICE_ROLE_KEY if privileged else SUPABASE_ANON_KEY
    if not SUPABASE_URL or not key:
        logger.error('Supabase configuration missing')
        raise ConfigurationError(
            "Supabase URL or Key missing. Check .env file.",
            details={'has_url': bool(SUPABASE_URL), 'privileged': privileged}
        )

    logger.debug(f'Creating Supabase client (privileged={privileged})')
    return create_client(SUPABASE_URL, key)
