import jwt
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.config import settings


# oauth2_scheme — FastAPI security scheme for Bearer token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(sub: str, role: str) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured. Set it in .env.")
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_tenant(token: str = Depends(oauth2_scheme)) -> dict:
    return verify_token(token)


async def require_super_admin(current: dict = Depends(get_current_tenant)) -> dict:
    if current.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current
