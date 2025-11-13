from fastapi import FastAPI, HTTPException, Request

from .api import router as api_router
from .config import get_settings
from .db import engine
from .mcp import router as mcp_router
from .models import Base

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(api_router)
app.include_router(mcp_router)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if settings.api_key:
        api_key = request.headers.get("x-api-key")
        if api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    response = await call_next(request)
    return response


@app.get("/")
def read_root():
    return {"message": "Health MCP Server is running"}
