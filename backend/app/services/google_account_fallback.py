"""Google-account fallback for Flow Bridge tasks.

Mirrors the AI-provider fallback pattern in ``ai_client.py`` (try candidates
in order, move on the next one when the current one fails for an
account-specific reason, honest error when all are exhausted) — but for
Google accounts instead of LLM providers.

Scope note: there is no automated Flow video execution in this codebase yet
(Flow tasks are a tracker + export-prompts / import-results). The per-account
"attempt" here is therefore the step that actually binds a task to a Google
account and can fail per account: validating the stored OAuth token against
Google (tokeninfo), refreshing it when expired. When real Flow automation
lands, its per-account call should be passed in as ``attempt`` to
``run_with_google_fallback`` instead of ``validate_account_token``.

Account-specific failures (trigger fallback): quota_exceeded / rate_limited
(429, quota text), token_invalid (401 / invalid_token), refresh_failed,
no_token. NOT account-specific (abort immediately, no fallback): Google
unreachable / 5xx / network errors — switching accounts cannot fix those.
"""

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FlowTask, GoogleAccount, GoogleAccountStatus
from app.utils.encryption import decrypt_data, encrypt_data

logger = logging.getLogger(__name__)

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Reasons that are tied to ONE account -> try the next account.
ACCOUNT_SPECIFIC_REASONS = frozenset({
    "quota_exceeded",
    "rate_limited",
    "token_invalid",
    "refresh_failed",
    "no_token",
    # Browser-login path (Di order 2026-11-17 22:22 WIB): a failure tied to
    # one account's browser session / credentials -> try the next account.
    "no_password",
    "login_failed",
    "browser_challenge",
    "session_expired",
    "flow_blocked",
})


class GoogleAccountFailure(Exception):
    """One Google account cannot be used for this task."""

    def __init__(self, account_id: Optional[UUID], reason: str, detail: str = ""):
        self.account_id = account_id
        self.reason = reason
        self.detail = detail or reason
        super().__init__(f"Google account {account_id}: {reason} — {self.detail}")

    @property
    def is_account_specific(self) -> bool:
        return self.reason in ACCOUNT_SPECIFIC_REASONS


class AllGoogleAccountsFailed(Exception):
    """Every candidate Google account failed; carries the honest per-account log."""

    def __init__(self, attempts: list[dict], message: Optional[str] = None):
        self.attempts = attempts
        if message is None:
            summary = "; ".join(
                f"{a.get('email') or a.get('account_id')}: {a.get('reason')}"
                for a in attempts
            )
            message = f"All Google accounts failed — {summary}"
        super().__init__(message)


class GoogleServiceUnavailable(Exception):
    """Google itself (not one account) is unreachable / erroring."""


def get_google_http_client() -> httpx.AsyncClient:
    """httpx client for Google calls. Monkeypatchable in tests."""
    from app.api.google_accounts import _google_client
    return _google_client()


def classify_http_failure(status_code: int, body: str) -> Optional[str]:
    """Map an HTTP failure from Google to a fallback reason, or None if it
    is not account-specific (caller must abort, not fall back)."""
    text = (body or "").lower()
    if status_code == 429 or "quota" in text or "rate limit" in text:
        return "quota_exceeded" if "quota" in text else "rate_limited"
    if status_code in (401, 403) or "invalid_token" in text or "invalid_grant" in text:
        return "token_invalid"
    return None  # 5xx / anything else: Google-side, not this account


def _history_entry(account: GoogleAccount, result: str, reason: str) -> dict:
    return {
        "account_id": str(account.id),
        "email": account.email,
        "result": result,
        "reason": reason,
        "at": datetime.now(timezone.utc).isoformat(),
    }


