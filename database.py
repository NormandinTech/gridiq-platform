"""
GridIQ SaaS — Billing API Routes
==================================
POST /billing/checkout          — create Stripe checkout session
POST /billing/webhook           — Stripe webhook handler
GET  /billing/portal            — Stripe customer portal URL
GET  /billing/subscription      — current plan + status
POST /billing/mock-activate     — dev mode: activate pilot without Stripe
"""
from __future__ import annotations

import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.auth.models import PlanTier
from backend.auth.routes import get_current_user, TokenPayload
from backend.billing.service import billing_service

logger = logging.getLogger(__name__)
billing_router = APIRouter(prefix="/billing", tags=["Billing"])


class CheckoutRequest(BaseModel):
    plan: str = "pilot"   # pilot | starter | professional


@billing_router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    current: TokenPayload = Depends(get_current_user),
):
    """Create a Stripe Checkout session. Returns redirect URL."""
    if current.role not in ("owner",):
        raise HTTPException(status_code=403, detail="Only the account owner can manage billing")

    try:
        plan = PlanTier(req.plan)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {req.plan}")

    base_url = os.getenv("APP_BASE_URL", "https://gridiq.io")
    session = billing_service.create_checkout_session(
        tenant_id=current.tenant_id,
        plan=plan,
        success_url=f"{base_url}/dashboard?payment=success",
        cancel_url=f"{base_url}/onboarding/payment?cancelled=true",
    )

    if not session:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return {
        "checkout_url": session.checkout_url,
        "session_id":   session.session_id,
    }


@billing_router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe sends events here when payments succeed/fail/subscriptions change.
    This endpoint MUST be publicly accessible (no auth).
    """
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    result = billing_service.handle_webhook(payload, sig_header)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@billing_router.get("/portal")
async def get_billing_portal(current: TokenPayload = Depends(get_current_user)):
    """Get URL to Stripe Customer Portal (manage subscription, invoices, payment method)."""
    if current.role not in ("owner",):
        raise HTTPException(status_code=403, detail="Only the account owner can access billing")

    base_url = os.getenv("APP_BASE_URL", "https://gridiq.io")
    url = billing_service.get_portal_url(
        current.tenant_id,
        return_url=f"{base_url}/settings/billing",
    )
    if not url:
        raise HTTPException(status_code=404, detail="No billing account found. Complete checkout first.")

    return {"portal_url": url}


@billing_router.get("/subscription")
async def get_subscription(current: TokenPayload = Depends(get_current_user)):
    """Get current subscription status and plan details."""
    return billing_service.get_subscription_status(current.tenant_id)


@billing_router.post("/mock-activate")
async def mock_activate_pilot(current: TokenPayload = Depends(get_current_user)):
    """DEV ONLY: Activate pilot without going through Stripe."""
    if os.getenv("APP_ENV") == "production":
        raise HTTPException(status_code=404, detail="Not found")
    success = billing_service.mock_activate_pilot(current.tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"message": "Pilot activated (mock)", "tenant_id": current.tenant_id}
