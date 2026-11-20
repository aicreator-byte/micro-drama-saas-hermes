"""Billing langganan — MODE TEST/SANDBOX SAJA.

Di tidak punya kartu kredit: provider di sini HANYA `test` (simulasi
lokal, tanpa panggilan ke Stripe, tanpa live key). Bila suatu saat ada
`STRIPE_SECRET_KEY` live di env, provider test MENOLAK menggunakannya —
integrasi live sengaja tidak diimplementasikan di kaki ini.

Paket (harga IDR/bulan, test only):
  free    Rp0      — 1 proyek, auto-generate 5 episode
  pro     Rp99.000 — proyek tanpa batas, auto-generate 30 episode
  studio  Rp249.000 — semua pro + timeline + subtitle prioritas
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "id": "free", "name": "Free", "price_idr": 0,
        "max_projects": 1, "max_episodes_per_job": 5,
        "features": ["1 proyek", "Auto-generate 5 episode/job"],
    },
    "pro": {
        "id": "pro", "name": "Pro", "price_idr": 99000,
        "max_projects": None, "max_episodes_per_job": 30,
        "features": ["Proyek tanpa batas", "Auto-generate 30 episode/job", "Timeline video"],
    },
    "studio": {
        "id": "studio", "name": "Studio", "price_idr": 249000,
        "max_projects": None, "max_episodes_per_job": 50,
        "features": ["Semua Pro", "Subtitle prioritas", "Cek konsistensi karakter"],
    },
}

# Secret HMAC untuk webhook test — WAJIB dari env
# BILLING_TEST_WEBHOOK_SECRET, tanpa default hardcoded (audit ronde 2,
# P2-1: default lama yang ter-commit di repo bisa dipakai siapa pun
# untuk menandatangani webhook palsu). Bila env tidak di-set, dipakai
# secret acak per proses (webhook dari proses lain tidak valid) + warning
# di log — set env untuk secret yang stabil antar restart.
# BUKAN live Stripe webhook secret; tidak pernah dicetak.
_TEST_WEBHOOK_SECRET_ENV = os.getenv("BILLING_TEST_WEBHOOK_SECRET")
if _TEST_WEBHOOK_SECRET_ENV:
    TEST_WEBHOOK_SECRET = _TEST_WEBHOOK_SECRET_ENV
else:
    TEST_WEBHOOK_SECRET = secrets.token_hex(32)
    logger.warning(
        "BILLING_TEST_WEBHOOK_SECRET tidak di-set — memakai secret webhook "
        "test acak per proses. Set env untuk secret yang stabil antar restart."
    )


class BillingError(Exception):
    pass


def list_plans() -> list[dict[str, Any]]:
    return [dict(p) for p in PLANS.values()]


def get_plan(plan_id: str) -> dict[str, Any]:
    plan = PLANS.get(plan_id)
    if plan is None:
        raise BillingError(f"Unknown plan: {plan_id}")
    return dict(plan)


class TestBillingProvider:
    """Provider simulasi. Checkout mengembalikan URL palsu bertanda test;
    tidak ada kartu, tidak ada charge nyata, tidak ada panggilan keluar."""

    name = "test"

    def create_checkout_session(self, *, user_id: uuid.UUID, plan_id: str) -> dict[str, Any]:
        plan = get_plan(plan_id)
        if plan["price_idr"] == 0:
            raise BillingError("Plan free tidak butuh checkout — aktifkan langsung")
        session_id = f"cs_test_{uuid.uuid4().hex[:24]}"
        return {
            "session_id": session_id,
            "checkout_url": f"https://checkout.test/billing/{session_id}?plan={plan_id}",
            "plan": plan,
            "mode": "test",
            "note": "TEST MODE — tidak ada pembayaran nyata",
        }

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """HMAC-SHA256 sederhana atas payload dengan secret test."""
        expected = hmac.new(
            TEST_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def sign_test_payload(self, payload: bytes) -> str:
        return hmac.new(
            TEST_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()


def next_period_end(days: int = 30) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)


def apply_webhook_event(event_type: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Petakan event webhook test ke perubahan status langganan.
    Kembalikan dict perubahan atau None bila event tidak dikenal/diabaikan."""
    mapping = {
        "checkout.session.completed": {"status": "active"},
        "customer.subscription.created": {"status": "active"},
        "customer.subscription.updated": {"status": "active"},
        "invoice.payment_failed": {"status": "past_due"},
        "customer.subscription.deleted": {"status": "canceled"},
    }
    change = mapping.get(event_type)
    if change is None:
        return None
    out = dict(change)
    if event_type in ("checkout.session.completed", "customer.subscription.created"):
        out["current_period_end"] = next_period_end()
    return out


def serialize_subscription(sub) -> dict[str, Any]:
    return {
        "id": str(sub.id),
        "user_id": str(sub.user_id),
        "plan": sub.plan,
        "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status),
        "provider": sub.provider,
        "provider_customer_id": sub.provider_customer_id,
        "provider_subscription_id": sub.provider_subscription_id,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }
