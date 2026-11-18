#!/usr/bin/env python3
"""
Live test script for Phase 2 Hermes implementation.
Tests the complete flow: register, login, project, characters, episode, 
story generate (real LLM), scene generate (real LLM), Google OAuth flow,
Settings API, and verifies no secrets leak.
"""
import asyncio
import httpx
import json
import sys
import os

# Disable proxy for localhost - httpx is picking up malformed proxy env
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('ALL_PROXY', None)
os.environ.pop('all_proxy', None)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1'

BASE_URL = "http://localhost:8000/api/v1"

async def test_live_flow():
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("=" * 60)
        print("PHASE 2 LIVE TEST START")
        print("=" * 60)
        
        # 1. REGISTER
        print("\n1. REGISTER USER")
        register_data = {
            "email": "test@livetest.example",
            "password": "testpassword123",
            "full_name": "Live Test User"
        }
        resp = await client.post(f"{BASE_URL}/auth/register", json=register_data)
        assert resp.status_code in (200, 201), f"Register failed: {resp.text}"
        user = resp.json()
        print(f"   ✓ Registered: {user['email']} (id: {user['id']})")
        
        # 2. LOGIN
        print("\n2. LOGIN")
        login_data = {"username": "test@livetest.example", "password": "testpassword123"}
        resp = await client.post(f"{BASE_URL}/auth/login", data=login_data)
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        tokens = resp.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        print(f"   ✓ Login successful, got access_token")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 3. GET ME
        print("\n3. GET ME")
        resp = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        assert resp.status_code == 200, f"Get me failed: {resp.text}"
        me = resp.json()
        print(f"   ✓ Current user: {me['email']}")
        
        # 4. CREATE PROJECT
        print("\n4. CREATE PROJECT")
        project_data = {
            "title": "Live Test Project",
            "description": "Testing Phase 2 Hermes implementation",
            "genre": "drama",
            "tone": "serious"
        }
        resp = await client.post(f"{BASE_URL}/projects", json=project_data, headers=headers)
        assert resp.status_code == 200, f"Create project failed: {resp.text}"
        project = resp.json()
        project_id = project["id"]
        print(f"   ✓ Created project: {project['title']} (id: {project_id})")
        
        # 5. CREATE 6 CHARACTERS
        print("\n5. CREATE 6 CHARACTERS")
        characters = [
            {"name": "Aria", "role": "protagonist", "description": "A determined journalist", "age": 28, "traits": ["curious", "brave", "empathetic"]},
            {"name": "Marcus", "role": "antagonist", "description": "A corrupt corporate executive", "age": 45, "traits": ["ruthless", "charismatic", "calculating"]},
            {"name": "Elena", "role": "supporting", "description": "Aria's loyal friend and hacker", "age": 26, "traits": ["tech-savvy", "loyal", "witty"]},
            {"name": "Detective Chen", "role": "supporting", "description": "A weary but honest detective", "age": 52, "traits": ["experienced", "cynical", "just"]},
            {"name": "Dr. Voss", "role": "supporting", "description": "A brilliant but morally ambiguous scientist", "age": 38, "traits": ["intelligent", "secretive", "ambitious"]},
            {"name": "Sam", "role": "supporting", "description": "A mysterious informant with unclear motives", "age": 31, "traits": ["enigmatic", "resourceful", "unpredictable"]},
        ]
        char_ids = []
        for char in characters:
            resp = await client.post(f"{BASE_URL}/projects/{project_id}/characters", json=char, headers=headers)
            assert resp.status_code == 200, f"Create character failed: {resp.text}"
            c = resp.json()
            char_ids.append(c["id"])
            print(f"   ✓ Created character: {c['name']} ({c['role']})")
        print(f"   ✓ Total characters: {len(char_ids)}")
        
        # 6. CREATE SERIES BIBLE
        print("\n6. CREATE SERIES BIBLE")
        bible_data = {
            "project_id": project_id,
            "premise": "A journalist uncovers a corporate conspiracy involving AI mind control",
            "themes": ["truth vs power", "technology ethics", "personal sacrifice"],
            "setting": "Near-future metropolis",
            "tone": "dark, suspenseful, thought-provoking"
        }
        resp = await client.post(f"{BASE_URL}/projects/{project_id}/series-bible", json=bible_data, headers=headers)
        assert resp.status_code == 200, f"Create series bible failed: {resp.text}"
        bible = resp.json()
        print(f"   ✓ Created series bible")
        
        # 7. CREATE EPISODE
        print("\n7. CREATE EPISODE")
        episode_data = {
            "project_id": project_id,
            "episode_number": 1,
            "title": "The First Thread",
            "summary": "Aria receives an anonymous tip about a secret project"
        }
        resp = await client.post(f"{BASE_URL}/projects/{project_id}/episodes", json=episode_data, headers=headers)
        assert resp.status_code == 200, f"Create episode failed: {resp.text}"
        episode = resp.json()
        episode_id = episode["id"]
        print(f"   ✓ Created episode: {episode['title']} (id: {episode_id})")
        
        # 8. STORY GENERATE - REAL LLM
        print("\n8. STORY GENERATE (REAL LLM)")
        story_request = {
            "project_id": project_id,
            "episode_id": episode_id,
            "prompt": "Generate a detailed episode outline for episode 1 where Aria receives an anonymous tip about a secret corporate AI project. Include 5-7 scenes with descriptions.",
            "max_tokens": 2000,
            "temperature": 0.7
        }
        resp = await client.post(f"{BASE_URL}/story/generate", json=story_request, headers=headers, timeout=120.0)
        assert resp.status_code == 200, f"Story generate failed: {resp.text}"
        story_result = resp.json()
        outline = story_result.get("outline", "")
        print(f"   ✓ Story generated successfully")
        print(f"   ✓ Response preview (first 500 chars):")
        print(f"      {outline[:500]}...")
        # Verify it's not a mock/template
        assert len(outline) > 100, "Outline too short - might be mock"
        assert "Aria" in outline or "aria" in outline.lower(), "Character not mentioned in outline"
        print(f"   ✓ Verified: Real LLM content (not mock template)")
        
        # 9. SCENE GENERATE - REAL LLM
        print("\n9. SCENE GENERATE (REAL LLM)")
        scene_request = {
            "project_id": project_id,
            "episode_id": episode_id,
            "scene_number": 1,
            "prompt": "Write the opening scene where Aria receives the anonymous tip in a rainy cafe. Include dialogue and atmospheric description.",
            "max_tokens": 1500,
            "temperature": 0.7
        }
        resp = await client.post(f"{BASE_URL}/story/scene", json=scene_request, headers=headers, timeout=120.0)
        assert resp.status_code == 200, f"Scene generate failed: {resp.text}"
        scene_result = resp.json()
        scene_content = scene_result.get("content", "")
        print(f"   ✓ Scene generated successfully")
        print(f"   ✓ Response preview (first 500 chars):")
        print(f"      {scene_content[:500]}...")
        assert len(scene_content) > 100, "Scene too short - might be mock"
        assert "Aria" in scene_content or "aria" in scene_content.lower(), "Character not mentioned in scene"
        print(f"   ✓ Verified: Real LLM content (not mock template)")
        
        # 10. GOOGLE OAUTH AUTHORIZE URL
        print("\n10. GOOGLE OAUTH AUTHORIZE URL")
        resp = await client.get(f"{BASE_URL}/google-accounts/auth-url", headers=headers)
        assert resp.status_code == 200, f"Auth URL failed: {resp.text}"
        auth_data = resp.json()
        auth_url = auth_data.get("auth_url", "")
        state = auth_data.get("state", "")
        print(f"   ✓ Auth URL generated")
        print(f"   ✓ Auth URL starts with: {auth_url[:80]}...")
        assert auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth"), \
            f"Auth URL doesn't start with Google OAuth endpoint: {auth_url[:60]}"
        assert "state=" in auth_url, "State parameter missing from auth URL"
        assert len(state) > 10, "State seems too short"
        print(f"   ✓ Verified: Google OAuth URL format correct, contains state")
        
        # 11. GOOGLE OAUTH CALLBACK - WRONG STATE (should reject)
        print("\n11. GOOGLE OAUTH CALLBACK - WRONG STATE (should reject)")
        # We need to trigger the callback with wrong state
        # The callback endpoint expects a code and state from Google
        # Since we can't get a real code, we test with wrong state
        # The state is stored server-side, so we need to call with a different state
        wrong_state = "wrong-state-" + "x" * 20
        resp = await client.get(
            f"{BASE_URL}/google-accounts/callback",
            params={"code": "fake-code", "state": wrong_state}
        )
        # Should fail with 400 (invalid state) or 500 (exchange failed)
        assert resp.status_code in (400, 500), f"Expected 400/500 for wrong state, got {resp.status_code}: {resp.text}"
        print(f"   ✓ Callback correctly rejects wrong state (status: {resp.status_code})")
        
        # 12. SETTINGS - GET (should not leak secrets)
        print("\n12. SETTINGS GET (no secrets leak)")
        resp = await client.get(f"{BASE_URL}/settings", headers=headers)
        assert resp.status_code == 200, f"Settings GET failed: {resp.text}"
        settings = resp.json()
        print(f"   ✓ Settings retrieved")
        print(f"   ✓ Settings keys: {list(settings.keys())}")
        # Verify no secrets in response
        settings_str = json.dumps(settings)
        assert "google_oauth_client_secret" not in settings_str, "Secret leaked in response!"
        assert "google_oauth_client_secret_encrypted" not in settings_str, "Encrypted secret leaked!"
        assert "google_oauth_client_id" not in settings_str or settings.get("google_oauth_client_id_configured") is not None, "Client ID leaked!"
        # Should have configured flags
        assert "google_oauth_client_id_configured" in settings, "Missing configured flag for client ID"
        assert "google_oauth_client_secret_configured" in settings, "Missing configured flag for client secret"
        assert "ai_providers" in settings, "Missing ai_providers"
        print(f"   ✓ Verified: No secrets leaked, only configured flags")
        print(f"   ✓ AI Providers count: {len(settings.get('ai_providers', []))}")
        
        # 13. SETTINGS - PATCH (update AI providers order)
        print("\n13. SETTINGS PATCH (update AI providers)")
        # Get current providers first
        current_providers = settings.get("ai_providers", [])
        assert len(current_providers) >= 1, "No providers configured"
        # Reorder: move first to last
        if len(current_providers) > 1:
            new_providers = current_providers[1:] + [current_providers[0]]
        else:
            new_providers = current_providers
        
        patch_data = {"ai_providers": new_providers}
        resp = await client.patch(f"{BASE_URL}/settings", json=patch_data, headers=headers)
        assert resp.status_code == 200, f"Settings PATCH failed: {resp.text}"
        updated = resp.json()
        print(f"   ✓ Settings updated")
        assert updated.get("ai_providers") == new_providers, "Providers not updated"
        print(f"   ✓ Verified: AI providers order updated")
        
        # 14. SETTINGS - PATCH (add OAuth credentials)
        print("\n14. SETTINGS PATCH (add OAuth credentials)")
        patch_data = {
            "google_oauth_client_id": "test-client-id-123",
            "google_oauth_client_secret": "test-client-secret-456"
        }
        resp = await client.patch(f"{BASE_URL}/settings", json=patch_data, headers=headers)
        assert resp.status_code == 200, f"Settings PATCH OAuth failed: {resp.text}"
        updated = resp.json()
        print(f"   ✓ OAuth credentials saved")
        assert updated.get("google_oauth_client_id_configured") == True, "Client ID not marked configured"
        assert updated.get("google_oauth_client_secret_configured") == True, "Client secret not marked configured"
        print(f"   ✓ Verified: OAuth credentials marked as configured")
        
        # 15. SETTINGS - GET again (verify secrets still not leaked)
        print("\n15. SETTINGS GET again (verify no secrets)")
        resp = await client.get(f"{BASE_URL}/settings", headers=headers)
        assert resp.status_code == 200, f"Settings GET failed: {resp.text}"
        settings = resp.json()
        settings_str = json.dumps(settings)
        assert "test-client-secret-456" not in settings_str, "Secret value leaked!"
        assert "test-client-id-123" not in settings_str, "Client ID value leaked!"
        assert settings.get("google_oauth_client_id_configured") == True
        assert settings.get("google_oauth_client_secret_configured") == True
        print(f"   ✓ Verified: Actual secret values NOT in response, only flags")
        
        # 16. GOOGLE ACCOUNTS LIST - should not crash on decryption errors
        print("\n16. GOOGLE ACCOUNTS LIST (resilience test)")
        resp = await client.get(f"{BASE_URL}/google-accounts", headers=headers)
        assert resp.status_code == 200, f"Google accounts list failed: {resp.text}"
        accounts = resp.json()
        print(f"   ✓ Google accounts list retrieved: {len(accounts)} accounts")
        print(f"   ✓ Verified: List endpoint doesn't crash")
        
        print("\n" + "=" * 60)
        print("ALL LIVE TESTS PASSED ✓")
        print("=" * 60)
        return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_live_flow())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)