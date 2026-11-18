"""Browser-login path for Google Flow (Di order 2026-11-17 22:22 WIB).

Di menolak jalur Google Cloud Console ("Hrsnya login biasa. Dengan browser
masing2"). Jalur ini login ke Google dengan **email + password biasa lewat
browser (Playwright + Chromium)**, TANPA client_id / client_secret Cloud
Console. OAuth tetap ada dan tidak dihapus — jalur browser ini jalan
berdampingan dan tidak memakainya sama sekali.

Cara kerja
----------
- Satu profil browser persisten per akun:
  ``BROWSER_PROFILE_DIR/<user_id>/<account_id>/`` (Chromium user-data-dir).
  Cookie + localStorage sesi Google tersimpan di sana, jadi login cukup
  sekali; eksekusi berikutnya memakai ulang sesi bila masih hidup.
- Password dibaca dari ``GoogleAccount.password_encrypted`` (enkripsi yang
  sudah ada, via ``decrypt_data`` — cara enkripsi TIDAK diubah) dan TIDAK
  pernah ditulis ke log / file / response.
- ``PlaywrightBrowserDriver``: login Google (identifier -> password ->
  deteksi sukses / password salah / challenge 2FA-captcha), lalu buka
  Google Flow (``FLOW_URL``), isi prompt task, dan submit.
- Auto ganti akun: eksekusi memakai loop fallback yang sama dengan
  ``run_with_google_fallback`` — bila satu akun gagal karena alasan yang
  terikat akun itu (``no_password`` / ``login_failed`` /
  ``browser_challenge`` / ``session_expired`` / ``flow_blocked``), otomatis
  pindah ke akun CONNECTED berikutnya milik user yang sama; setiap
  percobaan dicatat di ``FlowTask.fallback_history``.
- Bila Playwright/Chromium tidak tersedia di mesin, eksekusi gagal jujur
  (``GoogleServiceUnavailable`` -> HTTP 502), bukan diam-diam fallback ke
  mode manual. Mode manual (export-prompts) tetap tersedia apa adanya.

Batasan jujur (baca sebelum mengandalkan jalur ini)
---------------------------------------------------
- Login Google asli dan UI Google Flow ASLI belum pernah diverifikasi di
  sini (tidak ada kredensial Google asli untuk tes). Selector form login
  Google memakai pola standar accounts.google.com; selector kotak prompt
  dan tombol Generate Flow bersifat best-effort dan BELUM terverifikasi
  terhadap UI Flow yang sebenarnya — jalankan pertama dengan akun nyata
  kemungkinan butuh penyesuaian selector.
- Google bisa memblokir otomasi browser (bot detection / captcha / 2FA):
  driver mendeteksi halaman challenge dan mengembalikan
  ``browser_challenge`` (akun itu dilewati, fallback ke akun berikut);
  bila semua akun kena challenge, task gagal jujur dengan alasan itu dan
  operator harus login manual sekali lewat browser yang sama (profil
  persisten dipakai ulang, jadi sesi manual itu langsung terpakai
  eksekusi berikutnya) atau memakai export-prompts manual.
- Setelah prompt di-submit ke Flow, task berstatus ``generating`` — video
  masih dirender di Flow; penyelesaian tetap lewat import-results yang
  sudah ada (tidak ada polling download otomatis dari Flow).
"""

import glob
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol
from urllib.parse import unquote, urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import FlowTask, GoogleAccount, GoogleAccountStatus
from app.services.google_account_fallback import (
    AllGoogleAccountsFailed,
    GoogleAccountFailure,
    GoogleServiceUnavailable,
    run_with_google_fallback,
)
from app.utils.encryption import decrypt_data

logger = logging.getLogger(__name__)

# Deteksi halaman challenge Google (2FA / captcha / verifikasi).
CHALLENGE_MARKERS = (
    "2-step verification",
    "2-step verification",
    "verify it's you",
    "verify it’s you",
    "confirm it's you",
    "enter the code",
    "recaptcha",
    "unusual traffic",
    "couldn't sign you in",
    "try again later",
)
# Deteksi pemblokiran otomasi di halaman Flow.
FLOW_BLOCK_MARKERS = (
    "unusual traffic",
    "automated",
    "couldn't verify",
    "verify you're not a robot",
    "verify you’re not a robot",
    "recaptcha",
)


def _is_network_error(exc: Exception) -> bool:
    """Playwright network failure (proxy/DNS/connect) — a machine-level
    problem, NOT this account's fault: must abort fallback (switching
    accounts cannot fix it), never masquerade as 'login rejected'."""
    msg = str(exc)
    return ("net::ERR_" in msg or "ERR_TUNNEL" in msg
            or "ERR_NAME_NOT_RESOLVED" in msg or "ERR_CONNECTION" in msg)


