"""Security utilities: OIDC token validation, CSRF, session helpers."""
import hashlib
import hmac
import os
import time
from typing import Any, Optional
import httpx
from jose import jwt, JWTError
from .config import settings


_oidc_config_cache: dict[str, Any] = {}
_jwks_cache: dict[str, Any] = {}


async def fetch_oidc_config() -> dict[str, Any]:
    if _oidc_config_cache:
        return _oidc_config_cache
    if not settings.OIDC_DISCOVERY_URL:
        raise ValueError("OIDC_DISCOVERY_URL not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(settings.OIDC_DISCOVERY_URL)
        resp.raise_for_status()
        _oidc_config_cache.update(resp.json())
    return _oidc_config_cache


async def fetch_jwks(jwks_uri: str) -> dict[str, Any]:
    if _jwks_cache.get("uri") == jwks_uri and _jwks_cache.get("keys"):
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(jwks_uri)
        resp.raise_for_status()
        data = resp.json()
    _jwks_cache.clear()
    _jwks_cache["uri"] = jwks_uri
    _jwks_cache["keys"] = data["keys"]
    return _jwks_cache


async def validate_token(token: str) -> dict[str, Any]:
    """Validate a JWT access/ID token against the OIDC provider."""
    config = await fetch_oidc_config()
    jwks = await fetch_jwks(config["jwks_uri"])
    header = jwt.get_unverified_header(token)
    # find matching key
    key = next(
        (k for k in jwks["keys"] if k.get("kid") == header.get("kid")),
        None,
    ) or (jwks["keys"][0] if jwks["keys"] else None)
    if not key:
        raise JWTError("No matching JWKS key")
    claims = jwt.decode(
        token,
        key,
        algorithms=[header.get("alg", "RS256")],
        audience=settings.OIDC_CLIENT_ID,
        issuer=config["issuer"],
        options={"verify_exp": True, "verify_nbf": True},
    )
    return claims


def generate_csrf_token(session_id: str) -> str:
    """Generate a CSRF token tied to the session."""
    secret = settings.SESSION_SECRET.encode() or os.urandom(32)
    msg = f"{session_id}:{int(time.time()) // 3600}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_csrf_token(session_id: str, token: str) -> bool:
    expected_current = generate_csrf_token(session_id)
    return hmac.compare_digest(expected_current, token)


def get_role_from_claims(claims: dict[str, Any]) -> str:
    """Extract highest role from Keycloak realm_access.roles."""
    roles = claims.get("realm_access", {}).get("roles", [])
    if "admin" in roles:
        return "admin"
    if "analyst" in roles or "operator" in roles:
        return "analyst"
    return "viewer"
