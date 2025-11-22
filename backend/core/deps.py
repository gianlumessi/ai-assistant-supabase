from fastapi import Header, HTTPException, status, Request

async def get_website_id(x_website_id: str | None = Header(default=None, alias="X-Website-Id")) -> str:
    if not x_website_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Website-Id header")
    return x_website_id

# Multitenant step will add: get_current_user() which validates the Authorization: Bearer <jwt>
# For Step 1, we treat user as optional to unblock local testing.
async def get_current_user_or_none(request: Request):
    return getattr(request.state, "user", None)
