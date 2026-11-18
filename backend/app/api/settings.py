"""Settings API - App-wide configuration management."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import get_current_active_user, get_current_admin_user
from app.models import User, AppSettings
from app.schemas import (
    ProviderConfig, AppSettingsUpdate, AppSettingsResponse,
)
from app.utils.encryption import encrypt_data

router = APIRouter(prefix="/settings", tags=["settings"])

# Env vars whose values may be used as provider API keys. Anything else
# (e.g. SECRET_KEY) must never be sent to a provider base_url.
ALLOWED_API_KEY_ENVS = frozenset({
    "AI_API_KEY",
    "NVIDIA_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "DEEPINFRA_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
})


async def get_or_create_settings(db: AsyncSession) -> AppSettings:
    """Get or create the single AppSettings row."""
    result = await db.execute(select(AppSettings))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = AppSettings()
        db.add(settings)
        # Note: caller must commit
    return settings


@router.get("", response_model=AppSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get app settings (secrets not exposed, only configured flags)."""
    settings = await get_or_create_settings(db)

    # Parse AI providers
    ai_providers = []
    if settings.ai_providers:
        for p in settings.ai_providers:
            ai_providers.append(ProviderConfig(**p))

    # Check if OAuth credentials are configured (without exposing them)
    client_id_configured = bool(settings.google_oauth_client_id_encrypted)
    client_secret_configured = bool(settings.google_oauth_client_secret_encrypted)

    return AppSettingsResponse(
        ai_providers=ai_providers,
        google_oauth_client_id_configured=client_id_configured,
        google_oauth_client_secret_configured=client_secret_configured,
    )


@router.patch("", response_model=AppSettingsResponse)
async def update_settings(
    update: AppSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Update app settings. Only admin users can modify settings
    (AppSettings is a single global row shared by all tenants)."""
    settings = await get_or_create_settings(db)

    if update.ai_providers is not None:
        # Whitelist api_key_env: the stored name is read from the process
        # environment and sent as a Bearer token to the provider base_url,
        # so an arbitrary env-var name would be a secret-exfiltration vector.
        for p in update.ai_providers:
            if p.api_key_env not in ALLOWED_API_KEY_ENVS:
                raise HTTPException(
                    status_code=400,
                    detail=f"api_key_env '{p.api_key_env}' is not allowed",
                )
        # Validate and sort by order
        providers_data = [p.model_dump() for p in update.ai_providers]
        providers_data.sort(key=lambda p: p.get("order", 999))
        settings.ai_providers = providers_data

    if update.google_oauth_client_id is not None:
        if update.google_oauth_client_id.strip():
            settings.google_oauth_client_id_encrypted = encrypt_data({"value": update.google_oauth_client_id.strip()})
        else:
            settings.google_oauth_client_id_encrypted = None

    if update.google_oauth_client_secret is not None:
        if update.google_oauth_client_secret.strip():
            settings.google_oauth_client_secret_encrypted = encrypt_data({"value": update.google_oauth_client_secret.strip()})
        else:
            settings.google_oauth_client_secret_encrypted = None

    await db.commit()
    await db.refresh(settings)

    # Return updated settings (will mask secrets)
    return await get_settings(db, current_user)
