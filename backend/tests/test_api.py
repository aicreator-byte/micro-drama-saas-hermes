import pytest
from httpx import AsyncClient


class TestAuth:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register(self, client: AsyncClient):
        """Test user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration with duplicate email fails."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "password123",
                "full_name": "Another User",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login(self, client: AsyncClient, test_user):
        """Test user login."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Test login with wrong password fails."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me(self, client: AsyncClient, auth_headers):
        """Test getting current user info."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test getting current user without auth fails."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient, test_user):
        """Test refreshing access token - login again to get new token."""
        # Login again to get new token (no refresh endpoint implemented)
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestProjects:
    """Test project operations."""

    @pytest.mark.asyncio
    async def test_create_project(self, client: AsyncClient, auth_headers):
        """Test creating a project."""
        response = await client.post(
            "/api/v1/projects",
            json={
                "title": "My Drama Series",
                "description": "A test drama series",
                "genre": "Drama",
                "themes": ["family", "romance"],
                "status": "DRAFT",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Drama Series"
        assert data["owner_id"] is not None

    @pytest.mark.asyncio
    async def test_list_projects(self, client: AsyncClient, auth_headers, test_project):
        """Test listing projects."""
        response = await client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert len(data["projects"]) >= 1

    @pytest.mark.asyncio
    async def test_get_project(self, client: AsyncClient, auth_headers, test_project):
        """Test getting a specific project."""
        response = await client.get(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_project.id)
        assert data["title"] == test_project.title

    @pytest.mark.asyncio
    async def test_update_project(self, client: AsyncClient, auth_headers, test_project):
        """Test updating a project."""
        response = await client.patch(
            f"/api/v1/projects/{test_project.id}",
            json={"title": "Updated Title", "status": "in_production"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "in_production"

    @pytest.mark.asyncio
    async def test_delete_project(self, client: AsyncClient, auth_headers, test_project):
        """Test deleting a project."""
        response = await client.delete(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
        assert response.status_code == 204


class TestSeriesBible:
    """Test series bible operations."""

    @pytest.mark.asyncio
    async def test_create_series_bible(self, client: AsyncClient, auth_headers, test_project):
        """Test creating a series bible."""
        response = await client.post(
            f"/api/v1/series-bible/{test_project.id}",
            json={
                "premise": "A family drama about love and betrayal",
                "main_plot": "Two sisters compete for the family business",
                "tone": "Emotional and dramatic",
                "visual_style": "Cinematic, warm tones",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == str(test_project.id)
        assert data["premise"] == "A family drama about love and betrayal"

    @pytest.mark.asyncio
    async def test_get_series_bible(self, client: AsyncClient, auth_headers, test_project):
        """Test getting series bible."""
        # First create one
        await client.post(
            f"/api/v1/series-bible/{test_project.id}",
            json={"premise": "Test premise"},
            headers=auth_headers,
        )

        response = await client.get(f"/api/v1/series-bible/{test_project.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == str(test_project.id)


class TestCharacters:
    """Test character operations."""

    @pytest.mark.asyncio
    async def test_create_character(self, client: AsyncClient, auth_headers, test_project):
        """Test creating a character."""
        response = await client.post(
            f"/api/v1/characters/{test_project.id}",
            json={
                "name": "Hero",
                "role": "Protagonist",
                "physical_appearance": "Tall, dark hair, brown eyes",
                "personality": "Brave, compassionate",
                "background": "Grew up in a small town",
                "costume": "Casual wear",
                "consistency_instructions": "Always wears a necklace",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Hero"
        assert data["project_id"] == str(test_project.id)

    @pytest.mark.asyncio
    async def test_list_characters(self, client: AsyncClient, auth_headers, test_project):
        """Test listing characters."""
        # Create a few characters
        for i in range(3):
            await client.post(
                f"/api/v1/characters/{test_project.id}",
                json={"name": f"Character {i}", "role": "Supporting"},
                headers=auth_headers,
            )

        response = await client.get(f"/api/v1/characters/{test_project.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 3


class TestLocations:
    """Test location operations."""

    @pytest.mark.asyncio
    async def test_create_location(self, client: AsyncClient, auth_headers, test_project):
        """Test creating a location."""
        response = await client.post(
            f"/api/v1/locations/{test_project.id}",
            json={
                "name": "Main House",
                "description": "A beautiful Victorian house",
                "environment": "Interior, living room",
                "lighting": "Warm, natural light",
                "atmosphere": "Cozy and inviting",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Main House"
        assert data["project_id"] == str(test_project.id)


class TestEpisodes:
    """Test episode operations."""

    @pytest.mark.asyncio
    async def test_create_episode(self, client: AsyncClient, auth_headers, test_project):
        """Test creating an episode."""
        response = await client.post(
            f"/api/v1/episodes/{test_project.id}",
            json={
                "episode_number": 1,
                "title": "Pilot",
                "outline": "Introduction to the main characters",
                "status": "PLANNED",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["episode_number"] == 1
        assert data["title"] == "Pilot"

    @pytest.mark.asyncio
    async def test_list_episodes(self, client: AsyncClient, auth_headers, test_project):
        """Test listing episodes."""
        # Create a few episodes
        for i in range(3):
            await client.post(
                f"/api/v1/episodes/{test_project.id}",
                json={"episode_number": i + 1, "title": f"Episode {i + 1}"},
                headers=auth_headers,
            )

        response = await client.get(f"/api/v1/episodes/{test_project.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 3


class TestScenes:
    """Test scene operations."""

    @pytest.mark.asyncio
    async def test_create_scene(self, client: AsyncClient, auth_headers, test_project):
        """Test creating a scene."""
        # First create an episode
        ep_response = await client.post(
            f"/api/v1/episodes/{test_project.id}",
            json={"episode_number": 1, "title": "Ep 1"},
            headers=auth_headers,
        )
        episode = ep_response.json()

        response = await client.post(
            f"/api/v1/scenes/{test_project.id}/episodes/{episode['id']}",
            json={
                "scene_number": 1,
                "title": "Opening Scene",
                "description": "The hero wakes up",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scene_number"] == 1
        assert data["episode_id"] == episode["id"]


class TestPrompts:
    """Test prompt operations."""

    @pytest.mark.asyncio
    async def test_create_prompt(self, client: AsyncClient, auth_headers, test_project):
        """Test creating a prompt."""
        response = await client.post(
            f"/api/v1/prompts/{test_project.id}",
            json={
                "prompt_type": "character_image",
                "title": "Hero Portrait",
                "prompt_text": "A heroic portrait of the main character",
                "negative_prompt": "blurry, low quality",
                "parameters": {"width": 1024, "height": 1024},
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["prompt_type"] == "character_image"
        assert data["title"] == "Hero Portrait"


class TestGoogleAccounts:
    """Test Google account operations."""

    @pytest.mark.asyncio
    async def test_create_google_account(self, client: AsyncClient, auth_headers):
        """Test creating a Google account."""
        response = await client.post(
            "/api/v1/google-accounts",
            json={
                "email": "test@gmail.com",
                "display_name": "Test Account",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@gmail.com"
        assert data["display_name"] == "Test Account"
        assert data["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_list_google_accounts(self, client: AsyncClient, auth_headers):
        """Test listing Google accounts."""
        # Create one first
        await client.post(
            "/api/v1/google-accounts",
            json={"email": "test@gmail.com"},
            headers=auth_headers,
        )

        response = await client.get("/api/v1/google-accounts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_account_limit(self, client: AsyncClient, auth_headers):
        """Test 20 account limit per user."""
        # Create 20 accounts
        for i in range(20):
            response = await client.post(
                "/api/v1/google-accounts",
                json={"email": f"test{i}@gmail.com"},
                headers=auth_headers,
            )
            assert response.status_code == 201

        # 21st should fail
        response = await client.post(
            "/api/v1/google-accounts",
            json={"email": "test21@gmail.com"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "20" in response.json()["detail"] or "limit" in response.json()["detail"].lower()


class TestFlowBridge:
    """Test Flow Bridge operations."""

    @pytest.mark.asyncio
    async def test_create_flow_task(self, client: AsyncClient, auth_headers, test_project):
        """Test creating a flow task."""
        response = await client.post(
            f"/api/v1/flow/{test_project.id}/tasks",
            json={
                "task_type": "prompt_preparation",
                "title": "Prepare Prompts for Ep 1",
                "input_prompts": [{"prompt_type": "video_generation", "prompt_text": "test"}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["task_type"] == "prompt_preparation"
        assert data["project_id"] == str(test_project.id)


class TestAssets:
    """Test asset operations."""

    @pytest.mark.asyncio
    async def test_list_assets(self, client: AsyncClient, auth_headers, test_project):
        """Test listing assets."""
        response = await client.get(f"/api/v1/assets/{test_project.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestStoryEngine:
    """Test story engine operations."""

    @pytest.mark.asyncio
    async def test_generate_series(self, client: AsyncClient, auth_headers, test_project):
        """Test generating a series outline."""
        response = await client.post(
            f"/api/v1/story-engine/{test_project.id}/generate-series",
            json={
                "premise": "A test drama",
                "genre": "Drama",
                "num_episodes": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "episodes" in data
        assert "series_bible" in data