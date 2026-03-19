"""
GridIQ SaaS — Stripe Billing Service
======================================
Handles subscriptions, payment collection, and plan enforcement.

Stripe products map to GridIQ plans:
  pilot        — $10,000 one-time
  starter      — $48,000/yr ($4,000/mo)
  professional — $240,000/yr ($20,000/mo)
  enterprise   — custom (contact sales)

Flow:
  1. Tenant completes onboarding
  2. We create a Stripe Checkout session
  3. Utility enters card details on Stripe's hosted page
  4. Stripe sends webhook → we activate subscription
  5. Monthly/annual auto-billing handled by Stripe
  6. Failed payment → webhook → we downgrade to past_due
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.auth.models import PlanTier, TenantStatus
from backend.auth.service import auth_service

logger = logging.getLogger(__name__)

# ── Stripe price IDs (set these in your Stripe dashboard) ────────────────────
# In production: set these as environment variables
STRIPE_PRICES = {
    PlanTier.PILOT:        os.getenv("STRIPE_PRICE_PILOT",        "price_pilot_10000"),
    PlanTier.STARTER:      os.getenv("STRIPE_PRICE_STARTER",      "price_starter_annual"),
    PlanTier.PROFESSIONAL: os.getenv("STRIPE_PRICE_PROFESSIONAL", "price_pro_annual"),
}

PLAN_LIMITS = {
    PlanTier.PILOT:        500,
    PlanTier.STARTER:      500,
    PlanTier.PROFESSIONAL: 5000,
    PlanTier.ENTERPRISE:   999999,
}


@dataclass
class CheckoutSession:
    session_id:  str
    checkout_url: str
    tenant_id:   str
    plan:        str


class BillingService:

    def __init__(self):
        self._stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
        self._webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self._stripe = None
        if self._stripe_key and self._stripe_key.startswith("sk_"):
            try:
                import stripe
                stripe.api_key = self._stripe_key
                self._stripe = stripe
                logger.info("[Billing] Stripe initialized")
            except ImportError:
                logger.warning("[Billing] stripe library not installed — billing in mock mode")
        else:
            logger.info("[Billing] No Stripe key — running in mock mode")

    def create_checkout_session(
        self,
        tenant_id: str,
        plan: PlanTier,
        success_url: str,
        cancel_url: str,
    ) -> Optional[CheckoutSession]:
        """
        Create a Stripe Checkout session for a tenant to enter payment details.
        Returns the URL to redirect the utility to.
        """
        tenant = auth_service.get_tenant(tenant_id)
        if not tenant:
            logger.error(f"[Billing] Tenant {tenant_id} not found")
            return None

        if not self._stripe:
            # Mock mode — return a fake session
            logger.info(f"[Billing] MOCK checkout session for {tenant.name} → {plan.value}")
            return CheckoutSession(
                session_id=f"cs_mock_{tenant_id[:8]}",
                checkout_url=f"{success_url}?session_id=mock&plan={plan.value}",
                tenant_id=tenant_id,
                plan=plan.value,
            )

        try:
            # Create or get Stripe customer
            if not tenant.stripe_customer_id:
                customer = self._stripe.Customer.create(
                    email=tenant.primary_email,
                    name=tenant.name,
                    metadata={"tenant_id": tenant_id, "gridiq_plan": plan.value},
                )
                tenant.stripe_customer_id = customer.id

            price_id = STRIPE_PRICES.get(plan)
            if not price_id:
                logger.error(f"[Billing] No price ID for plan {plan}")
                return None

            mode = "payment" if plan == PlanTier.PILOT else "subscription"

            session = self._stripe.checkout.Session.create(
                customer=tenant.stripe_customer_id,
                payment_method_types=["card", "us_bank_account"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode=mode,
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                metadata={"tenant_id": tenant_id, "plan": plan.value},
                invoice_creation={"enabled": True} if mode == "payment" else None,
            )

            logger.info(f"[Billing] Checkout session created: {session.id} for {tenant.name}")
            return CheckoutSession(
                session_id=session.id,
                checkout_url=session.url,
                tenant_id=tenant_id,
                plan=plan.value,
            )

        except Exception as exc:
            logger.error(f"[Billing] Checkout session failed: {exc}")
            return None

    def handle_webhook(self, payload: bytes, sig_header: str) -> Dict:
        """
        Process Stripe webhook events.
        Called by the webhook endpoint — validates signature then processes.
        """
        if not self._stripe:
            logger.info("[Billing] MOCK webhook received")
            return {"status": "mock"}

        try:
            event = self._stripe.Webhook.construct_event(
                payload, sig_header, self._webhook_secret
            )
        except Exception as exc:
            logger.error(f"[Billing] Webhook signature failed: {exc}")
            return {"error": "invalid signature"}

        event_type = event["type"]
        data = event["data"]["object"]

        logger.info(f"[Billing] Webhook: {event_type}")

        if event_type == "checkout.session.completed":
            self._on_checkout_complete(data)

        elif event_type in ("invoice.payment_succeeded", "invoice.paid"):
            self._on_payment_succeeded(data)

        elif event_type == "invoice.payment_failed":
            self._on_payment_failed(data)

        elif event_type == "customer.subscription.deleted":
            self._on_subscription_cancelled(data)

        elif event_type == "customer.subscription.updated":
            self._on_subscription_updated(data)

        return {"received": True}

    def get_portal_url(self, tenant_id: str, return_url: str) -> Optional[str]:
        """
        Get a Stripe Customer Portal URL so the tenant can manage their
        subscription, update payment method, download invoices.
        """
        tenant = auth_service.get_tenant(tenant_id)
        if not tenant or not tenant.stripe_customer_id:
            return None

        if not self._stripe:
            return f"{return_url}?portal=mock"

        try:
            session = self._stripe.billing_portal.Session.create(
                customer=tenant.stripe_customer_id,
                return_url=return_url,
            )
            return session.url
        except Exception as exc:
            logger.error(f"[Billing] Portal URL failed: {exc}")
            return None

    def get_subscription_status(self, tenant_id: str) -> Dict:
        """Get current subscription details for a tenant."""
        tenant = auth_service.get_tenant(tenant_id)
        if not tenant:
            return {"error": "Tenant not found"}

        return {
            "tenant_id":            tenant_id,
            "plan":                 tenant.plan.value,
            "status":               tenant.status.value,
            "asset_limit":          PLAN_LIMITS.get(tenant.plan, 500),
            "current_asset_count":  tenant.current_asset_count,
            "stripe_customer_id":   tenant.stripe_customer_id,
            "subscription_start":   tenant.subscription_start,
            "subscription_end":     tenant.subscription_end,
            "pilot_start_date":     tenant.pilot_start_date,
            "pilot_end_date":       tenant.pilot_end_date,
        }

    # ── Webhook handlers ──────────────────────────────────────────────────────

    def _on_checkout_complete(self, data: Dict) -> None:
        tenant_id = data.get("metadata", {}).get("tenant_id")
        plan_str  = data.get("metadata", {}).get("plan", "pilot")
        if not tenant_id:
            return

        tenant = auth_service.get_tenant(tenant_id)
        if not tenant:
            return

        plan = PlanTier(plan_str)
        tenant.plan = plan
        tenant.status = TenantStatus.PILOT if plan == PlanTier.PILOT else TenantStatus.ACTIVE
        tenant.plan_asset_limit = PLAN_LIMITS.get(plan, 500)
        tenant.stripe_subscription_id = data.get("subscription")
        tenant.subscription_start = datetime.now(timezone.utc).isoformat()

        if plan == PlanTier.PILOT:
            from datetime import timedelta
            start = datetime.now(timezone.utc)
            tenant.pilot_start_date = start.isoformat()
            tenant.pilot_end_date   = (start + timedelta(days=90)).isoformat()

        logger.info(f"[Billing] Checkout complete: {tenant.name} → {plan.value}")

    def _on_payment_succeeded(self, data: Dict) -> None:
        customer_id = data.get("customer")
        tenant = self._tenant_by_customer(customer_id)
        if not tenant:
            return
        if tenant.status == TenantStatus.PAST_DUE:
            tenant.status = TenantStatus.ACTIVE
        logger.info(f"[Billing] Payment succeeded: {tenant.name}")

    def _on_payment_failed(self, data: Dict) -> None:
        customer_id = data.get("customer")
        tenant = self._tenant_by_customer(customer_id)
        if not tenant:
            return
        tenant.status = TenantStatus.PAST_DUE
        logger.warning(f"[Billing] Payment FAILED: {tenant.name} — status → past_due")

    def _on_subscription_cancelled(self, data: Dict) -> None:
        customer_id = data.get("customer")
        tenant = self._tenant_by_customer(customer_id)
        if not tenant:
            return
        tenant.status = TenantStatus.CANCELLED
        logger.info(f"[Billing] Subscription cancelled: {tenant.name}")

    def _on_subscription_updated(self, data: Dict) -> None:
        customer_id = data.get("customer")
        tenant = self._tenant_by_customer(customer_id)
        if not tenant:
            return
        # Could check for plan upgrades here
        logger.info(f"[Billing] Subscription updated: {tenant.name if tenant else customer_id}")

    def _tenant_by_customer(self, customer_id: str):
        from backend.auth.service import _tenants
        return next(
            (t for t in _tenants.values() if t.stripe_customer_id == customer_id),
            None,
        )

    def mock_activate_pilot(self, tenant_id: str) -> bool:
        """
        Dev/demo helper: instantly activate a pilot without going through Stripe.
        Use this during development and for demo accounts.
        """
        tenant = auth_service.get_tenant(tenant_id)
        if not tenant:
            return False
        from datetime import timedelta
        start = datetime.now(timezone.utc)
        tenant.plan             = PlanTier.PILOT
        tenant.status           = TenantStatus.PILOT
        tenant.plan_asset_limit = 500
        tenant.pilot_start_date = start.isoformat()
        tenant.pilot_end_date   = (start + timedelta(days=90)).isoformat()
        logger.info(f"[Billing] MOCK pilot activated: {tenant.name}")
        return True


# ── Singleton ─────────────────────────────────────────────────────────────────
billing_service = BillingService()
