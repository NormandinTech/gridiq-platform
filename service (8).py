"""
GridIQ SaaS — Auth API Routes
==============================
POST /auth/signup           — create account
POST /auth/verify-email     — verify email token
POST /auth/login            — login, get tokens
POST /auth/refresh          — refresh access token
POST /auth/logout           — invalidate refresh token
POST /auth/forgot-password  — request reset email
POST /auth/reset-password   — complete reset
GET  /auth/me               — get current user
POST /auth/invite           — invite a team member
POST /auth/accept-invite    — accept invitation
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, field_validator

from backend.auth.models import UserRole
from backend.auth.service import auth_service
from backend.auth.tokens import token_service, TokenPayload

logger = logging.getLogger(__name__)
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

REFRESH_COOKIE = "gridiq_refresh"
COOKIE_MAX_AGE = 30 * 24 * 3600   # 30 days


# ── Request / response schemas ────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email:        str
    password:     str
    full_name:    str
    utility_name: str
    phone:        str = ""

class LoginRequest(BaseModel):
    email:    str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str

class InviteRequest(BaseModel):
    email: str
    role:  str = "operator"

class AcceptInviteRequest(BaseModel):
    token:     str
    full_name: str
    password:  str

class VerifyEmailRequest(BaseModel):
    token: str


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/api/v1/auth",
    )

def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


# ── Dependency: get current user from Bearer token ────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenPayload:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = token_service.verify(credentials.credentials, expected_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def require_role(*roles: UserRole):
    """Factory for role-based access control."""
    async def _check(current: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if current.role not in [r.value for r in roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current
    return _check


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_router.post("/signup")
async def signup(req: SignupRequest, response: Response):
    result = auth_service.signup(
        email=req.email,
        password=req.password,
        full_name=req.full_name,
        utility_name=req.utility_name,
        phone=req.phone,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {
        "message": result.message,
        "user_id": result.user.user_id,
        "tenant_id": result.tenant.tenant_id,
    }


@auth_router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, response: Response):
    result = auth_service.verify_email(req.token)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    if result.refresh_token:
        _set_refresh_cookie(response, result.refresh_token)
    return {
        "message": result.message,
        "access_token": result.access_token,
        "token_type": "bearer",
        "user": _user_dict(result.user),
        "tenant": _tenant_dict(result.tenant),
    }


@auth_router.post("/login")
async def login(req: LoginRequest, response: Response):
    result = auth_service.login(req.email, req.password)
    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)
    _set_refresh_cookie(response, result.refresh_token)
    return {
        "access_token": result.access_token,
        "token_type":   "bearer",
        "user":         _user_dict(result.user),
        "tenant":       _tenant_dict(result.tenant),
    }


@auth_router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None, alias=REFRESH_COOKIE),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    result = token_service.refresh(refresh_token)
    if not result:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    new_access, new_refresh = result
    _set_refresh_cookie(response, new_refresh)
    return {"access_token": new_access, "token_type": "bearer"}


@auth_router.post("/logout")
async def logout(response: Response):
    _clear_refresh_cookie(response)
    return {"message": "Logged out"}


@auth_router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    result = auth_service.request_password_reset(req.email)
    return {"message": result.message}


@auth_router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    result = auth_service.reset_password(req.token, req.new_password)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {"message": result.message}


@auth_router.get("/me")
async def get_me(current: TokenPayload = Depends(get_current_user)):
    user   = auth_service.get_user(current.user_id)
    tenant = auth_service.get_tenant(current.tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user":   _user_dict(user),
        "tenant": _tenant_dict(tenant),
    }


@auth_router.post("/invite")
async def invite_user(
    req: InviteRequest,
    current: TokenPayload = Depends(get_current_user),
):
    # Only owners and admins can invite
    if current.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only account owners and admins can invite users")
    result = auth_service.invite_user(
        tenant_id=current.tenant_id,
        inviter_id=current.user_id,
        invitee_email=req.email,
        role=req.role,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {"message": result.message}


@auth_router.post("/accept-invite")
async def accept_invite(req: AcceptInviteRequest, response: Response):
    result = auth_service.accept_invite(req.token, req.full_name, req.password)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    _set_refresh_cookie(response, result.refresh_token)
    return {
        "access_token": result.access_token,
        "token_type":   "bearer",
        "user":         _user_dict(result.user),
        "tenant":       _tenant_dict(result.tenant),
    }


@auth_router.get("/team")
async def get_team(current: TokenPayload = Depends(get_current_user)):
    users = auth_service.get_tenant_users(current.tenant_id)
    return {"users": [_user_dict(u) for u in users]}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_dict(user) -> dict:
    if not user: return {}
    return {
        "user_id":        user.user_id,
        "email":          user.email,
        "full_name":      user.full_name,
        "role":           user.role.value,
        "status":         user.status.value,
        "email_verified": user.email_verified,
        "last_login":     user.last_login,
        "job_title":      user.job_title,
        "avatar_url":     user.avatar_url,
        "created_at":     user.created_at,
    }

def _tenant_dict(tenant) -> dict:
    if not tenant: return {}
    return {
        "tenant_id":           tenant.tenant_id,
        "name":                tenant.name,
        "slug":                tenant.slug,
        "status":              tenant.status.value,
        "plan":                tenant.plan.value,
        "plan_asset_limit":    tenant.plan_asset_limit,
        "current_asset_count": tenant.current_asset_count,
        "scada_connected":     tenant.scada_connected,
        "onboarding_step":     tenant.onboarding_step,
        "onboarding_complete": tenant.onboarding_complete,
        "pilot_start_date":    tenant.pilot_start_date,
        "pilot_end_date":      tenant.pilot_end_date,
        "created_at":          tenant.created_at,
    }
