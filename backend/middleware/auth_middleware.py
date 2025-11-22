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

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Optional: cache the client to save time
base_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Default: anonymous client
        request.state.supabase = base_client
        request.state.user = None

        # Get Authorization: Bearer <token>
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Allow anonymous (chatbot) requests to continue; they use service role later
            return await call_next(request)

        token = auth_header.split(" ")[1]
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
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid Supabase token")

        return await call_next(request)
