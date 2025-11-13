import logging
import secrets

from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.sessions import SessionMiddleware

from .admin_router import router as admin_router
from .admin_service import ensure_default_admin
from .api import router as api_router
from .config import get_settings
from .db import SessionLocal, engine
from .mcp import router as mcp_router
from .models import Base

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(api_router)
app.include_router(mcp_router)
app.include_router(admin_router)

session_secret = settings.session_secret_key or secrets.token_urlsafe(32)
app.add_middleware(SessionMiddleware, secret_key=session_secret, max_age=60 * 60 * 8)

logger = logging.getLogger(__name__)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_default_admin(session, logger=logger)
        session.commit()


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if settings.api_key and not request.url.path.startswith("/admin"):
        api_key = request.headers.get("x-api-key")
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    response = await call_next(request)
    return response


@app.get("/")
def read_root():
    return {"message": "Health MCP Server is running"}
