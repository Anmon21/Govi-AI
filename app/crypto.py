from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


# _fernet — key loaded from env-backed settings; never persisted to DB or logged
def _fernet() -> Fernet:
    if not settings.fernet_key:
        raise RuntimeError("FERNET_KEY is not configured. Set it in .env.")
    return Fernet(settings.fernet_key.encode())


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed: invalid ciphertext or wrong key") from exc
