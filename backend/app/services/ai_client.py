"""AI Client Service - Real LLM integration with provider fallback."""

import json
import os
import re
import ssl
import logging
from typing import Any, Optional
from uuid import UUID

import httpx
from app.core.config import settings
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Proxy and SSL configuration for egress
PROXY_URL = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
CA_BUNDLE_PATH = "/run/hatch/egress-tls/ca-bundle.pem"

def _get_ssl_context() -> Optional[ssl.SSLContext]:
    """Create SSL context with custom CA bundle if available."""
    if os.path.exists(CA_BUNDLE_PATH):
        return ssl.create_default_context(cafile=CA_BUNDLE_PATH)
    return None

def _get_client_config() -> dict:
    """Get httpx client configuration with proxy and SSL."""
    config = {"timeout": 120.0, "trust_env": False}
    if PROXY_URL:
        config["proxy"] = PROXY_URL
    ssl_context = _get_ssl_context()
    if ssl_context:
        config["verify"] = ssl_context
    return config


class AIProviderError(Exception):
    """Raised when an AI provider fails."""

    def __init__(self, provider_id: str, message: str, status_code: Optional[int] = None):
        self.provider_id = provider_id
        self.status_code = status_code
        super().__init__(f"Provider {provider_id}: {message}")


class AIClient:
    """Client for calling AI providers with fallback support."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._settings_cache: Optional[dict] = None

    async def _get_ai_providers(self) -> list[dict]:
        """Get AI provider configuration from settings (DB + env fallback)."""
        if self._settings_cache is not None:
            return self._settings_cache.get("ai_providers", [])

        # Try to get from DB settings
        from app.models import AppSettings
        result = await self.db.execute(select(AppSettings))
        app_settings = result.scalar_one_or_none()

        if app_settings and app_settings.ai_providers:
            providers = app_settings.ai_providers
        else:
            # Fallback to env-based default (Nvidia NIM)
            providers = [
                {
                    "id": "nvidia-nemotron-ultra",
                    "name": "Nvidia NIM",
                    "provider": "nvidia",
                    "model": "nvidia/nemotron-3-ultra-550b-a55b",
                    "api_key_env": "NVIDIA_API_KEY",
                    "key_env": "NVIDIA_API_KEY",  # legacy compat
                    "enabled": True,
                    "priority": 1,
                    "order": 1,
                    "base_url": "https://integrate.api.nvidia.com/v1",
                }
            ]

        # Normalize providers: support both schema (order, api_key_env, name) and legacy (priority, key_env, provider) fields
        normalized = []
        for p in providers:
            np = dict(p)
            # id fallback
            np.setdefault("id", np.get("name", "").lower().replace(" ", "-") or "unknown")
            # provider fallback
            np.setdefault("provider", np.get("id", "nvidia"))
            # key_env / api_key_env sync
            if "api_key_env" in np and "key_env" not in np:
                np["key_env"] = np["api_key_env"]
            elif "key_env" in np and "api_key_env" not in np:
                np["api_key_env"] = np["key_env"]
            # order / priority sync
            if "order" in np and "priority" not in np:
                np["priority"] = np["order"]
            elif "priority" in np and "order" not in np:
                np["order"] = np["priority"]
            # base_url default
            np.setdefault("base_url", "https://integrate.api.nvidia.com/v1")
            normalized.append(np)

        # Sort by priority (lower = first)
        normalized.sort(key=lambda p: p.get("priority", 999))
        self._settings_cache = {"ai_providers": normalized}
        return normalized

    def _get_api_key(self, key_env: str) -> Optional[str]:
        """Get API key: process env dulu, fallback ke Settings (.env).

        Nilai .env TIDAK masuk os.environ (pydantic-settings hanya isi
        objek Settings), jadi os.getenv saja selalu None di deployment
        normal — fallback ini yang membuat key dari .env terpakai.
        """
        return os.getenv(key_env) or getattr(settings, key_env, None)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Call chat completions with provider fallback.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed response with 'content' and metadata

        Raises:
            AIProviderError: If all providers fail
        """
        providers = await self._get_ai_providers()
        enabled_providers = [p for p in providers if p.get("enabled", True)]

        if not enabled_providers:
            raise AIProviderError("none", "No AI providers configured or enabled")

        last_error = None
        for provider in enabled_providers:
            provider_id = provider.get("id", "unknown")
            try:
                logger.info(f"Trying AI provider: {provider_id} ({provider.get('model')})")
                result = await self._call_provider(provider, messages, temperature, max_tokens, **kwargs)
                logger.info(f"Provider {provider_id} succeeded")
                return result
            except AIProviderError as e:
                logger.warning(f"Provider {provider_id} failed: {e}")
                last_error = e
                continue
            except Exception as e:
                logger.warning(f"Provider {provider_id} unexpected error: {e}")
                last_error = AIProviderError(provider_id, str(e))
                continue

        # All providers failed
        raise AIProviderError(
            "all",
            f"All AI providers failed. Last error: {last_error}",
            status_code=502,
        )

    async def _call_provider(
        self,
        provider: dict,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs,
    ) -> dict[str, Any]:
        """Call a specific provider's chat completions endpoint."""
        provider_type = provider.get("provider", "nvidia")
        model = provider.get("model")
        key_env = provider.get("key_env")
        base_url = provider.get("base_url", "https://integrate.api.nvidia.com/v1")

        api_key = self._get_api_key(key_env)
        if not api_key:
            raise AIProviderError(
                provider.get("id", "unknown"),
                f"API key not configured (env var: {key_env})",
                status_code=401,
            )

        if provider_type == "nvidia":
            return await self._call_nvidia(base_url, api_key, model, messages, temperature, max_tokens, **kwargs)
        else:
            # Unknown provider type - try OpenAI-compatible format
            return await self._call_openai_compatible(base_url, api_key, model, messages, temperature, max_tokens, **kwargs)

    async def _call_nvidia(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs,
    ) -> dict[str, Any]:
        """Call Nvidia NIM chat completions endpoint."""
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        client_config = _get_client_config()
        async with httpx.AsyncClient(**client_config) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 429:
            raise AIProviderError("nvidia", "Rate limited (429)", status_code=429)
        if response.status_code == 401:
            raise AIProviderError("nvidia", "Invalid API key (401)", status_code=401)
        if response.status_code >= 500:
            raise AIProviderError("nvidia", f"Server error ({response.status_code})", status_code=response.status_code)
        if response.status_code != 200:
            raise AIProviderError("nvidia", f"HTTP {response.status_code}: {response.text[:200]}", status_code=response.status_code)

        data = response.json()

        # Parse Nvidia response format (OpenAI-compatible)
        choices = data.get("choices", [])
        if not choices:
            raise AIProviderError("nvidia", "Empty choices in response")

        message = choices[0].get("message", {})
        content = message.get("content", "").strip()

        if not content:
            raise AIProviderError("nvidia", "Empty content in response")

        return {
            "content": content,
            "model": model,
            "provider": "nvidia",
            "usage": data.get("usage", {}),
            "raw": data,
        }

    async def _call_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs,
    ) -> dict[str, Any]:
        """Call OpenAI-compatible chat completions endpoint."""
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        client_config = _get_client_config()
        async with httpx.AsyncClient(**client_config) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 429:
            raise AIProviderError("openai_compat", "Rate limited (429)", status_code=429)
        if response.status_code == 401:
            raise AIProviderError("openai_compat", "Invalid API key (401)", status_code=401)
        if response.status_code >= 500:
            raise AIProviderError("openai_compat", f"Server error ({response.status_code})", status_code=response.status_code)
        if response.status_code != 200:
            raise AIProviderError("openai_compat", f"HTTP {response.status_code}: {response.text[:200]}", status_code=response.status_code)

        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise AIProviderError("openai_compat", "Empty choices in response")

        message = choices[0].get("message", {})
        content = message.get("content", "").strip()

        if not content:
            raise AIProviderError("openai_compat", "Empty content in response")

        return {
            "content": content,
            "model": model,
            "provider": "openai_compatible",
            "usage": data.get("usage", {}),
            "raw": data,
        }


