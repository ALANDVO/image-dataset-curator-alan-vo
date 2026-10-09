"""OIDC authorization-code + PKCE auth endpoints."""
from __future__ import annotations

import os
import secrets
import urllib.parse
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse, JSONResponse

from ..core.config import settings
from ..core.security import fetch_oidc_config, validate_token, get_role_from_claims, generate_csrf_token
from .deps import get_current_user, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Start OIDC authorization-code + PKCE flow."""
    if not settings.OIDC_DISCOVERY_URL:
        raise HTTPException(status_code=503, detail="OIDC not configured.")
    oidc = await fetch_oidc_config()
    auth_endpoint = oidc["authorization_endpoint"]

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    # code_challenge = base64url(SHA-256(verifier))
    import hashlib, base64
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    # Store state/nonce/verifier in a short-lived cookie (server side)
    redirect_uri = f"{settings.FRONTEND_URL}/auth/callback"
    params = {
        "response_type": "code",
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{auth_endpoint}?" + urllib.parse.urlencode(params)

    response = RedirectResponse(url=auth_url, status_code=302)
    # Store verifier/state in short-lived HttpOnly cookies (server-side PKCE)
    response.set_cookie("pkce_verifier", code_verifier, httponly=True, samesite="lax", max_age=600, secure=not settings.DEMO_MODE)
    response.set_cookie("oauth_state", state, httponly=True, samesite="lax", max_age=600, secure=not settings.DEMO_MODE)
    response.set_cookie("oauth_nonce", nonce, httponly=True, samesite="lax", max_age=600, secure=not settings.DEMO_MODE)
    return response


@router.get("/callback")
async def callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    pkce_verifier: Annotated[str | None, Cookie()] = None,
    oauth_state: Annotated[str | None, Cookie()] = None,
    oauth_nonce: Annotated[str | None, Cookie()] = None,
) -> RedirectResponse:
    """Exchange authorization code for tokens; set session cookie."""
    if error:
        raise HTTPException(status_code=400, detail=f"OIDC error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state.")
    if not oauth_state or state != oauth_state:
        raise HTTPException(status_code=400, detail="State mismatch (CSRF check failed).")
    if not pkce_verifier:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier.")

    oidc = await fetch_oidc_config()
    token_endpoint = oidc["token_endpoint"]
    redirect_uri = f"{settings.FRONTEND_URL}/auth/callback"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": pkce_verifier,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Token exchange failed.")

    tokens = resp.json()
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status_code=502, detail="No id_token in response.")

    # Validate id_token
    claims = await validate_token(id_token)
    if claims.get("nonce") != oauth_nonce:
        raise HTTPException(status_code=400, detail="Nonce mismatch.")

    # Store id_token as session (HttpOnly, SameSite=Lax)
    secure = not settings.DEMO_MODE
    redir = RedirectResponse(url=f"{settings.FRONTEND_URL}/", status_code=302)
    redir.set_cookie("session_token", id_token, httponly=True, samesite="lax", max_age=3600, secure=secure)
    # Clear PKCE cookies
    redir.delete_cookie("pkce_verifier")
    redir.delete_cookie("oauth_state")
    redir.delete_cookie("oauth_nonce")
    return redir


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear session cookie."""
    response.delete_cookie("session_token", httponly=True, samesite="lax")
    return {"status": "logged out"}


@router.get("/me")
async def me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    request: Request,
) -> dict[str, Any]:
    """Return current user info and a CSRF token."""
    csrf = generate_csrf_token(user.sub)
    return {
        "sub": user.sub,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "csrf_token": csrf,
    }
