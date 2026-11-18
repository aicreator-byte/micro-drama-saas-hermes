"""Google-account fallback tests for Flow Bridge (Di order 2026-11-17).

Fake Google HTTP client: tokeninfo answers per access_token, refresh is
never reached (no OAuth credentials in test DB -> refresh returns None).
"""
import pytest
from httpx import AsyncClient

from app.models import GoogleAccount, GoogleAccountStatus, FlowTask
from app.utils.encryption import encrypt_data
import app.services.google_account_fallback as fallback_svc


class FakeResponse:
    def __init__(self, status_code, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data or {}

    def json(self):
        return self._json


class FakeGoogleClient:
    """tokeninfo verdict per access_token; refresh always fails."""

    def __init__(self, verdicts):
        self.verdicts = verdicts  # access_token -> (status, text)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        token = (params or {}).get("access_token")
        status, text = self.verdicts.get(token, (400, "invalid_token"))
        return FakeResponse(status, text, {"expires_in": 3600} if status == 200 else {})

    async def post(self, url, data=None):
        return FakeResponse(400, '{"error": "invalid_grant"}')


async def _make_account(db, user, email, token, status=GoogleAccountStatus.CONNECTED):
    account = GoogleAccount(
        user_id=user.id,
        email=email,
        display_name=email,
        status=status,
        session_data=encrypt_data({"tokens": {"access_token": token, "refresh_token": f"rt-{token}"}}),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def _make_task(client, auth_headers, project, account_id=None):
    payload = {"task_type": "video_generation", "title": "Fallback test task"}
    if account_id:
        payload["google_account_id"] = str(account_id)
    resp = await client.post(f"/api/v1/flow/{project.id}/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_fallback_first_fails_second_succeeds(client, auth_headers, test_project, test_user, db, monkeypatch):
    """Akun 1 token invalid -> pindah ke akun 2 -> berhasil."""
    a1 = await _make_account(db, test_user, "a1@gmail.com", "bad-token-1")
    a2 = await _make_account(db, test_user, "a2@gmail.com", "good-token-2")
    monkeypatch.setattr(
        fallback_svc, "get_google_http_client",
        lambda: FakeGoogleClient({"bad-token-1": (400, "invalid_token"), "good-token-2": (200, "")}),
    )
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "generating"
    assert data["active_account_id"] == str(a2.id)
    assert data["google_account_id"] == str(a2.id)
    assert data["error_message"] is None
    history = data["fallback_history"]
    assert [h["result"] for h in history] == ["failed", "succeeded"]
    assert history[0]["reason"] == "refresh_failed"  # invalid + refresh gagal (tanpa kreds OAuth)
    assert history[0]["email"] == "a1@gmail.com"
    assert history[1]["email"] == "a2@gmail.com"


@pytest.mark.asyncio
async def test_all_accounts_fail_honest_error(client, auth_headers, test_project, test_user, db, monkeypatch):
    """Semua akun gagal -> 502 jujur, task failed, alasan per akun tercatat."""
    a1 = await _make_account(db, test_user, "a1@gmail.com", "quota-token-1")
    a2 = await _make_account(db, test_user, "a2@gmail.com", "bad-token-2")
    monkeypatch.setattr(
        fallback_svc, "get_google_http_client",
        lambda: FakeGoogleClient({
            "quota-token-1": (429, "quota exceeded for this account"),
            "bad-token-2": (400, "invalid_token"),
        }),
    )
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute", headers=auth_headers)
    assert resp.status_code == 502, resp.text
    assert "a1@gmail.com" in resp.json()["detail"] and "a2@gmail.com" in resp.json()["detail"]
    got = await client.get(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}", headers=auth_headers)
    data = got.json()
    assert data["status"] == "failed"
    assert "a1@gmail.com" in data["error_message"] and "a2@gmail.com" in data["error_message"]
    reasons = {h["email"]: h["reason"] for h in data["fallback_history"]}
    assert reasons["a1@gmail.com"] == "quota_exceeded"
    assert reasons["a2@gmail.com"] == "refresh_failed"
    assert all(h["result"] == "failed" for h in data["fallback_history"])


@pytest.mark.asyncio
async def test_create_task_auto_picks_first_usable(client, auth_headers, test_project, test_user, db):
    """Tanpa google_account_id -> task otomatis terikat ke akun CONNECTED pertama."""
    a1 = await _make_account(db, test_user, "a1@gmail.com", "tok-1")
    await _make_account(db, test_user, "a2@gmail.com", "tok-2")
    task = await _make_task(client, auth_headers, test_project)
    assert task["google_account_id"] == str(a1.id)
    assert task["active_account_id"] == str(a1.id)
    assert task["fallback_history"] == []


@pytest.mark.asyncio
async def test_execute_no_usable_account(client, auth_headers, test_project, test_user, db):
    """Tanpa akun CONNECTED sama sekali -> 502 jujur, bukan diam-diam gagal."""
    await _make_account(db, test_user, "off@gmail.com", "tok-1", status=GoogleAccountStatus.DISCONNECTED)
    task = await _make_task(client, auth_headers, test_project)
    assert task["active_account_id"] is None
    resp = await client.post(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute", headers=auth_headers)
    assert resp.status_code == 502
    assert "No usable Google account" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_retry_after_failure_uses_fallback(client, auth_headers, test_project, test_user, db, monkeypatch):
    """Task failed -> retry manual -> fallback jalan, riwayat ditambah (tidak dihapus)."""
    a1 = await _make_account(db, test_user, "a1@gmail.com", "bad-token-1")
    a2 = await _make_account(db, test_user, "a2@gmail.com", "good-token-2")
    fake = FakeGoogleClient({"bad-token-1": (400, "invalid_token"), "good-token-2": (400, "invalid_token")})
    monkeypatch.setattr(fallback_svc, "get_google_http_client", lambda: fake)
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute", headers=auth_headers)
    assert resp.status_code == 502
    # Akun 2 ternyata pulih -> retry harus berhasil via fallback.
    fake.verdicts["good-token-2"] = (200, "")
    resp = await client.post(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/retry", json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "generating"
    assert data["active_account_id"] == str(a2.id)
    assert len(data["fallback_history"]) == 4  # 2 gagal (run 1) + gagal+sukses (retry)
    assert data["error_message"] is None


@pytest.mark.asyncio
async def test_retry_non_failed_task_is_409(client, auth_headers, test_project, test_user, db):
    a1 = await _make_account(db, test_user, "a1@gmail.com", "tok-1")
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/retry", json={}, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_fallback_never_tries_other_users_accounts(
    client, auth_headers, test_project, test_user, test_user2, db, monkeypatch
):
    """Fallback hanya pakai akun milik user yang sama."""
    a1 = await _make_account(db, test_user, "mine@gmail.com", "bad-token-1")
    await _make_account(db, test_user2, "theirs@gmail.com", "good-token-2")
    monkeypatch.setattr(
        fallback_svc, "get_google_http_client",
        lambda: FakeGoogleClient({"bad-token-1": (400, "invalid_token"), "good-token-2": (200, "")}),
    )
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute", headers=auth_headers)
    assert resp.status_code == 502
    got = await client.get(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}", headers=auth_headers)
    emails = [h["email"] for h in got.json()["fallback_history"]]
    assert emails == ["mine@gmail.com"]