def decrypt_tokens(account: GoogleAccount) -> dict:
    """Return the stored token dict, or raise an account-specific failure."""
    if not account.session_data:
        raise GoogleAccountFailure(account.id, "no_token", "No session data stored")
    try:
        session_data = decrypt_data(account.session_data)
    except Exception as e:
        raise GoogleAccountFailure(account.id, "token_invalid", f"Failed to decrypt session data: {e}")
    tokens = session_data.get("tokens", {}) if isinstance(session_data, dict) else {}
    if not tokens.get("access_token") and not tokens.get("refresh_token"):
        raise GoogleAccountFailure(account.id, "no_token", "No access or refresh token in session data")
    return tokens


def is_locally_usable(account: GoogleAccount) -> bool:
    """Cheap local check (no network): CONNECTED + decryptable tokens present."""
    if account.status != GoogleAccountStatus.CONNECTED:
        return False
    try:
        decrypt_tokens(account)
        return True
    except GoogleAccountFailure:
        return False


async def get_candidate_accounts(
    db: AsyncSession, user_id: UUID, preferred_id: Optional[UUID] = None
) -> list[GoogleAccount]:
    """Candidate accounts for fallback, in try order: preferred first, then
    the user's other CONNECTED accounts (oldest first — stable, like the
    LLM provider priority order). Only accounts owned by this user."""
    result = await db.execute(
        select(GoogleAccount)
        .where(GoogleAccount.user_id == user_id)
        .order_by(GoogleAccount.created_at.asc())
    )
    accounts = result.scalars().all()
    connected = [a for a in accounts if a.status == GoogleAccountStatus.CONNECTED]
    if preferred_id:
        preferred = [a for a in connected if a.id == preferred_id]
        rest = [a for a in connected if a.id != preferred_id]
        return preferred + rest
    return connected


async def _refresh_tokens(db: AsyncSession, account: GoogleAccount, refresh_token: str) -> Optional[dict]:
    """Exchange refresh_token for new tokens. None = refresh failed (or no
    OAuth credentials configured — same outcome, no exception). Persists the
    new tokens on success."""
    try:
        from app.api.google_accounts import _get_oauth_credentials
        client_id, client_secret = await _get_oauth_credentials(db)
    except Exception:
        return None
    try:
        async with get_google_http_client() as client:
            resp = await client.post(TOKEN_URL, data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            })
    except httpx.HTTPError as e:
        raise GoogleServiceUnavailable(f"Google token refresh unreachable: {e}")
    if resp.status_code != 200:
        return None
    new_tokens = resp.json()
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    session_data = decrypt_data(account.session_data)
    session_data["tokens"] = new_tokens
    account.session_data = encrypt_data(session_data)
    account.status = GoogleAccountStatus.CONNECTED
    account.error_message = None
    return new_tokens


async def validate_account_token(
    db: AsyncSession, account: GoogleAccount, client: Optional[httpx.AsyncClient] = None
) -> dict:
    """Attempt to use one account: validate its access token with Google,
    refreshing when expired. Returns the usable token dict.
    Raises GoogleAccountFailure (account-specific -> fall back) or
    GoogleServiceUnavailable (Google-side -> abort, do not fall back)."""
    tokens = decrypt_tokens(account)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not access_token:
        if not refresh_token:
            raise GoogleAccountFailure(account.id, "no_token", "No access token")
        new_tokens = await _refresh_tokens(db, account, refresh_token)
        if new_tokens is None:
            raise GoogleAccountFailure(account.id, "refresh_failed", "Token refresh failed")
        return new_tokens

    async def _tokeninfo(c: httpx.AsyncClient):
        return await c.get(TOKENINFO_URL, params={"access_token": access_token})

    try:
        if client is not None:
            response = await _tokeninfo(client)
        else:
            async with get_google_http_client() as c:
                response = await _tokeninfo(c)
    except httpx.HTTPError as e:
        raise GoogleServiceUnavailable(f"Google tokeninfo unreachable: {e}")

    if response.status_code == 200:
        return tokens
    reason = classify_http_failure(response.status_code, response.text)
    if reason == "token_invalid" and refresh_token:
        new_tokens = await _refresh_tokens(db, account, refresh_token)
        if new_tokens is not None:
            return new_tokens
        raise GoogleAccountFailure(account.id, "refresh_failed", "Access token expired and refresh failed")
    if reason is not None:
        raise GoogleAccountFailure(account.id, reason, f"Token validation failed: {response.text[:200]}")
    # 5xx / unexpected: Google-side problem, switching accounts won't help.
    raise GoogleServiceUnavailable(
        f"Google token validation failed with HTTP {response.status_code}: {response.text[:200]}"
    )


