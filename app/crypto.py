from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


# _fernet — key loaded from env-backed settings; never persisted to DB or logged
def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(enc: str) -> str:
    return _fernet().decrypt(enc.encode()).decode()
