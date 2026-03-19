"""
GridIQ SaaS — JWT Token Service
================================
Issues and verifies JWT access tokens and refresh tokens.

Access token:  short-lived (1 hour), sent with every API request
Refresh token: long-lived (30 days), used to get new access tokens
               stored in httpOnly cookie — never accessible to JS

Token payload includes tenant_id and role so every API endpoint
can enforce tenant isolation and RBAC without a DB lookup.
"""
from __future__ import annotations

import json
import hmac
import hashlib
import base64
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

ACCESS_TOKEN_TTL_SECONDS  = 3600       # 1 hour
REFRESH_TOKEN_TTL_SECONDS = 2592000    # 30 days
ALGORITHM = "HS256"


@dataclass
class TokenPayload:
    user_id:   str
    tenant_id: str
    email:     str
    role:      str
    exp:       int       # unix timestamp
    iat:       int       # issued at
    token_type: str      # "access" or "refresh"


# ── Pure-Python JWT (no PyJWT dependency) ─────────────────────────────────────
# Uses HMAC-SHA256 which is exactly what PyJWT HS256 does.
# This avoids a dependency while staying spec-compliant.

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)


def _sign(header_b64: str, payload_b64: str, secret: str) -> str:
    msg = f"{header_b64}.{payload_b64}".encode('utf-8')
    sig = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


class TokenService:
    """
    Issues, verifies, and refreshes JWT tokens.
    In production: secret loaded from environment variable JWT_SECRET_KEY.
    """

    def __init__(self, secret: Optional[str] = None):
        import os
        self._secret = secret or os.getenv('JWT_SECRET_KEY', 'dev-secret-change-in-production-please')
        if self._secret == 'dev-secret-change-in-production-please':
            logger.warning("[TokenService] Using default dev secret — set JWT_SECRET_KEY in production!")

    def issue_access_token(self, user_id: str, tenant_id: str,
                           email: str, role: str) -> str:
        """Issue a short-lived access token (1 hour)."""
        return self._encode({
            "user_id":    user_id,
            "tenant_id":  tenant_id,
            "email":      email,
            "role":       role,
            "token_type": "access",
            "iat":        int(time.time()),
            "exp":        int(time.time()) + ACCESS_TOKEN_TTL_SECONDS,
        })

    def issue_refresh_token(self, user_id: str, tenant_id: str,
                            email: str, role: str) -> str:
        """Issue a long-lived refresh token (30 days)."""
        return self._encode({
            "user_id":    user_id,
            "tenant_id":  tenant_id,
            "email":      email,
            "role":       role,
            "token_type": "refresh",
            "iat":        int(time.time()),
            "exp":        int(time.time()) + REFRESH_TOKEN_TTL_SECONDS,
        })

    def verify(self, token: str, expected_type: str = "access") -> Optional[TokenPayload]:
        """
        Verify a token and return its payload.
        Returns None if invalid, expired, or wrong type.
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None

            header_b64, payload_b64, sig_b64 = parts

            # Verify signature
            expected_sig = _sign(header_b64, payload_b64, self._secret)
            if not hmac.compare_digest(expected_sig, sig_b64):
                logger.debug("[TokenService] Signature mismatch")
                return None

            # Decode payload
            payload = json.loads(_b64url_decode(payload_b64))

            # Check expiry
            if payload.get('exp', 0) < time.time():
                logger.debug("[TokenService] Token expired")
                return None

            # Check type
            if payload.get('token_type') != expected_type:
                logger.debug(f"[TokenService] Wrong token type: {payload.get('token_type')}")
                return None

            return TokenPayload(
                user_id=payload['user_id'],
                tenant_id=payload['tenant_id'],
                email=payload['email'],
                role=payload['role'],
                exp=payload['exp'],
                iat=payload['iat'],
                token_type=payload['token_type'],
            )
        except Exception as exc:
            logger.debug(f"[TokenService] Verify failed: {exc}")
            return None

    def refresh(self, refresh_token: str) -> Optional[tuple[str, str]]:
        """
        Exchange a valid refresh token for a new access + refresh token pair.
        Returns (new_access_token, new_refresh_token) or None.
        """
        payload = self.verify(refresh_token, expected_type="refresh")
        if not payload:
            return None

        new_access  = self.issue_access_token(
            payload.user_id, payload.tenant_id, payload.email, payload.role
        )
        new_refresh = self.issue_refresh_token(
            payload.user_id, payload.tenant_id, payload.email, payload.role
        )
        return new_access, new_refresh

    def _encode(self, payload: dict) -> str:
        header = {"alg": ALGORITHM, "typ": "JWT"}
        header_b64  = _b64url_encode(json.dumps(header, separators=(',',':')).encode())
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(',',':')).encode())
        sig = _sign(header_b64, payload_b64, self._secret)
        return f"{header_b64}.{payload_b64}.{sig}"


# ── Singleton ─────────────────────────────────────────────────────────────────
token_service = TokenService()