# Convenience function for direct use (creates its own DB session)
def _strip_json_fence(content: str) -> str:
    """Strip ```json ... ``` fences (and stray backticks) from LLM output
    before json.loads — LLMs wrap JSON in fences despite instructions."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def get_ai_client() -> AIClient:
    """Get an AIClient instance with a fresh DB session."""
    async for db in get_db():
        return AIClient(db)
    raise RuntimeError("Could not get database session")


# Prompt templates for story generation
SYSTEM_PROMPT_SERIES = """You are an expert TV series writer. Generate a compelling {num_episodes}-episode series outline from the given premise.
Return ONLY valid JSON matching the specified schema. No markdown, no explanations."""

SERIES_GENERATION_PROMPT = """Premise: {premise}
Genre: {genre}
Themes: {themes}
Tone: {tone}
Number of episodes: {num_episodes}

Characters in this project (write the story for THESE characters):
{characters}

Locations in this project (set scenes in THESE locations where fitting):
{locations}

Generate a complete series outline as JSON with this exact structure:
{{
  "episodes": [
    {{
      "episode_number": 1,
      "title": "Episode Title",
      "outline": "Detailed episode outline (200-400 words)",
      "act": "setup|confrontation|resolution",
      "key_beats": ["Beat 1 description", "Beat 2 description", "Beat 3 description", "Beat 4 description"],
      "cliffhanger": "Cliffhanger text or null for final episode"
    }}
  ],
  "series_bible": {{
    "main_plot": "Overall series plot summary (200-300 words)",
    "subplots": [
      {{"name": "Subplot name", "description": "Description", "theme": "Theme"}}
    ],
    "episode_structure": {{
      "total_episodes": {num_episodes},
      "structure": "three_act",
      "acts": {{
        "act1": {{"episodes": "1-X", "focus": "setup"}},
        "act2": {{"episodes": "X-Y", "focus": "confrontation"}},
        "act3": {{"episodes": "Y-Z", "focus": "resolution"}}
      }}
    }}
  }}
}}

