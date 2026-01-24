"""
backend/middleware/auth_middleware.py
-------------------------------------
Extracts the Supabase JWT from Authorization header,
verifies it, and attaches a Supabase client (user-scoped)
to request.state.supabase so RLS applies automatically.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from supabase import create_client
from jose import jwt, JWTError
import os

from backend.core.logging_config import get_logger, set_request_context
from backend.core.config import config

logger = get_logger(__name__)

# Get configuration from validated config
try:
    SUPABASE_URL, SUPABASE_ANON_KEY, _ = config.get_supabase_config()
except Exception:
    # Fallback for backward compatibility during initialization
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Optional: cache the client to save time
base_client = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    base_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate request ID for tracking
        import uuid
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Extract website_id from headers if present for logging context
        website_id = request.headers.get("x-website-id", "")

        # Set logging context
        set_request_context(request_id=request_id, website_id=website_id)

        # Default: anonymous client
        request.state.supabase = base_client
        request.state.user = None

        # Get Authorization: Bearer <token>
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Allow anonymous (chatbot) requests to continue; they use service role later
            logger.debug(
                f'Anonymous request: method={request.method}, path={request.url.path}'
            )
            return await call_next(request)

        # Extract token
        auth_parts = auth_header.split(" ")
        if len(auth_parts) != 2:
            logger.warning('Malformed Authorization header')
            raise HTTPException(status_code=401, detail="Malformed Authorization header")

        token = auth_parts[1]

        try:
            # Decode the JWT to verify it and extract user_id
            payload = jwt.get_unverified_claims(token)
            user_id = payload.get("sub")

            if user_id:
                request.state.user = {"user_id": user_id}
                # Create a user-scoped Supabase client (RLS applies automatically)
                request.state.supabase = create_client(
                    SUPABASE_URL,
                    SUPABASE_ANON_KEY,
                    options={"global": {"headers": {"Authorization": f"Bearer {token}"}}},
                )

                logger.info(
                    f'Authenticated request: user_id={user_id[:8]}..., '
                    f'method={request.method}, path={request.url.path}'
                )
            else:
                logger.warning('JWT token missing user ID (sub claim)')

        except JWTError as e:
            logger.warning(
                f'JWT validation failed: {str(e)}, method={request.method}, path={request.url.path}'
            )
            raise HTTPException(status_code=401, detail="Invalid Supabase token")
        except Exception as e:
            logger.error(
                f'Unexpected auth error: {str(e)}, method={request.method}, path={request.url.path}'
            )
            raise HTTPException(status_code=500, detail="Authentication error")

        return await call_next(request)
