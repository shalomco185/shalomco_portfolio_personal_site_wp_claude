"""התחברות פשוטה לשליח יחיד: סיסמה אחת, עוגייה חתומה (HMAC)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import HTTPException, Request, status

from .config import settings

COOKIE_NAME = "courier_session"


def _sign(payload: str) -> str:
    mac = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def make_token() -> str:
    expires = int(time.time()) + settings.session_days * 86400
    payload = f"v1.{expires}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str | None) -> bool:
    if not token or not settings.secret_key:
        return False
    try:
        version, expires, sig = token.split(".")
    except ValueError:
        return False
    payload = f"{version}.{expires}"
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    return expires.isdigit() and int(expires) > time.time()


def check_password(password: str) -> bool:
    if not settings.app_password:
        return False
    return hmac.compare_digest(password.encode(), settings.app_password.encode())


def require_login(request: Request) -> None:
    if not verify_token(request.cookies.get(COOKIE_NAME)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="נדרשת התחברות")
