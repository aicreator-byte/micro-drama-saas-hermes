"""Future-dev 19 Nov 2026: Settings admin gate, Google redirect URI env,
and .env loading independent of the process CWD.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.config import Settings
from app.core.security import create_access_token, get_password_hash
from app.models import User, UserRole

BACKEND_DIR = Path(__file__).resolve().parent.parent


class TestSettingsAdminOnly:
    @pytest_asyncio.fixture
    async def admin_user(self, db):
        user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("adminpass123"),
            full_name="Admin User",
            is_active=True,
            is_verified=True,
            role=UserRole.ADMIN,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_non_admin_patch_settings_forbidden(self, client: AsyncClient, auth_headers):
        response = await client.patch(
            "/api/v1/settings",
            json={"google_oauth_client_id": ""},
            headers=auth_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_patch_settings_ok(self, client: AsyncClient, admin_user):
        token = create_access_token(data={"sub": str(admin_user.id)})
        response = await client.patch(
            "/api/v1/settings",
            json={"google_oauth_client_id": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["google_oauth_client_id_configured"] is False

    @pytest.mark.asyncio
    async def test_non_admin_get_settings_ok(self, client: AsyncClient, auth_headers):
        # Membaca setting tetap boleh semua user aktif; yang dibatasi
        # hanya MENGUBAH (PATCH).
        response = await client.get("/api/v1/settings", headers=auth_headers)
        assert response.status_code == 200


class TestGoogleRedirectUriEnv:
    def test_default_is_localhost_callback(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_OAUTH_REDIRECT_URI", raising=False)
        assert Settings().GOOGLE_OAUTH_REDIRECT_URI == (
            "http://localhost:3000/dashboard/google-accounts/callback"
        )

    def test_env_override_is_respected(self, monkeypatch):
        monkeypatch.setenv(
            "GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/dashboard/google-accounts/callback")
        assert Settings().GOOGLE_OAUTH_REDIRECT_URI == (
            "https://example.com/dashboard/google-accounts/callback"
        )


class TestDotenvFromWrongCwd:
    def test_key_loaded_when_started_from_tmp(self):
        """Server yang dijalankan dari /tmp tetap membaca .env backend.

        Precondition: backend/.env berisi NVIDIA_API_KEY (key trial).
        Tes ini TIDAK PERNAH mencetak nilai key — hanya boolean.
        Bila key dicabut dari .env, tes ini gagal dan harus diperbarui.
        """
        env = dict(os.environ)
        env.pop("NVIDIA_API_KEY", None)  # satu-satunya sumber: backend/.env
        env["PYTHONPATH"] = str(BACKEND_DIR)
        result = subprocess.run(
            [sys.executable, "-c",
             "from app.core.config import settings; "
             "print(bool(settings.NVIDIA_API_KEY))"],
            cwd="/tmp",
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "True"
