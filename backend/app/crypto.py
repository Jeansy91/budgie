"""Encryption of stored bank data (Fernet: AES-128-CBC + HMAC-SHA256).

The key is derived from `BUDGIE_SECRET_KEY` and is never stored in the
database. Someone with only a database backup cannot read the data.
The PIN is not stored at all, not even encrypted.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class SecretKeyMissing(RuntimeError):
    pass


def _fernet() -> Fernet:
    secret = get_settings().secret_key
    if len(secret) < 16:
        raise SecretKeyMissing("BUDGIE_SECRET_KEY fehlt oder ist kürzer als 16 Zeichen")
    key = hashlib.sha256(b"budgie-fints\x00" + secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return _fernet().encrypt(data).decode()


def decrypt(token: str) -> bytes:
    try:
        return _fernet().decrypt(token.encode())
    except InvalidToken as exc:
        raise ValueError("Gespeicherte Bankdaten lassen sich nicht entschlüsseln (BUDGIE_SECRET_KEY geändert?)") from exc
