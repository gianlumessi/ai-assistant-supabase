import os
import time
import httpx
from jose import jwt
from fastapi import Request, HTTPException, status
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
JWKS_URL = f"{SUPABASE_URL}/auth/v1/keys"
ANON = os.environ["SUPABASE_ANON_KEY"]

_jwks_cache = None
_jwks_ts = 0

async def get_jwks():
    global _jwks_cache, _jwks_ts
    if _jwks_cache and time.time() - _jwks_ts < 3600:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(JWKS_URL)
        r.raise_for_status()
        _jwks_cache = r.json()
        _jwks_ts = time.time()
        return _jwks_cache

async def authenticate_request(request: Request):
    auth = request.headers.get("Authorization", "").split()
    if len(auth) == 2 and auth[0].lower() == "bearer":
        token = auth[1]
        jwks = await get_jwks()
        try:
            claims = jwt.decode(token, jwks, algorithms=["RS256"], options={"verify_aud": False})
            request.state.user = type("User", (), {"user_id": claims.get("sub")})
            # Create a user-scoped client for downstream calls (RLS enforcement)
            request.state.supabase = create_client(SUPABASE_URL, token)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e
    else:
        # Anonymous (dev/local). Avoid in production.
        request.state.user = None
        request.state.supabase = create_client(SUPABASE_URL, ANON)
