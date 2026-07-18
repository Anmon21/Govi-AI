import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import health, ai, content, auth, tenants, pages

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    content._vault.clear()
    content._vault.update(content.load_vault())
    yield


app = FastAPI(title="Govi AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ai.router)
app.include_router(content.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(pages.router)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/landing", include_in_schema=False)
async def landing():
    return FileResponse(os.path.join(_STATIC_DIR, "landing.html"))
