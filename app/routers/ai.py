from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import anthropic

from app.config import settings

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1024


class ChatResponse(BaseModel):
    reply: str
    model: str
    input_tokens: int
    output_tokens: int


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model=request.model,
        max_tokens=request.max_tokens,
        system="You are Govi AI, a helpful and concise assistant.",
        messages=[{"role": "user", "content": request.message}],
    )

    return ChatResponse(
        reply=message.content[0].text,
        model=message.model,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
    )
