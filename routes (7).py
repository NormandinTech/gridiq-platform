"""
GridIQ SaaS — Authentication & User Models
==========================================
Users belong to a Tenant (one utility = one tenant).
A tenant can have multiple users with different roles.

Roles:
  owner       — created the account, manages billing
  admin       — full platform access, can invite users
  operator    — can view + acknowledge alerts, create work orders
  viewer      — read-only dashboard access
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional


class UserRole(str, Enum):
    OWNER    = "owner"
    ADMIN    = "admin"
    OPERATOR = "operator"
    VIEWER   = "viewer"


class UserStatus(str, Enum):
    PENDING  = "pending"    # email not yet verified
    ACTIVE   = "active"
    SUSPENDED= "suspended"
    DELETED  = "deleted"


class TenantStatus(str, Enum):
    ONBOARDING = "onboarding"   # signed up, not yet connected data
    ACTIVE     = "active"       # paying, connected
    PILOT      = "pilot"        # 90-day pilot in progress
    PAST_DUE   = "past_due"     # payment failed
    CANCELLED  = "cancelled"


class PlanTier(str, Enum):
    PILOT        = "pilot"         # $10K pilot
    STARTER      = "starter"       # $48K/yr
    PROFESSIONAL = "professional"  # $240K/yr
    ENTERPRISE   = "enterprise"    # custom


# ── Tenant (one per utility) ──────────────────────────────────────────────────

@dataclass
class Tenant:
    """
    A utility company that has signed up for GridIQ.
    All their users, assets, telemetry, and alerts are scoped to this tenant.
    """
    tenant_id: str
    name: str                        # "Pacific Gas & Electric"
    slug: str                        # "pge" — used in URLs
    status: TenantStatus = TenantStatus.ONBOARDING
    plan: PlanTier = PlanTier.PILOT
    # Contact
    primary_email: str = ""
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    # Billing
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    plan_asset_limit: int = 500
    current_asset_count: int = 0
    pilot_start_date: Optional[str] = None
    pilot_end_date: Optional[str] = None
    subscription_start: Optional[str] = None
    subscription_end: Optional[str] = None
    # SCADA connection
    scada_connected: bool = False
    scada_protocol: Optional[str] = None
    scada_host: Optional[str] = None
    onboarding_step: int = 1         # 1-5 onboarding wizard steps
    onboarding_complete: bool = False
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    settings: Dict = field(default_factory=dict)


# ── User ──────────────────────────────────────────────────────────────────────

@dataclass
class User:
    """A person who logs in to GridIQ."""
    user_id: str
    tenant_id: str
    email: str
    full_name: str
    role: UserRole = UserRole.OPERATOR
    status: UserStatus = UserStatus.PENDING
    # Auth
    password_hash: str = ""
    email_verified: bool = False
    email_verify_token: Optional[str] = None
    last_login: Optional[str] = None
    login_count: int = 0
    # MFA (optional for now)
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    invited_by: Optional[str] = None   # user_id of inviter
    avatar_url: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None


# ── Password utilities ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=260_000,   # NIST recommended 2024
    )
    return f"pbkdf2:sha256:260000:{salt}:{key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    try:
        parts = password_hash.split(':')
        if len(parts) != 5 or parts[0] != 'pbkdf2':
            return False
        _, algo, iters, salt, stored_key = parts
        key = hashlib.pbkdf2_hmac(
            algo,
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=int(iters),
        )
        return hmac.compare_digest(key.hex(), stored_key)
    except Exception:
        return False


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


# ── Password validation ───────────────────────────────────────────────────────

def validate_password(password: str) -> Optional[str]:
    """
    Returns an error message if the password is too weak, None if it's fine.
    Requirements: 8+ chars, at least one number or symbol.
    Utilities are enterprise customers — we keep requirements reasonable.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if password.lower() == password and not any(c.isdigit() for c in password):
        return "Password must contain at least one number or uppercase letter"
    common = {'password', 'password1', '12345678', 'qwerty123', 'gridiq123'}
    if password.lower() in common:
        return "Password is too common"
    return None


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))
