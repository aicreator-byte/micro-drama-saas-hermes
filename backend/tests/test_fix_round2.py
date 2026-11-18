"""Regression tests for the post-round-2 audit fixes (Hermes leg).

Covers: 7th character accepted, /prompts/generate reachable, generate-all,
asset_metadata round-trip, admin-gated PATCH /settings + api_key_env
whitelist, removed duplicate /settings/google/* OAuth routes, Google
password via JSON body only, snapshot-before-regenerate, empty premise
rejected, import-results JSON-body contract + file-existence check.
"""
import json
import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.models import (
    User, UserRole, Episode, EpisodeRevision, Scene, GoogleAccount,
    FlowTask,
)


@pytest_asyncio.fixture
async def admin_user(db):
    """An ADMIN user (first-user bootstrap is API-level; fixtures insert directly)."""
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword123"),
        full_name="Admin User",
        is_active=True,
        is_verified=True,
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_headers(admin_user):
    token = create_access_token(data={"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_episode(db, test_project):
    episode = Episode(
        project_id=test_project.id,
        episode_number=1,
        title="Pilot",
        outline="Intro outline",
    )
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    return episode


@pytest_asyncio.fixture
async def test_scene(db, test_episode):
    scene = Scene(
        episode_id=test_episode.id,
        scene_number=1,
        title="Opening",
        description="A quiet street at dawn.",
    )
    db.add(scene)
    await db.commit()
    await db.refresh(scene)
    return scene


async def _create_characters(client, auth_headers, project_id, n):
    ids = []
    for i in range(n):
        r = await client.post(
            f"/api/v1/characters/{project_id}",
            json={"name": f"Char {i + 1}", "role": "supporting"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


class TestSeventhCharacter:
    @pytest.mark.asyncio
    async def test_seventh_character_accepted(self, client, auth_headers, test_project):
        await _create_characters(client, auth_headers, test_project.id, 6)
        r = await client.post(
            f"/api/v1/characters/{test_project.id}",
            json={"name": "Char 7", "role": "supporting"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text

    @pytest.mark.asyncio
    async def test_tenth_character_accepted(self, client, auth_headers, test_project):
        await _create_characters(client, auth_headers, test_project.id, 9)
        r = await client.post(
            f"/api/v1/characters/{test_project.id}",
            json={"name": "Char 10", "role": "supporting"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text


class TestPromptGeneration:
    @pytest.mark.asyncio
    async def test_generate_prompt_reachable(self, client, auth_headers):
        r = await client.post(
            "/api/v1/prompts/generate",
            json={
                "prompt_type": "character_image",
                "context": {"name": "Nadia", "physical_appearance": "tall",
                            "personality": "calm", "costume": "batik dress"},
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert "Nadia" in r.json()["prompt_text"]

    @pytest.mark.asyncio
    async def test_generate_prompt_incomplete_context_no_500(self, client, auth_headers):
        # Missing template keys must not KeyError -> 500; placeholders stay.
        r = await client.post(
            "/api/v1/prompts/generate",
            json={"prompt_type": "character_image", "context": {"name": "Nadia"}},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

    @pytest.mark.asyncio
    async def test_generate_all_scene_prompts(
        self, client, auth_headers, test_project, test_episode, test_scene
    ):
        r = await client.post(
            f"/api/v1/prompts/{test_project.id}/episodes/{test_episode.id}"
            f"/scenes/{test_scene.id}/generate-all",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        types = {p["prompt_type"] for p in r.json()}
        assert "scene_image" in types
        assert "video_generation" in types


class TestAssets:
    @pytest.mark.asyncio
    async def test_upload_metadata_roundtrip(self, client, auth_headers, test_project):
        r = await client.post(
            f"/api/v1/assets/{test_project.id}/upload",
            files={"file": ("frame.png", b"\x89PNG fake", "image/png")},
            data={"asset_type": "image", "metadata": json.dumps({"shot": 1})},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        asset = r.json()
        assert asset["asset_metadata"] == {"shot": 1}
        asset_id = asset["id"]
        try:
            r = await client.get(
                f"/api/v1/assets/{test_project.id}/{asset_id}", headers=auth_headers
            )
            assert r.status_code == 200, r.text
            assert r.json()["asset_metadata"] == {"shot": 1}
            r = await client.get(f"/api/v1/assets/{test_project.id}", headers=auth_headers)
            assert r.status_code == 200, r.text
            assert r.json()["total"] == 1
        finally:
            await client.delete(
                f"/api/v1/assets/{test_project.id}/{asset_id}", headers=auth_headers
            )

    @pytest.mark.asyncio
    async def test_upload_bad_extension_rejected(self, client, auth_headers, test_project):
        r = await client.post(
            f"/api/v1/assets/{test_project.id}/upload",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
            data={"asset_type": "image"},
            headers=auth_headers,
        )
        assert r.status_code == 400, r.text

    @pytest.mark.asyncio
    async def test_upload_bad_metadata_json_rejected(self, client, auth_headers, test_project):
        r = await client.post(
            f"/api/v1/assets/{test_project.id}/upload",
            files={"file": ("frame.png", b"\x89PNG fake", "image/png")},
            data={"asset_type": "image", "metadata": "{not json"},
            headers=auth_headers,
        )
        assert r.status_code == 400, r.text


class TestSettingsAdminGate:
    @pytest.mark.asyncio
    async def test_patch_settings_non_admin_forbidden(self, client, auth_headers):
        r = await client.patch(
            "/api/v1/settings",
            json={"ai_providers": []},
            headers=auth_headers,
        )
        assert r.status_code == 403, r.text

    @pytest.mark.asyncio
    async def test_patch_settings_admin_ok(self, client, admin_headers):
        r = await client.patch(
            "/api/v1/settings",
            json={"ai_providers": [
                {"name": "Nvidia NIM", "model": "nvidia/nemotron-3-ultra-550b-a55b",
                 "api_key_env": "NVIDIA_API_KEY", "enabled": True, "order": 1}
            ]},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["ai_providers"][0]["api_key_env"] == "NVIDIA_API_KEY"

    @pytest.mark.asyncio
    async def test_patch_settings_disallowed_api_key_env(self, client, admin_headers):
        r = await client.patch(
            "/api/v1/settings",
            json={"ai_providers": [
                {"name": "Evil", "model": "x", "api_key_env": "SECRET_KEY",
                 "enabled": True, "order": 1}
            ]},
            headers=admin_headers,
        )
        assert r.status_code == 400, r.text

    @pytest.mark.asyncio
    async def test_first_registered_user_is_admin(self, client, db):
        r = await client.post(
            "/api/v1/auth/register",
            json={"email": "first@example.com", "password": "firstpassword123",
                  "full_name": "First"},
        )
        assert r.status_code == 201, r.text
        result = await db.execute(
            select(User).where(User.email == "first@example.com")
        )
        assert result.scalar_one().role == UserRole.ADMIN


class TestDuplicateOAuthRemoved:
    @pytest.mark.asyncio
    async def test_settings_google_auth_url_gone(self, client, auth_headers):
        r = await client.get(
            "/api/v1/settings/google/auth-url",
            params={"account_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth_headers,
        )
        assert r.status_code == 404, r.text

    @pytest.mark.asyncio
    async def test_settings_google_callback_gone(self, client, auth_headers):
        r = await client.post(
            "/api/v1/settings/google/callback",
            json={"code": "x", "state": "y",
                  "account_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth_headers,
        )
        assert r.status_code == 404, r.text

    @pytest.mark.asyncio
    async def test_google_accounts_auth_url_without_creds_is_400_not_500(
        self, client, auth_headers
    ):
        r = await client.post(
            "/api/v1/google-accounts",
            json={"email": "oauth@example.com"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        account_id = r.json()["id"]
        r = await client.get(
            f"/api/v1/google-accounts/{account_id}/auth-url",
            headers=auth_headers,
        )
        assert r.status_code == 400, r.text  # no OAuth creds configured

    @pytest.mark.asyncio
    async def test_google_account_response_has_no_session_data(
        self, client, auth_headers
    ):
        r = await client.post(
            "/api/v1/google-accounts",
            json={"email": "nodata@example.com"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        assert "session_data" not in r.json()
        r = await client.get("/api/v1/google-accounts", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert all("session_data" not in a for a in r.json())


class TestGooglePasswordBodyOnly:
    @pytest.mark.asyncio
    async def test_set_password_body_ok(self, client, auth_headers):
        r = await client.post(
            "/api/v1/google-accounts",
            json={"email": "pw@example.com"},
            headers=auth_headers,
        )
        account_id = r.json()["id"]
        r = await client.post(
            f"/api/v1/google-accounts/{account_id}/password",
            json={"password": "secret123"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/google-accounts/{account_id}/password/verify",
            json={"password": "secret123"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["valid"] is True

    @pytest.mark.asyncio
    async def test_set_password_query_rejected(self, client, auth_headers):
        r = await client.post(
            "/api/v1/google-accounts",
            json={"email": "pwq@example.com"},
            headers=auth_headers,
        )
        account_id = r.json()["id"]
        r = await client.post(
            f"/api/v1/google-accounts/{account_id}/password?password=secret123",
            headers=auth_headers,
        )
        assert r.status_code == 422, r.text


class TestSnapshotBeforeRegenerate:
    @pytest.mark.asyncio
    async def test_generate_series_snapshots_old_episode(
        self, client, auth_headers, test_project, test_episode, test_scene, db
    ):
        mock_result = {
            "episodes": [
                {"episode_number": 1, "title": "New Pilot",
                 "outline": "Brand new outline"},
            ],
            "series_bible": {
                "main_plot": "New plot",
                "subplots": [],
                "episode_structure": {"total_episodes": 1},
            },
        }
        with patch(
            "app.api.story_engine.generate_series_outline", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = mock_result
            r = await client.post(
                f"/api/v1/story-engine/{test_project.id}/generate-series",
                json={"premise": "A test drama", "genre": "Drama", "num_episodes": 1},
                headers=auth_headers,
            )
        assert r.status_code == 201, r.text
        # Old episode replaced by the new one...
        result = await db.execute(
            select(Episode).where(Episode.project_id == test_project.id)
        )
        episodes = result.scalars().all()
        assert len(episodes) == 1
        assert episodes[0].title == "New Pilot"
        # ...but the old episode survives as a revision snapshot.
        result = await db.execute(select(EpisodeRevision))
        revisions = result.scalars().all()
        assert len(revisions) == 1
        assert revisions[0].outline == "Intro outline"
        assert revisions[0].scenes_snapshot[0]["title"] == "Opening"

    @pytest.mark.asyncio
    async def test_generate_series_invalid_llm_output_keeps_old_data(
        self, client, auth_headers, test_project, test_episode, db
    ):
        # LLM returns episodes without titles -> 502, old episode untouched.
        with patch(
            "app.api.story_engine.generate_series_outline", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = {
                "episodes": [{"episode_number": 1}],
                "series_bible": {"main_plot": "x", "subplots": [],
                                 "episode_structure": {}},
            }
            r = await client.post(
                f"/api/v1/story-engine/{test_project.id}/generate-series",
                json={"premise": "A test drama", "genre": "Drama", "num_episodes": 1},
                headers=auth_headers,
            )
        assert r.status_code == 502, r.text
        result = await db.execute(
            select(Episode).where(Episode.project_id == test_project.id)
        )
        episodes = result.scalars().all()
        assert len(episodes) == 1
        assert episodes[0].title == "Pilot"

    @pytest.mark.asyncio
    async def test_empty_premise_rejected(
        self, client, auth_headers, test_project
    ):
        r = await client.post(
            f"/api/v1/story-engine/{test_project.id}/generate-series",
            json={"premise": "", "genre": "Drama", "num_episodes": 1},
            headers=auth_headers,
        )
        assert r.status_code == 422, r.text


class TestImportResultsContract:
    @pytest.mark.asyncio
    async def test_import_results_json_body_missing_file_400(
        self, client, auth_headers, test_project, db, test_user
    ):
        task = FlowTask(
            project_id=test_project.id, task_type="video", title="T1",
            status="pending",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        r = await client.post(
            f"/api/v1/flow/{test_project.id}/import-results",
            json={"task_id": str(task.id),
                  "output_files": ["/nonexistent/path/video.mp4"]},
            headers=auth_headers,
        )
        assert r.status_code == 400, r.text

    @pytest.mark.asyncio
    async def test_import_results_json_body_existing_file_ok(
        self, client, auth_headers, test_project, db, tmp_path
    ):
        real_file = tmp_path / "clip.mp4"
        real_file.write_bytes(b"fake video")
        task = FlowTask(
            project_id=test_project.id, task_type="video", title="T1",
            status="pending",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        r = await client.post(
            f"/api/v1/flow/{test_project.id}/import-results",
            json={"task_id": str(task.id), "output_files": [str(real_file)]},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert "Imported 1 files" in r.json()["message"]
