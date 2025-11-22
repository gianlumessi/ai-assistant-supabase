# backend/core/website.py
from fastapi import Header, HTTPException

class WebsiteContext:
    def __init__(self, website_id: str):
        self.website_id = website_id

async def get_website_context(x_website_id: str = Header(None)) -> WebsiteContext:
    if not x_website_id:
        raise HTTPException(status_code=400, detail="X-Website-Id header is required")
    return WebsiteContext(website_id=x_website_id)
