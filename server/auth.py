"""
RemoteGate authentication endpoints and JWT helpers.

Provides:
- POST /api/login   – issue access + refresh tokens
- POST /api/refresh – rotate an access token
- verify_token()    – decode & validate a JWT (used by relay WS)
- In-memory rate-limiting on failed login attempts
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Rate-limiting state (in-memory)
# ---------------------------------------------------------------------------
# Maps client IP -> list of failure timestamps (most recent last).
_failed_attempts: dict[str, list[float]] = {}

_MAX_FAILURES = 5
_WINDOW_SECONDS = 15 * 60  # 15 minutes


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if the IP has exceeded the failure threshold."""
    now = time.time()
    attempts = _failed_attempts.get(ip, [])
    # Prune old entries outside the window
    attempts = [t for t in attempts if now - t < _WINDOW_SECONDS]
    _failed_attempts[ip] = attempts

    if len(attempts) >= _MAX_FAILURES:
        logger.warning("Rate-limited login from %s", ip)
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again later.",
        )


def _record_failure(ip: str) -> None:
    _failed_attempts.setdefault(ip, []).append(time.time())


def _clear_failures(ip: str) -> None:
    _failed_attempts.pop(ip, None)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_token(sub: str, expires_delta: timedelta, token_type: str = "access") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "exp": now + expires_delta,
        "iat": now,
        "type": token_type,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict:
    """Decode and validate a JWT.

    Returns:
        The decoded payload dict (contains 'sub', 'exp', 'type', etc.).

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: For any other validation failure.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate with username + password and receive JWT tokens."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # Validate credentials
    if body.username != settings.ADMIN_USERNAME:
        _record_failure(client_ip)
        logger.info("Login failed (bad username) from %s", client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not settings.ADMIN_PASSWORD_HASH:
        _record_failure(client_ip)
        logger.error("ADMIN_PASSWORD_HASH is not configured")
        raise HTTPException(status_code=500, detail="Server authentication not configured")

    password_ok = bcrypt.checkpw(
        body.password.encode("utf-8"),
        settings.ADMIN_PASSWORD_HASH.encode("utf-8"),
    )
    if not password_ok:
        _record_failure(client_ip)
        logger.info("Login failed (bad password) from %s", client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _clear_failures(client_ip)

    access_token = _create_token(
        sub=body.username,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
        token_type="access",
    )
    refresh_token = _create_token(
        sub=body.username,
        expires_delta=timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
        token_type="refresh",
    )

    logger.info("Login successful for user '%s' from %s", body.username, client_ip)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest) -> AccessTokenResponse:
    """Exchange a valid refresh token for a new access token."""
    try:
        payload = verify_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    access_token = _create_token(
        sub=payload["sub"],
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
        token_type="access",
    )
    return AccessTokenResponse(access_token=access_token)
