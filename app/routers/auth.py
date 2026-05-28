from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext

from app.auth import create_access_token
from app.config import settings
from app.db import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id, password_hash, is_super_admin FROM tenants WHERE email = ? AND is_active = 1",
            (request.email,),
        ).fetchone()
    finally:
        conn.close()

    if not row or not pwd_context.verify(request.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = "super_admin" if row["is_super_admin"] else "client"
    token = create_access_token(sub=str(row["id"]), role=role)
    return TokenResponse(access_token=token)
