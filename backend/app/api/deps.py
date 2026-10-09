"""
Authentication dependencies for FastAPI.

Architecture: backend-managed sessions with HttpOnly SameSite=Lax cookies
and CSRF protection on cookie-authenticated write endpoints.

DEMO MODE: Only active when DEMO_MODE=true. Production startup (main.py)
refuses DEMO_MODE=true when PRODUCTION=true is set. Per-request demo access
is unconditional once DEMO_MODE is enabled (the startup guard is the gate).
"""
from __future__ import annotations

import os
from typing import Annotated, Any, Optional

from fastapi import Cookie, Depends, HTTPException, Header, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.security import validate_token, get_role_from_claims, verify_csrf_token

DEMO_CLAIMS: dict[str, Any] = {
    "sub": "demo-user",
    "preferred_username": "demo",
    "email": "demo@localhost",
    "realm_access": {"roles": ["admin"]},
}


class CurrentUser:
    def __init__(self, claims: dict[str, Any]):
        self.sub: str = claims.get("sub", "anonymous")
        self.email: str = claims.get("email", "")
        self.username: str = claims.get("preferred_username", self.sub)
        self.role: str = get_role_from_claims(claims)
        self.claims: dict[str, Any] = claims

    def require_role(self, minimum: str) -> None:
        order = {"viewer": 0, "analyst": 1, "admin": 2}
        if order.get(self.role, 0) < order.get(minimum, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum}' required; you have '{self.role}'.",
            )


async def get_current_user(
    request: Request,
    session_token: Annotated[Optional[str], Cookie(alias="session_token")] = None,
) -> CurrentUser:
    """
    Resolve the current authenticated user from the session cookie.
    In demo mode, returns a synthetic admin user (startup prevents this in production).
    """
    if settings.DEMO_MODE:
        return CurrentUser(DEMO_CLAIMS)

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The session_token is the validated id_token stored server-side on login
    try:
        claims = await validate_token(session_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        ) from exc

    return CurrentUser(claims)


async def require_analyst(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    user.require_role("analyst")
    return user


async def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    user.require_role("admin")
    return user


def verify_csrf(
    request: Request,
    x_csrf_token: str | None = None,
    session_token: str | None = None,
) -> None:
    """CSRF check for cookie-authenticated write endpoints. Skip in demo mode."""
    if settings.DEMO_MODE:
        return
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session.")
    if not x_csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token required.")
    if not verify_csrf_token(session_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid.")
