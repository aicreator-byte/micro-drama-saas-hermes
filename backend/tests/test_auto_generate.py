"""Tests for the auto-generate job API (Fase 1 backend).

AI calls are mocked — no external network. Mirrors the mocking pattern of
TestStoryEngine in test_api.py.
"""

import pytest
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select

from app.models import (
    SeriesBible, Character, Location, Episode, Prompt, PromptType,
    AutoGenerateJob,
)
from app.services.ai_client import AIProviderError


def _series_result(num_episodes=3):
    return {
        "episodes": [
            {
                "episode_number": i + 1,
                "title": f"Episode {i + 1}",
                "outline": f"Outline for episode {i + 1}: the story advances.",
                "act": "setup",
                "key_beats": ["Beat 1", "Beat 2"],
                "cliffhanger": "A twist",
            }
            for i in range(num_episodes)
        ],
        "series_bible": {
            "main_plot": "A test drama about love and betrayal.",
            "subplots": [{"name": "Romance", "description": "Forbidden love", "theme": "Love"}],
            "episode_structure": {"total_episodes": num_episodes, "structure": "three_act"},
        },
    }


def _characters_result(n=5):
    roles = ["protagonist", "antagonist", "supporting", "love_interest", "mentor"]
    return [
        {
            "name": f"Character {i + 1}",
            "role": roles[i % len(roles)],
            "physical_appearance": "Tall, sharp features.",
            "personality": "Driven and stubborn.",
            "background": f"Backstory {i + 1}.",
            "costume": "Business attire.",
            "consistency_instructions": "Same face in every shot.",
        }
        for i in range(n)
    ]


def _locations_result(n=4):
    return [
        {
            "name": f"Location {i + 1}",
            "description": f"Description {i + 1}.",
            "environment": "Modern interior.",
            "lighting": "Warm evening.",
            "atmosphere": "Tense.",
            "consistency_instructions": "Same layout in every shot.",
        }
        for i in range(n)
    ]


def _video_prompts_result(episode_numbers):
    return [
        {
            "episode_number": n,
            "prompt_text": f"Cinematic vertical video for episode {n}: the story advances, dramatic lighting.",
            "negative_prompt": "blurry, low quality",
        }
        for n in episode_numbers
    ]


def _patch_all(mock_series=None, mock_chars=None, mock_locs=None, mock_prompts=None,
               mock_genre="drama"):
    """Context manager patching all LLM entry points (incl. genre inference)."""
    from contextlib import ExitStack
    stack = ExitStack()
    p1 = stack.enter_context(patch(
        "app.api.auto_generate.generate_series_outline", new_callable=AsyncMock))
    p2 = stack.enter_context(patch(
        "app.api.auto_generate.generate_characters", new_callable=AsyncMock))
    p3 = stack.enter_context(patch(
        "app.api.auto_generate.generate_locations", new_callable=AsyncMock))
    p4 = stack.enter_context(patch(
        "app.api.auto_generate.generate_episode_video_prompts", new_callable=AsyncMock))
    p5 = stack.enter_context(patch(
        "app.api.auto_generate.infer_genre_from_title", new_callable=AsyncMock))
    if mock_series is not None:
        p1.return_value = mock_series
    if mock_chars is not None:
        p2.return_value = mock_chars
    if mock_locs is not None:
        p3.return_value = mock_locs
    if mock_prompts is not None:
        p4.return_value = mock_prompts
    p5.return_value = mock_genre
    return stack


