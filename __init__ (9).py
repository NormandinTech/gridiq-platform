"""
GridIQ SaaS — Authentication Service
======================================
Handles the full auth lifecycle:
  - Signup (creates tenant + owner user)
  - Email verification
  - Login / logout
  - Password reset flow
  - User invitation (owner invites colleagues)
  - Session management

In-memory store for dev/pilot — swap for DB in production.
"""
from __future__ import annotations

import logging
import smtplib
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional, Tuple
from uuid import uuid4

from backend.auth.models import (
    PlanTier, Tenant, TenantStatus, User, UserRole, UserStatus,
    generate_token, hash_password, validate_email,
    validate_password, verify_password,
)
from backend.auth.tokens import token_service

logger = logging.getLogger(__name__)


# ── In-memory stores (replace with DB queries in production) ──────────────────

_tenants: Dict[str, Tenant] = {}         # tenant_id → Tenant
_users:   Dict[str, User]   = {}         # user_id   → User
_by_email: Dict[str, str]   = {}         # email     → user_id
_by_slug:  Dict[str, str]   = {}         # slug      → tenant_id
_reset_tokens: Dict[str, Tuple[str, datetime]] = {}  # token → (user_id, expiry)
_invite_tokens: Dict[str, Tuple[str, str, str]] = {} # token → (tenant_id, email, role)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class AuthResult:
    success: bool
    error: Optional[str] = None
    user: Optional[User] = None
    tenant: Optional[Tenant] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    message: Optional[str] = None


# ── Auth Service ──────────────────────────────────────────────────────────────