def _proxy_config() -> Optional[dict]:
    """Egress proxy dari env (bila ada) untuk Chromium — tanpa proxy,
    Chromium di VM ini tidak bisa mencapai Google sama sekali. Nilai proxy
    (termasuk kredensial di URL) TIDAK PERNAH di-log.

    Catatan terverifikasi: opsi ``bypass`` Playwright diabaikan Chromium di
    sini — begitu proxy diset, request ke localhost pun lewat proxy dan
    gagal (ERR_EMPTY_RESPONSE). Karena itu proxy HANYA dipakai bila target
    benar-benar eksternal (lihat ``_should_use_proxy``); URL lokal selalu
    tanpa proxy.
    """
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        return None
    cfg: dict = {"server": f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port or 3128}"}
    if parsed.username:
        cfg["username"] = unquote(parsed.username)
    if parsed.password:
        cfg["password"] = unquote(parsed.password)
    return cfg


def _should_use_proxy(*urls: str) -> bool:
    """Proxy hanya bila ada target eksternal; semua URL lokal -> tanpa proxy."""
    for url in urls:
        host = (urlparse(url).hostname or "").lower()
        if host not in ("localhost", "127.0.0.1", "::1"):
            return True
    return False


def browser_available() -> bool:
    """True bila Playwright ter-import (Chromium dicek saat launch)."""
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def find_chromium_executable() -> Optional[str]:
    """Cari binary Chromium Playwright yang sudah terunduh.

    Playwright 1.55 default memakai chromium_headless_shell-1187; bila
    belum terunduh, pakai chromium full yang ada di cache (mis. hasil
    ``playwright install chromium`` versi lain). Env
    ``PLAYWRIGHT_CHROMIUM_EXECUTABLE`` menang atas pencarian otomatis.
    """
    env_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if env_path and Path(env_path).exists():
        return env_path
    candidates = sorted(
        glob.glob(
            str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux64/chrome")
        )
    )
    return candidates[-1] if candidates else None


def profile_dir_for(user_id: UUID, account_id: UUID) -> Path:
    """Direktori profil browser persisten untuk satu akun."""
    return settings.BROWSER_PROFILE_DIR / str(user_id) / str(account_id)


def session_meta_path(user_id: UUID, account_id: UUID) -> Path:
    return profile_dir_for(user_id, account_id) / "session.json"


def read_session_meta(user_id: UUID, account_id: UUID) -> dict:
    """Metadata sesi browser (TANPA kredensial): kapan login terakhir,
    hasil cek terakhir. {} bila belum pernah login lewat browser."""
    try:
        return json.loads(session_meta_path(user_id, account_id).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_session_meta(user_id: UUID, account_id: UUID, meta: dict) -> None:
    path = session_meta_path(user_id, account_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2))


def decrypt_account_password(account: GoogleAccount) -> str:
    """Password akun dari DB terenkripsi. Tanpa password -> kegagalan yang
    terikat akun (fallback ke akun berikut, bukan error global)."""
    if not account.password_encrypted:
        raise GoogleAccountFailure(
            account.id, "no_password",
            "No browser password stored for this account "
            "(POST /settings/google/{id}/password first)",
        )
    try:
        stored = decrypt_data(account.password_encrypted)
    except Exception as e:
        raise GoogleAccountFailure(
            account.id, "login_failed", f"Failed to decrypt stored password: {e}"
        )
    password = stored.get("value", "") if isinstance(stored, dict) else ""
    if not password:
        raise GoogleAccountFailure(
            account.id, "no_password", "Stored browser password is empty"
        )
    return password


def build_flow_prompt(task: FlowTask) -> str:
    """Prompt Flow dari task: judul + deskripsi + input_prompts."""
    parts = [task.title or ""]
    if task.description:
        parts.append(task.description)
    for item in task.input_prompts or []:
        if isinstance(item, dict):
            text = item.get("prompt_text") or item.get("text") or ""
            if text:
                parts.append(str(text))
        elif isinstance(item, str):
            parts.append(item)
    return "\n\n".join(p for p in parts if p).strip()


class BrowserDriver(Protocol):
    """Antarmuka driver browser — implementasi nyata Playwright di bawah,
    fake driver di tes (tanpa jaringan / tanpa Google)."""

    async def ensure_logged_in(self, *, email: str, password: str,
                               force_relogin: bool = False) -> str:
        """'logged_in' | 'challenge' | 'login_failed'."""
        ...

    async def submit_flow_prompt(self, *, prompt_text: str) -> dict:
        ...

    async def close(self) -> None:
        ...


