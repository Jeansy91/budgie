"""Encryption of stored bank data (Fernet: AES-128-CBC + HMAC-SHA256).

The key is derived from `BUDGIE_SECRET_KEY` and is never stored in the
database. Someone with only a database backup cannot read the data.
By default the PIN is not stored. Only if the user opts into automatic
fetching is it stored here encrypted too (see fints/autosync.py).
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings
from .i18n import t


class SecretKeyMissing(RuntimeError):
    pass


def _fernet() -> Fernet:
    secret = get_settings().secret_key
    if len(secret) < 16:
        raise SecretKeyMissing(t("crypto.key_missing"))
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
        raise ValueError(t("crypto.cannot_decrypt")) from exc