class AuthService:

    # ── Signup ────────────────────────────────────────────────────────────────

    def signup(self, email: str, password: str, full_name: str,
               utility_name: str, phone: str = "") -> AuthResult:
        """
        Create a new tenant + owner user.
        Sends email verification link.
        """
        email = email.strip().lower()

        # Validate inputs
        if not validate_email(email):
            return AuthResult(success=False, error="Invalid email address")

        pw_error = validate_password(password)
        if pw_error:
            return AuthResult(success=False, error=pw_error)

        if not full_name.strip():
            return AuthResult(success=False, error="Full name is required")

        if not utility_name.strip():
            return AuthResult(success=False, error="Utility name is required")

        if email in _by_email:
            return AuthResult(success=False, error="An account with this email already exists")

        # Create tenant
        slug = self._make_slug(utility_name)
        tenant = Tenant(
            tenant_id=str(uuid4()),
            name=utility_name.strip(),
            slug=slug,
            primary_email=email,
            phone=phone,
            status=TenantStatus.ONBOARDING,
            plan=PlanTier.PILOT,
            plan_asset_limit=500,
        )

        # Create owner user
        verify_token = generate_token(32)
        user = User(
            user_id=str(uuid4()),
            tenant_id=tenant.tenant_id,
            email=email,
            full_name=full_name.strip(),
            role=UserRole.OWNER,
            status=UserStatus.PENDING,
            password_hash=hash_password(password),
            email_verified=False,
            email_verify_token=verify_token,
        )

        # Store
        _tenants[tenant.tenant_id] = tenant
        _users[user.user_id]       = user
        _by_email[email]           = user.user_id
        _by_slug[slug]             = tenant.tenant_id

        # Send verification email (non-blocking)
        self._send_verification_email(email, full_name, verify_token)

        logger.info(f"[Auth] New signup: {email} → tenant {tenant.tenant_id}")

        return AuthResult(
            success=True,
            user=user,
            tenant=tenant,
            message="Account created. Please check your email to verify your address.",
        )

    # ── Email verification ────────────────────────────────────────────────────

    def verify_email(self, token: str) -> AuthResult:
        """Verify email address from the link in the verification email."""
        user = next(
            (u for u in _users.values() if u.email_verify_token == token),
            None,
        )
        if not user:
            return AuthResult(success=False, error="Invalid or expired verification link")

        user.email_verified   = True
        user.email_verify_token = None
        user.status           = UserStatus.ACTIVE
        user.updated_at       = datetime.now(timezone.utc).isoformat()

        logger.info(f"[Auth] Email verified: {user.email}")

        # Issue tokens so they're logged in immediately after verifying
        access_token  = token_service.issue_access_token(
            user.user_id, user.tenant_id, user.email, user.role.value
        )
        refresh_token = token_service.issue_refresh_token(
            user.user_id, user.tenant_id, user.email, user.role.value
        )

        return AuthResult(
            success=True,
            user=user,
            tenant=_tenants.get(user.tenant_id),
            access_token=access_token,
            refresh_token=refresh_token,
            message="Email verified. Welcome to GridIQ.",
        )

    # ── Login ─────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> AuthResult:
        """
        Authenticate a user.
        Returns JWT access + refresh tokens on success.
        """
        email = email.strip().lower()

        user_id = _by_email.get(email)
        if not user_id:
            # Timing-safe: still run hash comparison to prevent timing attacks
            hash_password("dummy-timing-safe")
            return AuthResult(success=False, error="Invalid email or password")

        user = _users.get(user_id)
        if not user:
            return AuthResult(success=False, error="Invalid email or password")

        if not verify_password(password, user.password_hash):
            return AuthResult(success=False, error="Invalid email or password")

        if user.status == UserStatus.PENDING:
            return AuthResult(
                success=False,
                error="Please verify your email address before logging in. Check your inbox.",
            )

        if user.status == UserStatus.SUSPENDED:
            return AuthResult(success=False, error="This account has been suspended. Contact support.")

        if user.status == UserStatus.DELETED:
            return AuthResult(success=False, error="Invalid email or password")

        tenant = _tenants.get(user.tenant_id)
        if tenant and tenant.status == TenantStatus.CANCELLED:
            return AuthResult(success=False, error="This account has been cancelled.")

        # Update last login
        user.last_login  = datetime.now(timezone.utc).isoformat()
        user.login_count += 1

        # Issue tokens
        access_token  = token_service.issue_access_token(
            user.user_id, user.tenant_id, user.email, user.role.value
        )
        refresh_token = token_service.issue_refresh_token(
            user.user_id, user.tenant_id, user.email, user.role.value
        )

        logger.info(f"[Auth] Login: {email} (tenant {user.tenant_id})")

        return AuthResult(
            success=True,
            user=user,
            tenant=tenant,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    # ── Password reset ────────────────────────────────────────────────────────

    def request_password_reset(self, email: str) -> AuthResult:
        """
        Send a password reset email.
        Always returns success (don't reveal if email exists).
        """
        email = email.strip().lower()
        user_id = _by_email.get(email)

        if user_id:
            token  = generate_token(32)
            expiry = datetime.now(timezone.utc) + timedelta(hours=2)
            _reset_tokens[token] = (user_id, expiry)
            user = _users[user_id]
            self._send_password_reset_email(email, user.full_name, token)
            logger.info(f"[Auth] Password reset requested: {email}")

        return AuthResult(
            success=True,
            message="If an account exists with that email, a reset link has been sent.",
        )

    def reset_password(self, token: str, new_password: str) -> AuthResult:
        """Complete a password reset using the token from the email."""
        entry = _reset_tokens.get(token)
        if not entry:
            return AuthResult(success=False, error="Invalid or expired reset link")

        user_id, expiry = entry
        if datetime.now(timezone.utc) > expiry:
            del _reset_tokens[token]
            return AuthResult(success=False, error="This reset link has expired. Request a new one.")

        pw_error = validate_password(new_password)
        if pw_error:
            return AuthResult(success=False, error=pw_error)

        user = _users.get(user_id)
        if not user:
            return AuthResult(success=False, error="Invalid reset link")

        user.password_hash = hash_password(new_password)
        user.updated_at    = datetime.now(timezone.utc).isoformat()
        del _reset_tokens[token]

        logger.info(f"[Auth] Password reset completed: {user.email}")
        return AuthResult(success=True, message="Password updated. You can now log in.")

    # ── Invite team members ───────────────────────────────────────────────────

    def invite_user(self, tenant_id: str, inviter_id: str,
                    invitee_email: str, role: str = "operator") -> AuthResult:
        """Invite a colleague to join the tenant's GridIQ account."""
        invitee_email = invitee_email.strip().lower()

        if not validate_email(invitee_email):
            return AuthResult(success=False, error="Invalid email address")

        tenant = _tenants.get(tenant_id)
        if not tenant:
            return AuthResult(success=False, error="Tenant not found")

        if invitee_email in _by_email:
            return AuthResult(success=False, error="A user with this email already exists")

        token = generate_token(32)
        _invite_tokens[token] = (tenant_id, invitee_email, role)
        inviter = _users.get(inviter_id)
        self._send_invite_email(
            invitee_email, tenant.name,
            inviter.full_name if inviter else "Your colleague",
            token,
        )

        logger.info(f"[Auth] Invite sent: {invitee_email} → tenant {tenant_id}")
        return AuthResult(success=True, message=f"Invitation sent to {invitee_email}")

    def accept_invite(self, token: str, full_name: str, password: str) -> AuthResult:
        """Accept an invitation and create a user account."""
        entry = _invite_tokens.get(token)
        if not entry:
            return AuthResult(success=False, error="Invalid or expired invitation link")

        tenant_id, email, role = entry

        pw_error = validate_password(password)
        if pw_error:
            return AuthResult(success=False, error=pw_error)

        user = User(
            user_id=str(uuid4()),
            tenant_id=tenant_id,
            email=email,
            full_name=full_name.strip(),
            role=UserRole(role),
            status=UserStatus.ACTIVE,
            password_hash=hash_password(password),
            email_verified=True,
        )
        _users[user.user_id] = user
        _by_email[email]     = user.user_id
        del _invite_tokens[token]

        access_token  = token_service.issue_access_token(
            user.user_id, tenant_id, email, role
        )
        refresh_token = token_service.issue_refresh_token(
            user.user_id, tenant_id, email, role
        )

        logger.info(f"[Auth] Invite accepted: {email}")
        return AuthResult(
            success=True, user=user,
            tenant=_tenants.get(tenant_id),
            access_token=access_token,
            refresh_token=refresh_token,
        )

    # ── Getters ───────────────────────────────────────────────────────────────

    def get_user(self, user_id: str) -> Optional[User]:
        return _users.get(user_id)

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return _tenants.get(tenant_id)

    def get_tenant_users(self, tenant_id: str) -> list[User]:
        return [u for u in _users.values() if u.tenant_id == tenant_id]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_slug(self, name: str) -> str:
        import re
        base = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')[:40]
        slug = base
        counter = 1
        while slug in _by_slug:
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def _send_verification_email(self, email: str, name: str, token: str) -> None:
        base_url = os.getenv("APP_BASE_URL", "https://gridiq.io")
        link = f"{base_url}/verify-email?token={token}"
        subject = "Verify your GridIQ email address"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
          <div style="background: #0B1D35; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">GridIQ</h1>
          </div>
          <div style="background: white; padding: 32px; border: 1px solid #E2E8F0; border-top: none; border-radius: 0 0 12px 12px;">
            <h2 style="color: #0B1D35; margin-top: 0;">Welcome, {name}!</h2>
            <p style="color: #475569; line-height: 1.6;">Thanks for signing up for GridIQ. Please verify your email address to activate your account.</p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="{link}" style="background: #0B1D35; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">Verify email address</a>
            </div>
            <p style="color: #94A3B8; font-size: 13px;">This link expires in 24 hours. If you didn't sign up for GridIQ, you can ignore this email.</p>
          </div>
        </div>
        """
        self._send_email(email, subject, html)

    def _send_password_reset_email(self, email: str, name: str, token: str) -> None:
        base_url = os.getenv("APP_BASE_URL", "https://gridiq.io")
        link = f"{base_url}/reset-password?token={token}"
        subject = "Reset your GridIQ password"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
          <div style="background: #0B1D35; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">GridIQ</h1>
          </div>
          <div style="background: white; padding: 32px; border: 1px solid #E2E8F0; border-top: none; border-radius: 0 0 12px 12px;">
            <h2 style="color: #0B1D35; margin-top: 0;">Reset your password</h2>
            <p style="color: #475569; line-height: 1.6;">Hi {name}, we received a request to reset your GridIQ password.</p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="{link}" style="background: #1659C5; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">Reset password</a>
            </div>
            <p style="color: #94A3B8; font-size: 13px;">This link expires in 2 hours. If you didn't request a password reset, you can ignore this email.</p>
          </div>
        </div>
        """
        self._send_email(email, subject, html)

    def _send_invite_email(self, email: str, utility_name: str,
                           inviter_name: str, token: str) -> None:
        base_url = os.getenv("APP_BASE_URL", "https://gridiq.io")
        link = f"{base_url}/accept-invite?token={token}"
        subject = f"{inviter_name} invited you to {utility_name} on GridIQ"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
          <div style="background: #0B1D35; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">GridIQ</h1>
          </div>
          <div style="background: white; padding: 32px; border: 1px solid #E2E8F0; border-top: none; border-radius: 0 0 12px 12px;">
            <h2 style="color: #0B1D35; margin-top: 0;">You've been invited</h2>
            <p style="color: #475569; line-height: 1.6;"><strong>{inviter_name}</strong> has invited you to join <strong>{utility_name}</strong>'s GridIQ account — the AI-driven grid intelligence platform.</p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="{link}" style="background: #0B1D35; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">Accept invitation</a>
            </div>
            <p style="color: #94A3B8; font-size: 13px;">This invitation expires in 7 days.</p>
          </div>
        </div>
        """
        self._send_email(email, subject, html)

    def _send_email(self, to: str, subject: str, html: str) -> None:
        """Send email via SMTP. Falls back to logging in dev mode."""
        smtp_host = os.getenv("SMTP_HOST")
        smtp_user = os.getenv("SMTP_USERNAME")
        smtp_pass = os.getenv("SMTP_PASSWORD")
        from_addr = os.getenv("FROM_EMAIL", "noreply@gridiq.io")

        if not smtp_host:
            logger.info(f"[Email] DEV MODE — would send to {to}: {subject}")
            return

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From']    = f"GridIQ <{from_addr}>"
            msg['To']      = to
            msg.attach(MIMEText(html, 'html'))

            with smtplib.SMTP_SSL(smtp_host, 465) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_addr, to, msg.as_string())
            logger.info(f"[Email] Sent to {to}: {subject}")
        except Exception as exc:
            logger.error(f"[Email] Failed to send to {to}: {exc}")


# ── Singleton ─────────────────────────────────────────────────────────────────
auth_service = AuthService()