async def _wait_job(client, project_id, job_id, headers, timeout=30.0):
    """Poll GET until the job is terminal. POST is async (202) now, so
    the create response only shows pending/running; the background run
    finishes before the ASGI call returns in tests, so this is
    normally a single GET — polling mirrors what the frontend does."""
    import asyncio
    for _ in range(int(timeout / 0.2)):
        response = await client.get(
            f"/api/v1/projects/{project_id}/auto-generate/{job_id}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        if data["status"] in ("completed", "failed"):
            return data
        await asyncio.sleep(0.2)
    raise AssertionError(f"job {job_id} never reached a terminal state")


async def _counts(db, project_id):
    async def count(model, *conds):
        q = select(model).where(model.project_id == project_id, *conds)
        return len((await db.execute(q)).scalars().all())
    chars = await count(Character)
    locs = await count(Location)
    eps = await count(Episode)
    prompts = await count(Prompt, Prompt.prompt_type == PromptType.VIDEO_GENERATION)
    return chars, locs, eps, prompts


class TestAutoGenerate:
    @pytest.mark.asyncio
    async def test_full_run_creates_everything(self, client: AsyncClient, auth_headers, test_project, db):
        """POST auto-generate runs all 5 steps and fills the project."""
        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
        ):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] in ("pending", "running")
        data = await _wait_job(client, test_project.id, data["id"], auth_headers)
        assert data["status"] == "completed"
        assert len(data["steps"]) == 5
        assert [s["step_key"] for s in data["steps"]] == [
            "series_bible", "characters", "locations", "episodes", "prompts",
        ]
        assert all(s["status"] == "completed" for s in data["steps"])

        # Verify materialized rows
        result = await db.execute(
            select(SeriesBible).where(SeriesBible.project_id == test_project.id))
        bible = result.scalar_one_or_none()
        assert bible is not None and bible.main_plot.startswith("A test drama")
        assert await _counts(db, test_project.id) == (5, 4, 3, 3)

        # GET the job back
        job_id = data["id"]
        response = await client.get(
            f"/api/v1/projects/{test_project.id}/auto-generate/{job_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_retry_failed_step(self, client: AsyncClient, auth_headers, test_project, db):
        """A failed step stops the run; retry runs only that step onward."""
        # Patch characters to fail once, then succeed on retry.
        with patch("app.api.auto_generate.generate_series_outline", new_callable=AsyncMock) as m_series, \
                patch("app.api.auto_generate.generate_characters", new_callable=AsyncMock) as m_chars, \
                patch("app.api.auto_generate.generate_locations", new_callable=AsyncMock) as m_locs, \
                patch("app.api.auto_generate.generate_episode_video_prompts", new_callable=AsyncMock) as m_prompts:
            m_series.return_value = _series_result(3)
            m_chars.side_effect = [
                AIProviderError("nvidia", "boom"),
                _characters_result(5),
            ]
            m_locs.return_value = _locations_result(4)
            m_prompts.return_value = _video_prompts_result([1, 2, 3])

            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
            assert response.status_code == 202
            data = await _wait_job(client, test_project.id, response.json()["id"], auth_headers)
            assert data["status"] == "failed"
            steps = {s["step_key"]: s["status"] for s in data["steps"]}
            assert steps["series_bible"] == "completed"
            assert steps["characters"] == "failed"
            assert steps["locations"] == "pending"
            assert steps["episodes"] == "pending"
            assert steps["prompts"] == "pending"
            assert "characters" in (data["error_message"] or "")
            assert await _counts(db, test_project.id) == (0, 0, 3, 0)

            # Retry only the failed step; the rest continues.
            job_id = data["id"]
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate/{job_id}/retry/characters",
                headers=auth_headers,
            )
            assert response.status_code == 200
            assert response.json()["status"] in ("running", "completed")
            data = await _wait_job(client, test_project.id, job_id, auth_headers)
            assert data["status"] == "completed"
            assert all(s["status"] == "completed" for s in data["steps"])
            assert await _counts(db, test_project.id) == (5, 4, 3, 3)

    @pytest.mark.asyncio
    async def test_rerun_is_idempotent(self, client: AsyncClient, auth_headers, test_project, db):
        """A second run skips existing rows — no duplicates."""
        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
        ):
            first = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
            assert first.status_code == 202
            first_data = await _wait_job(client, test_project.id, first.json()["id"], auth_headers)
            assert first_data["status"] == "completed"
            assert await _counts(db, test_project.id) == (5, 4, 3, 3)

            second = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
            assert second.status_code == 202
            data = await _wait_job(client, test_project.id, second.json()["id"], auth_headers)
            assert data["status"] == "completed"
            steps = {s["step_key"]: s["status"] for s in data["steps"]}
            # Content already exists: steps skip instead of regenerating.
            assert steps["series_bible"] == "skipped"
            assert steps["characters"] == "skipped"
            assert steps["locations"] == "skipped"
            assert steps["prompts"] == "skipped"
            assert await _counts(db, test_project.id) == (5, 4, 3, 3)

    @pytest.mark.asyncio
    async def test_prompt_coverage_validation(self, client: AsyncClient, auth_headers, test_project, db):
        """Step 5 fails (no partial rows) when the LLM skips an episode."""
        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2]),  # episode 3 missing
        ):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = await _wait_job(client, test_project.id, response.json()["id"], auth_headers)
        assert data["status"] == "failed"
        steps = {s["step_key"]: s["status"] for s in data["steps"]}
        assert steps["prompts"] == "failed"
        assert await _counts(db, test_project.id) == (5, 4, 3, 0)

    @pytest.mark.asyncio
    async def test_auth_and_ownership(self, client: AsyncClient, auth_headers, auth_headers2, test_project):
        """401 without token, 404 for another user's project, 400 for bad retry."""
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/auto-generate",
            json={"title": "Test Project", "num_episodes": 3},
        )
        assert response.status_code == 401

        response = await client.post(
            f"/api/v1/projects/{test_project.id}/auto-generate",
            json={"title": "Test Project", "num_episodes": 3},
            headers=auth_headers2,
        )
        assert response.status_code == 404

        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
        ):
            created = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
        assert created.status_code == 202
        job_id = created.json()["id"]

        # Unknown step key
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/auto-generate/{job_id}/retry/nope",
            headers=auth_headers,
        )
        assert response.status_code == 400

        # Retrying a completed step is rejected
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/auto-generate/{job_id}/retry/characters",
            headers=auth_headers,
        )
        assert response.status_code == 400

        # Unknown job
        response = await client.get(
            f"/api/v1/projects/{test_project.id}/auto-generate/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    # --- Future-dev 19 Nov 2026 -------------------------------------
    @pytest.mark.asyncio
    async def test_title_not_changed(self, client: AsyncClient, auth_headers, test_project, db):
        """POST auto-generate must NOT rename the project (job title only)."""
        from app.models import Project
        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
        ):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Different Job Title", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        assert response.json()["title"] == "Different Job Title"
        result = await db.execute(select(Project).where(Project.id == test_project.id))
        assert result.scalar_one().title == "Test Project"

    @pytest.mark.asyncio
    async def test_blank_title_rejected(self, client: AsyncClient, auth_headers, test_project):
        """Judul hanya-spasi ditolak 422 (backend), bukan lolos diam-diam."""
        for bad in ("   ", "", " \t\n "):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": bad, "num_episodes": 3},
                headers=auth_headers,
            )
            assert response.status_code == 422, bad

    @pytest.mark.asyncio
    async def test_manual_bible_protected(self, client: AsyncClient, auth_headers, test_project, db):
        """Bible manual tidak ditimpa langkah 1 bila episode belum ada."""
        created = await client.post(
            f"/api/v1/series-bible/{test_project.id}",
            json={"main_plot": "Manual plot — do not touch."},
            headers=auth_headers,
        )
        assert created.status_code == 201
        assert created.json()["source"] == "manual"

        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
        ):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = await _wait_job(client, test_project.id, response.json()["id"], auth_headers)
        assert data["status"] == "completed"
        step1 = next(s for s in data["steps"] if s["step_key"] == "series_bible")
        assert step1["result_summary"]["bible_protected"] is True

        result = await db.execute(
            select(SeriesBible).where(SeriesBible.project_id == test_project.id))
        bible = result.scalar_one()
        assert bible.main_plot == "Manual plot — do not touch."
        assert bible.source == "manual"
        # Episode tetap dibuat dari outline LLM.
        assert await _counts(db, test_project.id) == (5, 4, 3, 3)

    @pytest.mark.asyncio
    async def test_partial_step_rolls_back(self, client: AsyncClient, auth_headers, test_project, db):
        """Langkah yang gagal di tengah jalan tidak meninggalkan baris
        setengah jadi (rollback, bukan commit parsial)."""
        from unittest.mock import patch as mock_patch
        from app.api import auto_generate as ag_mod

        async def _boom(db, job, project, user, ai_client):
            db.add(Character(project_id=project.id, name="Half Done", order_index=0))
            await db.flush()
            raise RuntimeError("boom mid-step")

        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
        ), mock_patch.dict(ag_mod.STEP_RUNNERS, {"characters": _boom}):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = await _wait_job(client, test_project.id, response.json()["id"], auth_headers)
        assert data["status"] == "failed"
        steps = {s["step_key"]: s["status"] for s in data["steps"]}
        assert steps["characters"] == "failed"
        # Karakter setengah jadi ikut ter-rollback: 0 karakter di DB.
        assert await _counts(db, test_project.id) == (0, 0, 3, 0)

    @pytest.mark.asyncio
    async def test_genre_inferred_from_title(self, client: AsyncClient, auth_headers, test_project, db):
        """Tanpa genre user, langkah 1 menebak genre dari judul via LLM."""
        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
            mock_genre="romance",
        ):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Cinta di Ujung Senja", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = await _wait_job(client, test_project.id, response.json()["id"], auth_headers)
        assert data["status"] == "completed"
        assert data["genre"] == "romance"
        step1 = next(s for s in data["steps"] if s["step_key"] == "series_bible")
        assert step1["result_summary"]["genre"] == "romance"
        assert step1["result_summary"]["genre_source"] == "llm"

    @pytest.mark.asyncio
    async def test_genre_unknown_when_inference_fails(self, client: AsyncClient, auth_headers, test_project):
        """Inferensi genre gagal -> label jujur 'unknown', bukan 'drama'."""
        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
            mock_genre=None,
        ):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Xyzzy Plugh", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = await _wait_job(client, test_project.id, response.json()["id"], auth_headers)
        assert data["status"] == "completed"
        assert data["genre"] == "unknown"
        step1 = next(s for s in data["steps"] if s["step_key"] == "series_bible")
        assert step1["result_summary"]["genre_source"] == "unknown"

    @pytest.mark.asyncio
    async def test_step_summaries_have_counts(self, client: AsyncClient, auth_headers, test_project):
        """Setiap ringkasan langkah berisi angka skalar (modal tidak kosong)."""
        with _patch_all(
            mock_series=_series_result(3),
            mock_chars=_characters_result(5),
            mock_locs=_locations_result(4),
            mock_prompts=_video_prompts_result([1, 2, 3]),
        ):
            response = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = await _wait_job(client, test_project.id, response.json()["id"], auth_headers)
        assert data["status"] == "completed"
        summaries = {s["step_key"]: s["result_summary"] for s in data["steps"]}
        assert summaries["series_bible"]["created_count"] == 3
        assert summaries["series_bible"]["episode_count"] == 3
        assert summaries["characters"]["created_count"] == 5
        assert summaries["locations"]["created_count"] == 4
        assert summaries["episodes"]["total_episodes"] == 3
        assert summaries["prompts"]["created_count"] == 3