Divide episodes across three acts: setup (first third), confrontation (middle third), resolution (final third)."""


SYSTEM_PROMPT_SCENES = """You are an expert screenwriter. Break down an episode outline into detailed scenes with shot lists.
Return ONLY valid JSON matching the specified schema. No markdown, no explanations."""

SCENE_BREAKDOWN_PROMPT = """Episode Outline: {episode_outline}

Characters:
{characters}

Locations:
{locations}

Generate a scene breakdown as JSON array with this exact structure per scene:
[
  {{
    "scene_number": 1,
    "title": "Scene Title",
    "description": "Detailed scene description (100-200 words)",
    "location_id": "location-uuid-or-null",
    "location_name": "Location name",
    "characters": [
      {{
        "character_id": "character-uuid",
        "character_name": "Character Name",
        "actions": "What the character does in this scene",
        "emotional_state": "Character's emotional state",
        "position": "center|left|right|various"
      }}
    ],
    "shot_list": [
      {{"shot": 1, "type": "establishing|wide|medium|close_up|reverse|detail", "description": "Shot description"}}
    ],
    "camera_directions": "Overall camera direction notes"
  }}
]

Create 5-8 scenes. Use provided character/location UUIDs where available. Match location_id to one of the provided locations."""


async def generate_series_outline(
    ai_client: AIClient,
    premise: str,
    genre: str,
    themes: list[str],
    num_episodes: int,
    tone: Optional[str],
    characters: Optional[list[dict]] = None,
    locations: Optional[list[dict]] = None,
) -> dict:
    """Generate series outline using LLM."""
    chars_str = "\n".join(
        [f"- {c.get('name', '')} ({c.get('role', '')})" for c in (characters or [])]
    ) or "None defined yet"
    locs_str = "\n".join([f"- {l.get('name', '')}" for l in (locations or [])]) or "None defined yet"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SERIES.format(num_episodes=num_episodes)},
        {"role": "user", "content": SERIES_GENERATION_PROMPT.format(
            premise=premise,
            genre=genre or "drama",
            themes=", ".join(themes) if themes else "human drama",
            tone=tone or "dramatic",
            num_episodes=num_episodes,
            characters=chars_str,
            locations=locs_str,
        )},
    ]

    result = await ai_client.chat_completion(messages, temperature=0.8, max_tokens=8000)

    try:
        parsed = json.loads(_strip_json_fence(result["content"]))
        # Validate structure
        if "episodes" not in parsed or "series_bible" not in parsed:
            raise ValueError("Missing required keys in response")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM series response: {e}")
        logger.debug(f"Raw content: {result['content'][:500]}")
        raise AIProviderError("nvidia", f"Invalid JSON response: {e}")


async def generate_scene_breakdown(
    ai_client: AIClient,
    episode_outline: str,
    characters: list[dict],
    locations: list[dict],
) -> list[dict]:
    """Generate scene breakdown using LLM."""
    chars_str = "\n".join([f"- {c['id']}: {c['name']} ({c.get('role', '')})" for c in characters]) or "None"
    locs_str = "\n".join([f"- {l['id']}: {l['name']}" for l in locations]) or "None"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SCENES},
        {"role": "user", "content": SCENE_BREAKDOWN_PROMPT.format(
            episode_outline=episode_outline,
            characters=chars_str,
            locations=locs_str,
        )},
    ]

    result = await ai_client.chat_completion(messages, temperature=0.7, max_tokens=6000)

    try:
        parsed = json.loads(_strip_json_fence(result["content"]))
        if not isinstance(parsed, list):
            raise ValueError("Response is not a list")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM scene response: {e}")
        logger.debug(f"Raw content: {result['content'][:500]}")
        raise AIProviderError("nvidia", f"Invalid JSON response: {e}")

SYSTEM_PROMPT_CHARACTERS = """You are an expert TV series writer. Create the main cast for a series from the given premise and plot.
Return ONLY valid JSON matching the specified schema. No markdown, no explanations."""

CHARACTERS_GENERATION_PROMPT = """Premise: {premise}
Genre: {genre}
Series plot: {main_plot}

