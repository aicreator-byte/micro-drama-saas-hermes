"""Browser-login path tests (Di order 2026-11-17 22:22 WIB).

Fake driver: login + Flow submit tanpa jaringan / tanpa Google.
Real-browser test: Playwright + Chromium sungguhan melawan halaman login
lokal palsu (halaman HTML yang meniru form login Google 2 langkah +
halaman Flow) — membuktikan mesin otomasi (launch, profil persisten,
isi form, pakai ulang sesi, submit prompt) benar-benar jalan.
Login Google ASLI tidak bisa diuji di sini (tidak ada kredensial asli).
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models import GoogleAccount, GoogleAccountStatus
from app.utils.encryption import encrypt_data
import app.services.browser_login as browser_svc
from app.services.browser_login import PlaywrightBrowserDriver

LOGIN_PAGE = """<!doctype html><html><body>
<div id="step-email">
  <input type="email" id="identifierId">
  <button id="identifierNext" onclick="document.getElementById('step-email').style.display='none';document.getElementById('step-pass').style.display='block';">Next</button>
</div>
<div id="step-pass" style="display:none">
  <input type="password" name="Passwd">
  <button id="passwordNext" onclick="localStorage.setItem('fake_logged_in','1');document.getElementById('step-pass').style.display='none';document.getElementById('account-home').style.display='block';">Next</button>
