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


def _patch_all(mock_series=None, mock_chars=None, mock_locs=None, mock_prompts=None):
    """Context manager patching all four LLM entry points."""
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
    if mock_series is not None:
        p1.return_value = mock_series
    if mock_chars is not None:
        p2.return_value = mock_chars
    if mock_locs is not None:
        p3.return_value = mock_locs
    if mock_prompts is not None:
        p4.return_value = mock_prompts
    return stack


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
        assert response.status_code == 201
        data = response.json()
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
            assert response.status_code == 201
            data = response.json()
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
            data = response.json()
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
            assert first.status_code == 201
            assert first.json()["status"] == "completed"
            assert await _counts(db, test_project.id) == (5, 4, 3, 3)

            second = await client.post(
                f"/api/v1/projects/{test_project.id}/auto-generate",
                json={"title": "Test Project", "genre": "Drama", "num_episodes": 3},
                headers=auth_headers,
            )
            assert second.status_code == 201
            data = second.json()
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
        assert response.status_code == 201
        data = response.json()
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
        assert created.status_code == 201
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