Create {num_characters} main characters for this series as a JSON array with this exact structure per character:
[
  {{
    "name": "Character Full Name",
    "role": "protagonist|antagonist|supporting|love_interest|mentor|rival",
    "physical_appearance": "Appearance description (60-100 words)",
    "personality": "Personality traits (60-100 words)",
    "background": "Character backstory (60-100 words)",
    "costume": "Signature wardrobe / costume notes",
    "consistency_instructions": "Visual consistency notes for image/video generation"
  }}
]

Give every character a distinct, memorable name. Roles must include one protagonist and one antagonist (or central conflict figure)."""


async def generate_characters(
    ai_client: AIClient,
    premise: str,
    genre: str,
    main_plot: Optional[str],
    num_characters: int = 5,
) -> list[dict]:
    """Generate the main cast using LLM."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_CHARACTERS},
        {"role": "user", "content": CHARACTERS_GENERATION_PROMPT.format(
            premise=premise,
            genre=genre or "drama",
            main_plot=main_plot or "",
            num_characters=num_characters,
        )},
    ]
    result = await ai_client.chat_completion(messages, temperature=0.8, max_tokens=4000)
    try:
        parsed = json.loads(_strip_json_fence(result["content"]))
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("Response is not a non-empty list")
        for c in parsed:
            if not isinstance(c, dict) or not str(c.get("name") or "").strip():
                raise ValueError("Character entry is missing a name")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM characters response: {e}")
        logger.debug(f"Raw content: {result['content'][:500]}")
        raise AIProviderError("nvidia", f"Invalid JSON response: {e}")


SYSTEM_PROMPT_LOCATIONS = """You are an expert TV series writer. Create the key shooting locations for a series from the given premise and plot.
Return ONLY valid JSON matching the specified schema. No markdown, no explanations."""

LOCATIONS_GENERATION_PROMPT = """Premise: {premise}
Genre: {genre}
Series plot: {main_plot}

Create {num_locations} key locations for this series as a JSON array with this exact structure per location:
[
  {{
    "name": "Location Name",
    "description": "What this place is (60-100 words)",
    "environment": "Physical environment / set details",
    "lighting": "Typical lighting (e.g. warm evening, cold fluorescent)",
    "atmosphere": "Mood / atmosphere of the place",
    "consistency_instructions": "Visual consistency notes for image/video generation"
  }}
]

Locations must be places where the story's key scenes happen (homes, workplaces, public places)."""