class PlaywrightBrowserDriver:
    """Driver Playwright nyata: profil persisten per akun + login Google
    + submit prompt ke Google Flow.

    ``login_url`` / ``account_url`` / ``flow_url`` bisa di-override (dipakai
    tes melawan halaman login lokal palsu — login Google asli tidak bisa
    diuji tanpa kredensial asli).
    """

    def __init__(self, profile_dir: Path, *, headless: Optional[bool] = None,
                 login_url: str = "https://accounts.google.com/signin/v2/identifier",
                 account_url: str = "https://myaccount.google.com/",
                 flow_url: Optional[str] = None):
        self.profile_dir = Path(profile_dir)
        self.headless = settings.BROWSER_HEADLESS if headless is None else headless
        self.login_url = login_url
        self.account_url = account_url
        self.flow_url = flow_url or settings.FLOW_URL
        self._playwright = None
        self._context = None

    async def _launch(self):
        if self._context is not None:
            return self._context
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise GoogleServiceUnavailable(
                "Playwright is not installed in this environment "
                "(pip install playwright + playwright install chromium)"
            ) from e
        self._playwright = await async_playwright().start()
        launch_kwargs: dict = {
            "headless": self.headless,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        proxy_cfg = _proxy_config() if _should_use_proxy(
            self.login_url, self.account_url, self.flow_url) else None
        if proxy_cfg:
            launch_kwargs["proxy"] = proxy_cfg
        executable = find_chromium_executable()
        if executable:
            launch_kwargs["executable_path"] = executable
        try:
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir), **launch_kwargs
            )
        except Exception as e:
            await self._playwright.stop()
            self._playwright = None
            raise GoogleServiceUnavailable(
                f"Could not launch Chromium: {e}"
            ) from e
        return self._context

    async def close(self) -> None:
        try:
            if self._context is not None:
                await self._context.close()
        finally:
            self._context = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

    async def _page_text(self, page) -> str:
        try:
            return (await page.content()).lower()
        except Exception:
            return ""

    async def _is_logged_in(self, page) -> bool:
        """Cek sesi: buka halaman akun; bila dialihkan ke form sign-in atau
        form email masih tampil -> belum login."""
        await page.goto(self.account_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        url = page.url.lower()
        if "accounts.google.com/signin" in url or "/signin" in url:
            return False
        if await page.locator('input[type="email"]:visible, #identifierId:visible').count():
            return False
        if await page.locator("#account-home, [data-logged-in]").count():
            return True
        # Tidak ada form login -> anggap sesi hidup (myaccount tampil).
        return True

    async def ensure_logged_in(self, *, email: str, password: str,
                               force_relogin: bool = False) -> str:
        try:
            return await self._ensure_logged_in_impl(
                email=email, password=password, force_relogin=force_relogin)
        except GoogleServiceUnavailable:
            raise
        except Exception as e:
            if _is_network_error(e):
                raise GoogleServiceUnavailable(
                    f"Browser could not reach Google: {e}"
                ) from e
            raise

    async def _ensure_logged_in_impl(self, *, email: str, password: str,
                                     force_relogin: bool = False) -> str:
        context = await self._launch()
        page = context.pages[0] if context.pages else await context.new_page()
        if not force_relogin and await self._is_logged_in(page):
            logger.info("Browser session already logged in, reusing profile")
            return "logged_in"

        await page.goto(self.login_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        # Langkah 1: email / identifier.
        email_input = page.locator('#identifierId:visible, input[type="email"]:visible').first
        if await email_input.count():
            await email_input.fill(email)
            next_btn = page.locator(
                '#identifierNext:visible, button:has-text("Next"):visible'
            ).first
            if await next_btn.count():
                await next_btn.click()
            await page.wait_for_timeout(1500)

        # Langkah 2: password.
        password_input = page.locator(
            'input[type="password"]:visible, input[name="Passwd"]:visible'
        ).first
        if await password_input.count():
            await password_input.fill(password)
            next_btn = page.locator(
                '#passwordNext:visible, button:has-text("Next"):visible'
            ).first
            if await next_btn.count():
                await next_btn.click()
            await page.wait_for_timeout(2000)

        text = await self._page_text(page)
        if any(m in text for m in CHALLENGE_MARKERS):
            logger.warning("Google login hit a challenge page (2FA/captcha)")
            return "challenge"
        if "wrong password" in text or "incorrect password" in text:
            return "login_failed"
        if await page.locator('input[type="password"]:visible').count():
            # Masih di form password tanpa pesan jelas -> login ditolak.
            return "login_failed"
        if await self._is_logged_in(page):
            return "logged_in"
        return "login_failed"

    async def submit_flow_prompt(self, *, prompt_text: str) -> dict:
        """Buka Flow, isi prompt, submit. Selector best-effort — UI Flow
        asli BELUM terverifikasi (lihat docstring modul)."""
        try:
            return await self._submit_flow_prompt_impl(prompt_text=prompt_text)
        except (GoogleAccountFailure, GoogleServiceUnavailable):
            raise
        except Exception as e:
            if _is_network_error(e):
                raise GoogleServiceUnavailable(
                    f"Browser could not reach Google Flow: {e}"
                ) from e
            raise

    async def _submit_flow_prompt_impl(self, *, prompt_text: str) -> dict:
        context = await self._launch()
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(self.flow_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        url = page.url.lower()
        if "accounts.google.com/signin" in url or "/signin" in url:
            raise GoogleAccountFailure(
                None, "session_expired",
                "Browser session expired: Flow redirected to Google sign-in",
            )
        text = await self._page_text(page)
        if any(m in text for m in FLOW_BLOCK_MARKERS):
            raise GoogleAccountFailure(
                None, "flow_blocked",
                "Google Flow blocked the automated browser session "
                "(bot detection / captcha)",
            )
        prompt_box = page.locator(
            'textarea[placeholder*="prompt" i]:visible, textarea:visible, '
            '[contenteditable="true"]:visible'
        ).first
        if not await prompt_box.count():
            raise GoogleAccountFailure(
                None, "flow_blocked",
                "Could not find the Flow prompt box — Flow UI may have "
                "changed (selectors unverified against real Flow UI)",
            )
        await prompt_box.fill(prompt_text)
        submit = page.locator(
            'button:has-text("Generate"), button:has-text("Create"), '
            'button[aria-label*="Generate" i], button[type="submit"]'
        ).first
        if await submit.count():
            await submit.click()
            await page.wait_for_timeout(3000)
        text = await self._page_text(page)
        if any(m in text for m in FLOW_BLOCK_MARKERS):
            raise GoogleAccountFailure(
                None, "flow_blocked",
                "Google Flow blocked the submission (bot detection / captcha)",
            )
        return {"status": "submitted", "flow_url": self.flow_url}


async def get_browser_candidate_accounts(
    db: AsyncSession, user_id: UUID, preferred_id: Optional[UUID] = None
) -> list[GoogleAccount]:
    """Kandidat jalur browser: akun milik user yang punya password tersimpan
    — TANPA syarat status OAuth CONNECTED, karena login browser tidak butuh
    token OAuth sama sekali (akun fresh DISCONNECTED + password = kandidat
    valid). Urutan: akun yang diminta dulu, lalu yang lain (terlama dulu)."""
    result = await db.execute(
        select(GoogleAccount)
        .where(GoogleAccount.user_id == user_id)
        .order_by(GoogleAccount.created_at.asc())
    )
    with_password = [a for a in result.scalars().all() if a.password_encrypted]
    if preferred_id:
        preferred = [a for a in with_password if a.id == preferred_id]
        rest = [a for a in with_password if a.id != preferred_id]
        return preferred + rest
    return with_password


def make_browser_driver(account: GoogleAccount, user_id: UUID) -> BrowserDriver:
    """Factory default (dimonkeypatch di tes dengan fake driver)."""
    return PlaywrightBrowserDriver(profile_dir_for(user_id, account.id))


async def browser_login_account(
    db: AsyncSession,
    account: GoogleAccount,
    *,
    force_relogin: bool = False,
    driver: Optional[BrowserDriver] = None,
) -> dict:
    """Login browser untuk SATU akun; kembalikan status jujur.

    Sukses -> profil sesi tersimpan + ``session.json`` ditulis, status akun
    CONNECTED. Challenge / password salah -> status ERROR + alasan, TANPA
    exception (endpoint login tunggal butuh jawaban, bukan 502).
    Tanpa password tersimpan -> ``no_password``.
    """
    own_driver = driver is None
    driver = driver or make_browser_driver(account, account.user_id)
    now = datetime.now(timezone.utc).isoformat()
    try:
        password = decrypt_account_password(account)
    except GoogleAccountFailure as e:
        if own_driver:
            await driver.close()
        account.error_message = e.detail
        account.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"account_id": str(account.id), "email": account.email,
                "logged_in": False, "reason": e.reason, "detail": e.detail}
    try:
        outcome = await driver.ensure_logged_in(
            email=account.email, password=password, force_relogin=force_relogin
        )
    except GoogleServiceUnavailable:
        raise
    except Exception as e:
        return {"account_id": str(account.id), "email": account.email,
                "logged_in": False, "reason": "login_failed",
                "detail": f"Browser login error: {e}"}
    finally:
        if own_driver:
            await driver.close()

    meta = {"email": account.email, "last_login_attempt_at": now,
            "last_outcome": outcome}
    if outcome == "logged_in":
        meta["logged_in_at"] = now
        _write_session_meta(account.user_id, account.id, meta)
        account.status = GoogleAccountStatus.CONNECTED
        account.error_message = None
        account.last_sync = datetime.now(timezone.utc)
        await db.commit()
        return {"account_id": str(account.id), "email": account.email,
                "logged_in": True, "reason": "ok",
                "profile_dir": str(profile_dir_for(account.user_id, account.id))}
    reason = ("browser_challenge" if outcome == "challenge" else "login_failed")
    detail = ("Google asked for extra verification (2FA/captcha) — manual "
              "login once in the same browser profile, or try another account"
              if outcome == "challenge" else
              "Google rejected the login (wrong password or session refused)")
    meta["reason"] = reason
    _write_session_meta(account.user_id, account.id, meta)
    account.status = GoogleAccountStatus.ERROR
    account.error_message = detail
    account.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"account_id": str(account.id), "email": account.email,
            "logged_in": False, "reason": reason, "detail": detail}


async def execute_flow_task_via_browser(
    db: AsyncSession,
    task: FlowTask,
    user_id: UUID,
    preferred_id: Optional[UUID] = None,
    *,
    force_relogin: bool = False,
    driver_factory=None,
) -> GoogleAccount:
    """Jalankan task Flow lewat browser, dengan auto ganti akun.

    Per akun: decrypt password -> login browser (profil persisten) -> submit
    prompt ke Flow. Gagal karena alasan akun -> akun berikut (riwayat di
    ``task.fallback_history``). Semua gagal -> ``AllGoogleAccountsFailed``
    (endpoint -> 502 jujur). Sukses -> task ``generating`` (video masih
    dirender di Flow; selesai via import-results). TIDAK memakai kredensial
    Cloud Console di jalur mana pun.
    """
    if not browser_available():
        raise GoogleServiceUnavailable(
            "Playwright is not installed — browser login cannot run "
            "(pip install playwright + playwright install chromium)"
        )
    prompt_text = build_flow_prompt(task)
    if not prompt_text:
        raise GoogleAccountFailure(None, "login_failed", "Task has no prompt text")

    candidates = await get_browser_candidate_accounts(db, user_id, preferred_id)
    if not candidates:
        raise AllGoogleAccountsFailed([{
            "account_id": None, "email": None,
            "result": "failed", "reason": "no_password",
            "at": datetime.now(timezone.utc).isoformat(),
        }], message="No usable Google account: no account with a stored "
                    "browser password (set it via POST "
                    "/settings/google/{account_id}/password first)")

    async def _attempt(account: GoogleAccount) -> dict:
        password = decrypt_account_password(account)
        driver = (driver_factory(account, user_id) if driver_factory is not None
                  else make_browser_driver(account, user_id))
        try:
            outcome = await driver.ensure_logged_in(
                email=account.email, password=password,
                force_relogin=force_relogin,
            )
        finally:
            await driver.close()
        if outcome == "challenge":
            raise GoogleAccountFailure(
                account.id, "browser_challenge",
                "Google asked for extra verification (2FA/captcha)",
            )
        if outcome != "logged_in":
            raise GoogleAccountFailure(
                account.id, "login_failed",
                "Google rejected the browser login",
            )
        _write_session_meta(user_id, account.id, {
            "email": account.email,
            "logged_in_at": datetime.now(timezone.utc).isoformat(),
            "last_outcome": "logged_in",
        })
        # Prompt submit memakai driver baru (profil persisten yang sama —
        # sesi login terbawa lewat user-data-dir).
        driver2 = (driver_factory(account, user_id) if driver_factory is not None
                   else make_browser_driver(account, user_id))
        try:
            result = await driver2.submit_flow_prompt(prompt_text=prompt_text)
        finally:
            await driver2.close()
        return {"mode": "browser", "flow": result}

    account, _ = await run_with_google_fallback(
        db, task, user_id, _attempt, preferred_id=preferred_id,
        candidates=candidates,
    )
    task.status = "generating"
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return account
