"""Unit tests for ai_client chunking + genre inference (future-dev 19 Nov 2026).

No network, no DB: the LLM is a stub that answers prompts for the
episodes named in the request.
"""
import json
import re
import pytest
from unittest.mock import AsyncMock

from app.services.ai_client import (
    AIProviderError,
    PROMPT_CHUNK_SIZE,
    PROMPT_CHUNK_MAX_TOKENS,
    generate_episode_video_prompts,
    infer_genre_from_title,
)


class _StubClient:
    """Fake AIClient answering prompts for episodes named in the request."""

    def __init__(self, drop_episode=None, genre_answer="romance"):
        self.calls = []  # (messages, temperature, max_tokens)
        self.drop_episode = drop_episode
        self.genre_answer = genre_answer

    async def chat_completion(self, messages, temperature=0.7, max_tokens=4000):
        self.calls.append((messages, temperature, max_tokens))
        user_content = messages[-1]["content"]
        if "Tebak SATU genre" in user_content:
            return {"content": self.genre_answer}
        numbers = [int(n) for n in re.findall(r"Episode (\d+):", user_content)]
        prompts = [
            {"episode_number": n, "prompt_text": f"Prompt for episode {n}",
             "negative_prompt": "blurry"}
            for n in numbers if n != self.drop_episode
        ]
        return {"content": json.dumps(prompts)}


def _episodes(n):
    return [
        {"episode_number": i, "title": f"Episode {i}", "outline": f"Outline {i}"}
        for i in range(1, n + 1)
    ]


class TestPromptChunking:
    @pytest.mark.asyncio
    async def test_12_episodes_in_3_calls_max_5_per_call(self):
        client = _StubClient()
        prompts = await generate_episode_video_prompts(
            client, _episodes(12), "Test Series", "drama", "dramatic")
        assert len(prompts) == 12
        assert sorted(p["episode_number"] for p in prompts) == list(range(1, 13))
        # 12 episode / 5 per chunk = 3 LLM calls (5 + 5 + 2).
        assert len(client.calls) == 3
        for messages, temperature, max_tokens in client.calls:
            assert max_tokens == PROMPT_CHUNK_MAX_TOKENS
            assert max_tokens == 4000
            per_call = len(re.findall(r"Episode (\d+):", messages[-1]["content"]))
            assert per_call <= PROMPT_CHUNK_SIZE

    @pytest.mark.asyncio
    async def test_missing_episode_in_chunk_raises_with_number(self):
        client = _StubClient(drop_episode=7)
        with pytest.raises(AIProviderError) as exc:
            await generate_episode_video_prompts(
                client, _episodes(12), "Test Series", "drama", "dramatic")
        assert "7" in str(exc.value)

    @pytest.mark.asyncio
    async def test_30_episodes_never_one_big_call(self):
        client = _StubClient()
        prompts = await generate_episode_video_prompts(
            client, _episodes(30), "Test Series", "drama", "dramatic")
        assert len(prompts) == 30
        assert len(client.calls) == 6  # 30 / 5
        assert all(mt == 4000 for _, _, mt in client.calls)


class TestGenreInference:
    @pytest.mark.asyncio
    async def test_returns_recognized_label(self):
        assert await infer_genre_from_title(_StubClient(genre_answer="romance"), "X") == "romance"

    @pytest.mark.asyncio
    async def test_normalizes_case_punctuation_whitespace(self):
        client = _StubClient(genre_answer='  "Thriller."  ')
        assert await infer_genre_from_title(client, "X") == "thriller"

    @pytest.mark.asyncio
    async def test_unknown_returns_none(self):
        assert await infer_genre_from_title(_StubClient(genre_answer="unknown"), "X") is None

    @pytest.mark.asyncio
    async def test_unrecognized_label_returns_none(self):
        assert await infer_genre_from_title(_StubClient(genre_answer="western"), "X") is None

    @pytest.mark.asyncio
    async def test_provider_error_returns_none(self):
        failing = AsyncMock()
        failing.chat_completion = AsyncMock(
            side_effect=AIProviderError("nvidia", "down"))
        assert await infer_genre_from_title(failing, "X") is None