async def run_with_google_fallback(
    db: AsyncSession,
    task: FlowTask,
    user_id: UUID,
    attempt: Callable[[GoogleAccount], Awaitable[dict]],
    preferred_id: Optional[UUID] = None,
    candidates: Optional[list[GoogleAccount]] = None,
) -> tuple[GoogleAccount, dict]:
    """Try ``attempt`` on each candidate account in order (same loop shape as
    ``AIClient.chat_completion``). Records every try in
    ``task.fallback_history``, moves ``task.active_account_id`` /
    ``task.google_account_id`` to the account that worked, and on total
    failure marks the task failed with an honest per-account error and raises
    ``AllGoogleAccountsFailed``. Commits once at the end of each outcome.

    ``candidates`` overrides the default list (CONNECTED accounts) — the
    browser-login path passes accounts with a stored password instead,
    regardless of OAuth status (browser login does not need OAuth tokens).
    """
    if candidates is None:
        candidates = await get_candidate_accounts(db, user_id, preferred_id)
    history: list[dict] = list(task.fallback_history or [])
    if not candidates:
        task.status = "failed"
        task.error_message = "No usable Google account: no CONNECTED account with valid tokens"
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        raise AllGoogleAccountsFailed([{
            "account_id": None, "email": None,
            "result": "failed", "reason": "no_usable_account",
            "at": datetime.now(timezone.utc).isoformat(),
        }], message="No usable Google account: no CONNECTED account with valid tokens")

    last_failure: Optional[GoogleAccountFailure] = None
    for account in candidates:
        try:
            logger.info(f"Flow task {task.id}: trying Google account {account.email}")
            result = await attempt(account)
            history.append(_history_entry(account, "succeeded", "ok"))
            task.fallback_history = history
            task.active_account_id = account.id
            task.google_account_id = account.id
            task.error_message = None
            await db.commit()
            logger.info(f"Flow task {task.id}: Google account {account.email} succeeded")
            return account, result
        except GoogleAccountFailure as e:
            if not e.is_account_specific:
                history.append(_history_entry(account, "failed", e.reason))
                task.fallback_history = history
                await db.commit()
                raise
            logger.warning(f"Flow task {task.id}: account {account.email} failed ({e.reason}), trying next")
            history.append(_history_entry(account, "failed", e.reason))
            last_failure = e
            continue

    # Every candidate failed for an account-specific reason: honest error.
    task.fallback_history = history
    task.status = "failed"
    task.error_message = (
        "All Google accounts failed: "
        + "; ".join(f"{h['email']}: {h['reason']}" for h in history if h["result"] == "failed")
    )
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()
    raise AllGoogleAccountsFailed([h for h in history if h["result"] == "failed"])


async def execute_flow_task(
    db: AsyncSession,
    task: FlowTask,
    user_id: UUID,
    preferred_id: Optional[UUID] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> GoogleAccount:
    """Bind a Flow task to a working Google account (validating + refreshing
    its token), falling back automatically to the next account on
    quota/token/refresh failure. On success the task is marked ``generating``
    (account ready — actual video generation still happens via Flow, tracked
    through export-prompts / import-results)."""
    async def _attempt(account: GoogleAccount) -> dict:
        return await validate_account_token(db, account, client=client)

    account, _ = await run_with_google_fallback(
        db, task, user_id, _attempt, preferred_id=preferred_id
    )
    task.status = "generating"
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return account
