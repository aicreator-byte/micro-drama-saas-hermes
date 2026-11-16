import pytest
from httpx import AsyncClient


class TestTenantIsolation:
    """Test multi-tenant data isolation."""

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_projects(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test that user 2 cannot access user 1's project."""
        # User 2 tries to access user 1's project
        response = await client.get(
            f"/api/v1/projects/{test_project.id}",
            headers=auth_headers2,
        )
        # Should return 404 (not found) or 403 (forbidden) - not 200
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_users_cannot_list_each_other_projects(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test that user 2 cannot see user 1's projects in list."""
        response = await client.get("/api/v1/projects", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        # User 2 should see 0 projects
        assert len(data["projects"]) == 0

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_series_bible(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test series bible isolation."""
        # User 1 creates series bible
        await client.post(
            f"/api/v1/series-bible/{test_project.id}",
            json={"premise": "Secret premise"},
            headers=auth_headers,
        )

        # User 2 tries to access
        response = await client.get(
            f"/api/v1/series-bible/{test_project.id}",
            headers=auth_headers2,
        )
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_characters(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test character isolation."""
        # User 1 creates character
        await client.post(
            f"/api/v1/characters/{test_project.id}",
            json={"name": "Secret Character"},
            headers=auth_headers,
        )

        # User 2 tries to list
        response = await client.get(
            f"/api/v1/characters/{test_project.id}",
            headers=auth_headers2,
        )
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_episodes(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test episode isolation."""
        # User 1 creates episode
        await client.post(
            f"/api/v1/episodes/{test_project.id}",
            json={"episode_number": 1, "title": "Secret Episode"},
            headers=auth_headers,
        )

        # User 2 tries to list
        response = await client.get(
            f"/api/v1/episodes/{test_project.id}",
            headers=auth_headers2,
        )
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_scenes(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test scene isolation."""
        # User 1 creates episode and scene
        ep = await client.post(
            f"/api/v1/episodes/{test_project.id}",
            json={"episode_number": 1},
            headers=auth_headers,
        )
        episode = ep.json()

        await client.post(
            f"/api/v1/scenes/{test_project.id}/episodes/{episode['id']}",
            json={"scene_number": 1, "title": "Secret Scene"},
            headers=auth_headers,
        )

        # User 2 tries to list
        response = await client.get(
            f"/api/v1/scenes/{test_project.id}/episodes/{episode['id']}",
            headers=auth_headers2,
        )
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_prompts(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test prompt isolation."""
        # User 1 creates prompt
        await client.post(
            f"/api/v1/prompts/{test_project.id}",
            json={
                "prompt_type": "character_image",
                "title": "Secret Prompt",
                "prompt_text": "secret",
            },
            headers=auth_headers,
        )

        # User 2 tries to list
        response = await client.get(
            f"/api/v1/prompts/{test_project.id}",
            headers=auth_headers2,
        )
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_google_accounts(
        self, client: AsyncClient, auth_headers, auth_headers2
    ):
        """Test Google account isolation."""
        # User 1 creates Google account
        await client.post(
            "/api/v1/google-accounts",
            json={"email": "user1@gmail.com"},
            headers=auth_headers,
        )

        # User 2 lists - should see only their own (0)
        response = await client.get("/api/v1/google-accounts", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_flow_tasks(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test Flow Bridge isolation."""
        # User 1 creates flow task
        await client.post(
            f"/api/v1/flow/{test_project.id}/tasks",
            json={"task_type": "prompt_preparation", "title": "Secret Task"},
            headers=auth_headers,
        )

        # User 2 tries to list
        response = await client.get(
            f"/api/v1/flow/{test_project.id}/tasks",
            headers=auth_headers2,
        )
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_assets(
        self, client: AsyncClient, auth_headers, auth_headers2, test_project
    ):
        """Test asset isolation."""
        # User 2 lists assets in user 1's project
        response = await client.get(
            f"/api/v1/assets/{test_project.id}",
            headers=auth_headers2,
        )
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_user_can_only_see_own_projects_after_creating_multiple(
        self, client: AsyncClient, auth_headers, auth_headers2, db
    ):
        """Test complete isolation with multiple projects per user."""
        from app.models import Project

        # User 1 creates 3 projects
        user1_projects = []
        for i in range(3):
            response = await client.post(
                "/api/v1/projects",
                json={"title": f"User1 Project {i}"},
                headers=auth_headers,
            )
            user1_projects.append(response.json())

        # User 2 creates 2 projects
        user2_projects = []
        for i in range(2):
            response = await client.post(
                "/api/v1/projects",
                json={"title": f"User2 Project {i}"},
                headers=auth_headers2,
            )
            user2_projects.append(response.json())

        # User 1 lists - should see only 3
        response = await client.get("/api/v1/projects", headers=auth_headers)
        data = response.json()
        assert len(data["projects"]) == 3
        project_titles = [p["title"] for p in data["projects"]]
        for p in user1_projects:
            assert p["title"] in project_titles
        for p in user2_projects:
            assert p["title"] not in project_titles

        # User 2 lists - should see only 2
        response = await client.get("/api/v1/projects", headers=auth_headers2)
        data = response.json()
        assert len(data["projects"]) == 2
        project_titles = [p["title"] for p in data["projects"]]
        for p in user2_projects:
            assert p["title"] in project_titles
        for p in user1_projects:
            assert p["title"] not in project_titles


class TestAccountLimit:
    """Test Google account limit enforcement."""

    @pytest.mark.asyncio
    async def test_max_20_accounts_per_user(self, client: AsyncClient, auth_headers):
        """Test that a user can connect at most 20 Google accounts."""
        # Create 20 accounts - all should succeed
        for i in range(20):
            response = await client.post(
                "/api/v1/google-accounts",
                json={"email": f"account{i}@gmail.com"},
                headers=auth_headers,
            )
            assert response.status_code == 201, f"Failed to create account {i}"

        # 21st account should fail
        response = await client.post(
            "/api/v1/google-accounts",
            json={"email": "account21@gmail.com"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "20" in response.json()["detail"] or "limit" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_account_limit_is_per_user(self, client: AsyncClient, auth_headers, auth_headers2):
        """Test that the 20 account limit is per user, not global."""
        # User 1 creates 20 accounts
        for i in range(20):
            await client.post(
                "/api/v1/google-accounts",
                json={"email": f"user1_account{i}@gmail.com"},
                headers=auth_headers,
            )

        # User 2 should also be able to create 20 accounts
        for i in range(20):
            response = await client.post(
                "/api/v1/google-accounts",
                json={"email": f"user2_account{i}@gmail.com"},
                headers=auth_headers2,
            )
            assert response.status_code == 201, f"User 2 failed to create account {i}"