from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, ai

app = FastAPI(title="Govi AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ai.router)