async def generate_locations(
    ai_client: AIClient,
    premise: str,
    genre: str,
    main_plot: Optional[str],
    num_locations: int = 4,
) -> list[dict]:
    """Generate the key locations using LLM."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_LOCATIONS},
        {"role": "user", "content": LOCATIONS_GENERATION_PROMPT.format(
            premise=premise,
            genre=genre or "drama",
            main_plot=main_plot or "",
            num_locations=num_locations,
        )},
    ]
    result = await ai_client.chat_completion(messages, temperature=0.8, max_tokens=4000)
    try:
        parsed = json.loads(_strip_json_fence(result["content"]))
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("Response is not a non-empty list")
        for loc in parsed:
            if not isinstance(loc, dict) or not str(loc.get("name") or "").strip():
                raise ValueError("Location entry is missing a name")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM locations response: {e}")
        logger.debug(f"Raw content: {result['content'][:500]}")
        raise AIProviderError("nvidia", f"Invalid JSON response: {e}")


SYSTEM_PROMPT_VIDEO_PROMPTS = """You are an expert video prompt engineer for AI video generation (Google Flow / Veo style). Write one cinematic video generation prompt per episode.
Return ONLY valid JSON matching the specified schema. No markdown, no explanations."""

VIDEO_PROMPTS_GENERATION_PROMPT = """Series: {series_title}
Genre: {genre}
Tone: {tone}

Main characters: {characters}
Key locations: {locations}

Episodes (write ONE video prompt per episode, using its outline):
{episodes}

Return a JSON array with this exact structure per episode:
[
  {{
    "episode_number": 1,
    "prompt_text": "Cinematic vertical video, 1-2 minutes: ... (80-150 words, describe visuals, camera movement, characters, actions, mood, lighting)",
    "negative_prompt": "blurry, low quality, distorted, flickering, bad motion, watermark, text"
  }}
]

Every episode_number in the input list must appear exactly once in the output. Prompts must be in the same language as the episode outlines."""


async def generate_episode_video_prompts(
    ai_client: AIClient,
    episodes: list[dict],
    series_title: str,
    genre: Optional[str],
    tone: Optional[str],
    characters: Optional[list[dict]] = None,
    locations: Optional[list[dict]] = None,
) -> list[dict]:
    """Generate one Flow/Veo video prompt per episode, in a single LLM call."""
    eps_str = "\n".join(
        f"- Episode {e.get('episode_number')}: {e.get('title', '')} — {e.get('outline', '')}"
        for e in episodes
    )
    chars_str = ", ".join(c.get("name", "") for c in (characters or [])) or "None"
    locs_str = ", ".join(l.get("name", "") for l in (locations or [])) or "None"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_VIDEO_PROMPTS},
        {"role": "user", "content": VIDEO_PROMPTS_GENERATION_PROMPT.format(
            series_title=series_title,
            genre=genre or "drama",
            tone=tone or "dramatic",
            characters=chars_str,
            locations=locs_str,
            episodes=eps_str,
        )},
    ]
    result = await ai_client.chat_completion(messages, temperature=0.7, max_tokens=8000)
    try:
        parsed = json.loads(_strip_json_fence(result["content"]))
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("Response is not a non-empty list")
        seen = set()
        for p in parsed:
            if not isinstance(p, dict):
                raise ValueError("Prompt entry is not an object")
            try:
                num = int(p["episode_number"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Prompt entry is missing a numeric episode_number")
            if num in seen:
                raise ValueError(f"Duplicate episode_number {num} in prompt response")
            seen.add(num)
            if not str(p.get("prompt_text") or "").strip():
                raise ValueError(f"Prompt for episode {num} is empty")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM video-prompts response: {e}")
        logger.debug(f"Raw content: {result['content'][:500]}")
        raise AIProviderError("nvidia", f"Invalid JSON response: {e}")
