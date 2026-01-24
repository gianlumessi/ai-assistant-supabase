from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.supabase_client import get_supabase
from backend.core.website import get_website_context, WebsiteContext
from backend.core.db import scoped_table
from backend.services.security import authenticate_request
from backend.middleware.auth_middleware import AuthMiddleware
from backend.routers import chat
#from backend.routers import documents <-- will be needed later when website owners will upload their docs
from fastapi.staticfiles import StaticFiles
from backend.core.logging_config import setup_logging, get_logger
from backend.core.config import config
from backend.core.exceptions import ConfigurationError, DatabaseError

# Validate environment variables before starting the application
try:
    config.validate_and_load()
except ConfigurationError as e:
    print(f"FATAL: {e}")
    raise SystemExit(1)

# Setup structured logging
setup_logging(
    use_json=config.USE_JSON_LOGGING,
    level=config.LOG_LEVEL
)

logger = get_logger(__name__)
logger.info('AI Assistant Backend starting up')

app = FastAPI(title="AI Assistant Backend")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    await authenticate_request(request)
    return await call_next(request)


# CORS (tighten later to your widget/app origins)
# TODO: make it tighter if required
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.mercantidicalabria.com",
                   "https://mercantidicalabria.com",
                   ## Dev origins:
                   "http://localhost:8000",
                   "http://localhost:5173",
                   "http://localhost:3000",
                   "http://127.0.0.1:5500",
                   "http://localhost:5500",
                   ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 Add middleware so RLS works for owners
app.add_middleware(AuthMiddleware)

# Routers
app.include_router(chat.router)
#app.include_router(documents.router) <-- will be needed later

# If you already have CORS & health routes, keep them as-is.

app.mount("/widget", StaticFiles(directory="frontend/widget", html=True), name="widget")

@app.get("/")
def root():
    return {"ok": True}

# Health: checks DB via anon key; point to an existing table (websites)
@app.get("/health/db")
def db_health():
    try:
        sb = get_supabase(privileged=False)
        res = sb.table("websites").select("id", count="exact").limit(1).execute()
        return {"ok": True, "count": res.count}
    except Exception as e:
        logger.error(f'Database health check failed: {str(e)}')
        raise HTTPException(status_code=503, detail='Database unavailable')

# Debug: privileged list of websites (admin only)
@app.get("/debug/websites")
def debug_websites():
    try:
        sb = get_supabase(privileged=True)
        res = sb.table("websites").select("*").limit(10).execute()
        return {"rows": res.data}
    except Exception as e:
        logger.error(f'Failed to fetch websites: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to fetch websites')

# ---------- Stage 1 core: Chats & Messages (scoped by website_id) ----------

# Create a chat
@app.post("/chats")
def create_chat(payload: dict = {}, website: WebsiteContext = Depends(get_website_context)):
    try:
        res = scoped_table("chats", website, privileged=False).insert({
            "title": payload.get("title", "New Chat")
        }).execute()
        logger.info(f'Chat created successfully for website {website.website_id}')
        return res.data
    except Exception as e:
        logger.error(f'Failed to create chat for website {website.website_id}: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to create chat')

# List chats for a website
@app.get("/chats")
def list_chats(website: WebsiteContext = Depends(get_website_context)):
    try:
        res = scoped_table("chats", website, privileged=False).select("id,title,created_at").execute()
        return res.data
    except Exception as e:
        logger.error(f'Failed to list chats for website {website.website_id}: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to list chats')

# Add a message to a chat
@app.post("/messages")
def add_message(payload: dict, website: WebsiteContext = Depends(get_website_context)):
    try:
        # expects: chat_id, role, content
        chat_id = payload.get("chat_id")
        if not chat_id:
            raise HTTPException(status_code=400, detail="chat_id is required")

        res = scoped_table("messages", website, privileged=False).insert({
            "chat_id": chat_id,
            "role": payload.get("role", "user"),
            "content": payload.get("content", ""),
        }).execute()
        logger.info(f'Message added to chat {chat_id}')
        return res.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to add message: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to add message')

# List messages for a chat
@app.get("/messages")
def list_messages(chat_id: str, website: WebsiteContext = Depends(get_website_context)):
    try:
        query = scoped_table("messages", website, privileged=False) \
            .select("id,role,content,created_at") \
            .eq("chat_id", chat_id)
        res = query.execute()
        return res.data
    except Exception as e:
        logger.error(f'Failed to list messages for chat {chat_id}: {str(e)}')
        raise HTTPException(status_code=500, detail='Failed to list messages')
