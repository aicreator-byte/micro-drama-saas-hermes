"""Billing API — TEST MODE SAJA (lihat app/services/billing.py).

Tidak ada live key, tidak ada charge nyata, tidak ada panggilan ke Stripe.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Subscription, SubscriptionStatus, BillingEvent
from app.schemas import (
    BillingPlanResponse, SubscriptionResponse, CheckoutCreate,
    CheckoutResponse, WebhookEventIn,
)
from app.services.billing import (
    list_plans, get_plan, TestBillingProvider, BillingError,
    apply_webhook_event, serialize_subscription,
)

router = APIRouter(prefix="/billing", tags=["billing"])
_provider = TestBillingProvider()


async def _get_or_create_subscription(db: AsyncSession, user: User) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(
            user_id=user.id, plan="free",
            status=SubscriptionStatus.INACTIVE, provider="test",
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
    return sub


async def _log_event(db: AsyncSession, user: User, event_type: str, payload: dict) -> None:
    db.add(BillingEvent(user_id=user.id, event_type=event_type, payload=payload))
    await db.commit()


@router.get("/plans", response_model=list[BillingPlanResponse])
async def get_plans():
    return list_plans()


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sub = await _get_or_create_subscription(db, current_user)
    return SubscriptionResponse(
        id=sub.id, user_id=sub.user_id, plan=sub.plan,
        status=sub.status.value, provider=sub.provider,
        provider_customer_id=sub.provider_customer_id,
        provider_subscription_id=sub.provider_subscription_id,
        current_period_end=sub.current_period_end,
        created_at=sub.created_at, updated_at=sub.updated_at,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        plan = get_plan(data.plan)
    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if plan["price_idr"] == 0:
        # Free: aktifkan langsung, tanpa checkout.
        sub = await _get_or_create_subscription(db, current_user)
        sub.plan = "free"
        sub.status = SubscriptionStatus.ACTIVE
        sub.provider = "test"
        await db.commit()
        await _log_event(db, current_user, "plan.activated.free", {"plan": "free"})
        return CheckoutResponse(
            session_id="free_no_checkout", checkout_url="",
            plan=BillingPlanResponse(**plan), mode="test",
            note="Plan Free aktif langsung — tidak ada checkout.",
        )
    try:
        session = _provider.create_checkout_session(user_id=current_user.id, plan_id=data.plan)
    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sub = await _get_or_create_subscription(db, current_user)
    sub.plan = data.plan
    sub.provider_subscription_id = session["session_id"]
    sub.provider_customer_id = f"cus_test_{current_user.id.hex[:12]}"
    await db.commit()
    await _log_event(db, current_user, "checkout.session.created", {
        "plan": data.plan, "session_id": session["session_id"], "mode": "test",
    })
    return CheckoutResponse(
        session_id=session["session_id"],
        checkout_url=session["checkout_url"],
        plan=BillingPlanResponse(**plan),
        mode="test",
        note=session["note"],
    )


@router.post("/webhook")
async def billing_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Webhook test: verifikasi HMAC, lalu terapkan perubahan status.
    Header: X-Test-Signature: <hmac sha256 hex atas body mentah>.
    Event tanpa user (customer id test) diabaikan dengan 200 + received:false."""
    raw = await request.body()
    signature = request.headers.get("X-Test-Signature", "")
    if not _provider.verify_webhook_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        event = WebhookEventIn.model_validate_json(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    change = apply_webhook_event(event.type, event.data)
    if change is None:
        return {"received": True, "applied": False, "reason": f"event {event.type} diabaikan"}
    # Test mode: payload membawa user_id eksplisit (tidak ada customer
    # Stripe nyata). Tanpa user_id, event dicatat diterima tapi tidak diterapkan.
    user = None
    raw_user_id = event.data.get("user_id")
    if raw_user_id:
        try:
            result = await db.execute(select(User).where(User.id == UUID(str(raw_user_id))))
            user = result.scalar_one_or_none()
        except ValueError:
            user = None
    if user is None:
        return {"received": True, "applied": False, "reason": "user_id tidak ada / tidak ditemukan (test)"}
    sub = await _get_or_create_subscription(db, user)
    if "status" in change:
        sub.status = SubscriptionStatus(change["status"])
    if "current_period_end" in change:
        sub.current_period_end = change["current_period_end"]
    await db.commit()
    applied_log = dict(change)
    if "current_period_end" in applied_log:
        applied_log["current_period_end"] = applied_log["current_period_end"].isoformat()
    await _log_event(db, user, f"webhook.{event.type}", {"applied": applied_log})
    return {"received": True, "applied": True, "status": sub.status.value}


@router.post("/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sub = await _get_or_create_subscription(db, current_user)
    sub.status = SubscriptionStatus.CANCELED
    sub.plan = "free"
    await db.commit()
    await _log_event(db, current_user, "subscription.canceled", {"plan": "free"})
    return SubscriptionResponse(
        id=sub.id, user_id=sub.user_id, plan=sub.plan,
        status=sub.status.value, provider=sub.provider,
        provider_customer_id=sub.provider_customer_id,
        provider_subscription_id=sub.provider_subscription_id,
        current_period_end=sub.current_period_end,
        created_at=sub.created_at, updated_at=sub.updated_at,
    )