</div>
<div id="account-home" data-logged-in="1" style="display:none">My Account</div>
</body></html>"""

ACCOUNT_PAGE = """<!doctype html><html><body><script>
if (localStorage.getItem('fake_logged_in') === '1') {
  document.write('<div id="account-home" data-logged-in="1">My Account</div>');
} else {
  document.write('<input type="email" id="identifierId">');
}
</script></body></html>"""

FLOW_PAGE = """<!doctype html><html><body>
<textarea placeholder="Describe your video prompt"></textarea>
<button onclick="document.getElementById('flow-submitted').style.display='block';">Generate</button>
<div id="flow-submitted" style="display:none">submitted</div>
</body></html>"""

# Halaman akun TANPA form sign-in DAN tanpa penanda login — reproduksi bug
# false positive 2026-11-19: halaman seperti ini (kosong/error) dulu
# dianggap "logged_in" oleh _is_logged_in.
ACCOUNT_BLANK_PAGE = """<!doctype html><html><body>
<div>Welcome</div><p>Nothing here proves a login.</p>
</body></html>"""

# Halaman akun DENGAN penanda login positif.
ACCOUNT_LOGGED_IN_PAGE = """<!doctype html><html><body>
<div id="account-home" data-logged-in="1">My Account</div>
</body></html>"""


class _FakePages(BaseHTTPRequestHandler):
    def do_GET(self):
        page = {"/login": LOGIN_PAGE, "/account": ACCOUNT_PAGE,
                "/account-blank": ACCOUNT_BLANK_PAGE,
                "/account-logged-in": ACCOUNT_LOGGED_IN_PAGE,
                "/flow": FLOW_PAGE}.get(self.path, "<html><body>404</body></html>")
        body = page.encode()
        self.send_response(200 if self.path in ("/login", "/account", "/account-blank",
                                                "/account-logged-in", "/flow") else 404)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def fake_google_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakePages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def _isolate_profiles(tmp_path, monkeypatch):
    """Profil browser tes di tmp, bukan dir produksi."""
    monkeypatch.setattr(settings, "BROWSER_PROFILE_DIR", tmp_path / "profiles")


class FakeDriver:
    """Driver palsu: hasil login + submit diatur per email."""

    def __init__(self, outcomes, submitted=None):
        self.outcomes = outcomes  # email -> "logged_in" | "challenge" | "login_failed"
        self.submitted = submitted if submitted is not None else []
        self.closed = 0

    async def ensure_logged_in(self, *, email, password, force_relogin=False):
        return self.outcomes.get(email, "logged_in")

    async def submit_flow_prompt(self, *, prompt_text):
        self.submitted.append(prompt_text)
        return {"status": "submitted", "flow_url": "fake://flow"}

    async def close(self):
        self.closed += 1


def _fake_factory(outcomes, submitted=None):
    def factory(account, user_id):
        return FakeDriver(outcomes, submitted)
    return factory


async def _make_account(db, user, email, password="pw-secret", status=GoogleAccountStatus.CONNECTED):
    account = GoogleAccount(
        user_id=user.id, email=email, display_name=email, status=status,
        session_data=encrypt_data({"tokens": {"access_token": "tok", "refresh_token": "rt"}}),
        password_encrypted=encrypt_data({"value": password}) if password else None,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def _make_task(client, auth_headers, project, account_id=None):
    payload = {"task_type": "video_generation", "title": "Browser login test task",
               "description": "a cat detective", "input_prompts": [{"prompt_text": "cat detective noir"}]}
    if account_id:
        payload["google_account_id"] = str(account_id)
    resp = await client.post(f"/api/v1/flow/{project.id}/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_browser_login_endpoint_success(client, auth_headers, test_user, db, monkeypatch):
    """Login browser sukses -> logged_in, session.json tersimpan."""
    a = await _make_account(db, test_user, "b1@gmail.com")
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        lambda account, user_id: FakeDriver({"b1@gmail.com": "logged_in"}))
    resp = await client.post(f"/api/v1/google-accounts/{a.id}/browser-login",
                             json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["logged_in"] is True and data["reason"] == "ok"
    meta_path = Path(settings.BROWSER_PROFILE_DIR) / str(test_user.id) / str(a.id) / "session.json"
    assert meta_path.exists()
    assert "logged_in_at" in meta_path.read_text()


@pytest.mark.asyncio
async def test_browser_login_no_password(client, auth_headers, test_user, db, monkeypatch):
    """Tanpa password tersimpan -> logged_in False, reason no_password."""
    a = await _make_account(db, test_user, "b2@gmail.com", password=None)
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        lambda account, user_id: FakeDriver({}))
    resp = await client.post(f"/api/v1/google-accounts/{a.id}/browser-login",
                             json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["logged_in"] is False
    assert resp.json()["reason"] == "no_password"


@pytest.mark.asyncio
async def test_browser_login_challenge(client, auth_headers, test_user, db, monkeypatch):
    """Challenge 2FA/captcha -> logged_in False, reason browser_challenge."""
    a = await _make_account(db, test_user, "b3@gmail.com")
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        lambda account, user_id: FakeDriver({"b3@gmail.com": "challenge"}))
    resp = await client.post(f"/api/v1/google-accounts/{a.id}/browser-login",
                             json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["reason"] == "browser_challenge"


@pytest.mark.asyncio
async def test_browser_session_endpoint(client, auth_headers, test_user, db, monkeypatch):
    """GET browser-session: has_password + profil ada setelah login."""
    a = await _make_account(db, test_user, "b4@gmail.com")
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        lambda account, user_id: FakeDriver({"b4@gmail.com": "logged_in"}))
    await client.post(f"/api/v1/google-accounts/{a.id}/browser-login",
                      json={}, headers=auth_headers)
    resp = await client.get(f"/api/v1/google-accounts/{a.id}/browser-session",
                            headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["has_password"] is True
    assert data["profile_exists"] is True
    assert data["session"]["last_outcome"] == "logged_in"


@pytest.mark.asyncio
async def test_execute_browser_challenge_then_success(client, auth_headers, test_project, test_user, db, monkeypatch):
    """Akun 1 kena challenge -> OTOMATIS pindah akun 2 -> generating."""
    a1 = await _make_account(db, test_user, "c1@gmail.com")
    a2 = await _make_account(db, test_user, "c2@gmail.com")
    submitted = []
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        _fake_factory({"c1@gmail.com": "challenge", "c2@gmail.com": "logged_in"}, submitted))
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(
        f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute-browser",
        json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "generating"
    assert data["active_account_id"] == str(a2.id)
    assert data["google_account_id"] == str(a2.id)
    history = data["fallback_history"]
    assert [h["result"] for h in history] == ["failed", "succeeded"]
    assert history[0]["reason"] == "browser_challenge"
    assert history[0]["email"] == "c1@gmail.com"
    assert history[1]["email"] == "c2@gmail.com"
    assert submitted and "cat detective noir" in submitted[0]


@pytest.mark.asyncio
async def test_execute_browser_all_fail_honest_error(client, auth_headers, test_project, test_user, db, monkeypatch):
    """Semua akun login ditolak -> 502 jujur, task failed, alasan per akun."""
    a1 = await _make_account(db, test_user, "d1@gmail.com")
    a2 = await _make_account(db, test_user, "d2@gmail.com")
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        _fake_factory({"d1@gmail.com": "login_failed", "d2@gmail.com": "login_failed"}))
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(
        f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute-browser",
        json={}, headers=auth_headers)
    assert resp.status_code == 502, resp.text
    assert "d1@gmail.com" in resp.json()["detail"] and "d2@gmail.com" in resp.json()["detail"]
    got = await client.get(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}", headers=auth_headers)
    data = got.json()
    assert data["status"] == "failed"
    assert {h["email"]: h["reason"] for h in data["fallback_history"]} == {
        "d1@gmail.com": "login_failed", "d2@gmail.com": "login_failed"}


@pytest.mark.asyncio
async def test_execute_browser_no_password_all(client, auth_headers, test_project, test_user, db, monkeypatch):
    """Semua akun tanpa password -> 502, reason no_password per akun."""
    a1 = await _make_account(db, test_user, "e1@gmail.com", password=None)
    await _make_account(db, test_user, "e2@gmail.com", password=None)
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        lambda account, user_id: FakeDriver({}))
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(
        f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute-browser",
        json={}, headers=auth_headers)
    assert resp.status_code == 502, resp.text
    assert "stored browser password" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_execute_browser_disconnected_account_with_password_is_candidate(
        client, auth_headers, test_project, test_user, db, monkeypatch):
    """Akun DISCONNECTED (tanpa OAuth) + password tersimpan TETAP kandidat
    jalur browser — login browser tidak butuh token OAuth."""
    a = await _make_account(db, test_user, "g1@gmail.com",
                            status=GoogleAccountStatus.DISCONNECTED)
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        _fake_factory({"g1@gmail.com": "logged_in"}))
    task = await _make_task(client, auth_headers, test_project, a.id)
    resp = await client.post(
        f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute-browser",
        json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "generating"
    assert resp.json()["active_account_id"] == str(a.id)


class NetworkDownDriver(FakeDriver):
    async def ensure_logged_in(self, *, email, password, force_relogin=False):
        from app.services.google_account_fallback import GoogleServiceUnavailable
        raise GoogleServiceUnavailable("Browser could not reach Google: net::ERR_TUNNEL_CONNECTION_FAILED")


@pytest.mark.asyncio
async def test_execute_browser_network_error_aborts_without_fallback(
        client, auth_headers, test_project, test_user, db, monkeypatch):
    """Browser tidak bisa mencapai Google (proxy/DNS) -> 502, akun berikut
    TIDAK dicoba (ganti akun tidak bisa memperbaiki jaringan)."""
    a1 = await _make_account(db, test_user, "h1@gmail.com")
    await _make_account(db, test_user, "h2@gmail.com")
    monkeypatch.setattr(browser_svc, "make_browser_driver",
                        lambda account, user_id: NetworkDownDriver({}))
    task = await _make_task(client, auth_headers, test_project, a1.id)
    resp = await client.post(
        f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute-browser",
        json={}, headers=auth_headers)
    assert resp.status_code == 502, resp.text
    assert "could not reach Google" in resp.json()["detail"]
    got = await client.get(f"/api/v1/flow/{test_project.id}/tasks/{task['id']}", headers=auth_headers)
    assert got.json()["status"] == "failed"
    assert got.json()["fallback_history"] == []


@pytest.mark.asyncio
async def test_real_chromium_login_and_flow_submit(fake_google_server, tmp_path):
    """Browser SUNGGUHAN (Chromium Playwright) vs halaman login lokal palsu:
    isi form 2 langkah -> login sukses -> launch kedua pakai ulang sesi
    (tanpa isi form lagi) -> submit prompt Flow -> marker submitted muncul."""
    profile = tmp_path / "real-profile"
    driver = PlaywrightBrowserDriver(
        profile,
        login_url=f"{fake_google_server}/login",
        account_url=f"{fake_google_server}/account",
        flow_url=f"{fake_google_server}/flow",
    )
    try:
        assert await driver.ensure_logged_in(email="real@test.com", password="pw") == "logged_in"
        result = await driver.submit_flow_prompt(prompt_text="cat detective noir")
        assert result["status"] == "submitted"
        page = driver._context.pages[0]
        assert await page.locator("#flow-submitted:visible").count() == 1
    finally:
        await driver.close()

    # Launch kedua, profil sama: sesi dipakai ulang tanpa login ulang.
    driver2 = PlaywrightBrowserDriver(
        profile,
        login_url=f"{fake_google_server}/login",
        account_url=f"{fake_google_server}/account",
        flow_url=f"{fake_google_server}/flow",
    )
    try:
        assert await driver2.ensure_logged_in(email="real@test.com", password="pw") == "logged_in"
    finally:
        await driver2.close()


@pytest.mark.asyncio
async def test_is_logged_in_requires_positive_evidence(fake_google_server, tmp_path):
    """False positive 2026-11-19: _is_logged_in dulu default True bila
    halaman tidak menunjukkan form sign-in maupun penanda login, sehingga
    akun palsu tercatat "logged_in" tanpa pernah login. Sekarang login
    HANYA bila ada bukti positif (penanda akun); halaman tanpa bukti
    apapun -> False, halaman dengan penanda login -> True."""
    blank = PlaywrightBrowserDriver(
        tmp_path / "blank-profile",
        login_url=f"{fake_google_server}/login",
        account_url=f"{fake_google_server}/account-blank",
        flow_url=f"{fake_google_server}/flow",
    )
    try:
        context = await blank._launch()
        page = context.pages[0] if context.pages else await context.new_page()
        assert await blank._is_logged_in(page) is False
    finally:
        await blank.close()

    logged_in = PlaywrightBrowserDriver(
        tmp_path / "logged-in-profile",
        login_url=f"{fake_google_server}/login",
        account_url=f"{fake_google_server}/account-logged-in",
        flow_url=f"{fake_google_server}/flow",
    )
    try:
        context = await logged_in._launch()
        page = context.pages[0] if context.pages else await context.new_page()
        assert await logged_in._is_logged_in(page) is True
    finally:
        await logged_in.close()


@pytest.mark.asyncio
async def test_execute_browser_real_chromium_end_to_end(
        client, auth_headers, test_project, test_user, db, monkeypatch, fake_google_server):
    """Endpoint execute-browser dengan Chromium sungguhan vs halaman palsu:
    200 generating, akun aktif tercatat, riwayat succeeded."""
    a = await _make_account(db, test_user, "f1@gmail.com")
    base = fake_google_server

    def real_factory(account, user_id):
        return PlaywrightBrowserDriver(
            browser_svc.profile_dir_for(test_user.id, account.id),
            login_url=f"{base}/login",
            account_url=f"{base}/account",
            flow_url=f"{base}/flow",
        )
    monkeypatch.setattr(browser_svc, "make_browser_driver", real_factory)
    task = await _make_task(client, auth_headers, test_project, a.id)
    resp = await client.post(
        f"/api/v1/flow/{test_project.id}/tasks/{task['id']}/execute-browser",
        json={}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "generating"
    assert data["active_account_id"] == str(a.id)
    assert data["fallback_history"][-1]["result"] == "succeeded"
