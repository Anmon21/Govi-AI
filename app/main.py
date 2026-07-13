from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, ai, content, auth, tenants, pages


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
