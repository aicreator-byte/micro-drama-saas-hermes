from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.models import User, GoogleAccount, GoogleAccountStatus, Project, AppSettings
from app.schemas import GoogleAccountCreate, GoogleAccountUpdate, GoogleAccountResponse, GoogleAccountPasswordUpdate, BrowserLoginRequest
from app.utils.encryption import encrypt_data, decrypt_data
from app.services.browser_login import (
    browser_login_account,
    read_session_meta,
    profile_dir_for,
)
import httpx
import secrets

router = APIRouter(prefix="/google-accounts", tags=["google-accounts"])


# Helper to get OAuth credentials from settings
async def _get_oauth_credentials(db: AsyncSession) -> tuple[str, str]:
    """Get decrypted OAuth client_id and client_secret from AppSettings."""
    result = await db.execute(select(AppSettings))
    app_settings = result.scalar_one_or_none()
    if not app_settings or not app_settings.google_oauth_client_id_encrypted or not app_settings.google_oauth_client_secret_encrypted:
        raise HTTPException(status_code=400, detail="Google OAuth credentials not configured in settings")

    try:
        client_id_data = decrypt_data(app_settings.google_oauth_client_id_encrypted)
        client_secret_data = decrypt_data(app_settings.google_oauth_client_secret_encrypted)
        return client_id_data.get("value", ""), client_secret_data.get("value", "")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")


# Helper to get redirect URI (configurable via env GOOGLE_OAUTH_REDIRECT_URI)
def _get_redirect_uri() -> str:
    return settings.GOOGLE_OAUTH_REDIRECT_URI


def _google_client() -> httpx.AsyncClient:
    """httpx client for Google calls, same proxy/CA handling as ai_client."""
    from app.services.ai_client import _get_client_config
    return httpx.AsyncClient(**_get_client_config())


@router.post("", response_model=GoogleAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_google_account(
    account_data: GoogleAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check account limit
    count_result = await db.execute(
        select(func.count(GoogleAccount.id)).where(GoogleAccount.user_id == current_user.id)
    )
    count = count_result.scalar() or 0
    if count >= settings.MAX_GOOGLE_ACCOUNTS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_GOOGLE_ACCOUNTS_PER_USER} Google accounts per user"
        )

    # Check if email already connected
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.user_id == current_user.id,
            GoogleAccount.email == account_data.email
        ))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="This email is already connected")

    account = GoogleAccount(
        user_id=current_user.id,
        email=account_data.email,
        display_name=account_data.display_name,
        session_data=None,
        status=GoogleAccountStatus.DISCONNECTED,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("", response_model=List[GoogleAccountResponse])
async def list_google_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(
        select(GoogleAccount).where(GoogleAccount.user_id == current_user.id)
        .order_by(GoogleAccount.created_at.desc())
    )
    accounts = result.scalars().all()
    # NOTE: session_data (tokens) is encrypted at rest and is NEVER returned
    # to clients — GoogleAccountResponse carries no session_data field.
    return accounts


@router.get("/{account_id}", response_model=GoogleAccountResponse)
async def get_google_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    return account


@router.patch("/{account_id}", response_model=GoogleAccountResponse)
async def update_google_account(
    account_id: UUID,
    account_data: GoogleAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    update_data = account_data.model_dump(exclude_unset=True)

    # Encrypt session data if provided
    if "session_data" in update_data and update_data["session_data"]:
        update_data["session_data"] = encrypt_data(update_data["session_data"])

    for field, value in update_data.items():
        setattr(account, field, value)

    account.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_google_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    # Check if any project is using this account
    result = await db.execute(
        select(Project).where(Project.selected_google_account_id == account_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Account is in use by a project. Disconnect from projects first.")

    await db.delete(account)
    await db.commit()


@router.post("/{account_id}/sync", response_model=GoogleAccountResponse)
async def sync_google_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Sync Google account session - validate tokens with real Google API.
    Performs real token validation via tokeninfo endpoint.
    """
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    if not account.session_data:
        account.status = GoogleAccountStatus.ERROR
        account.error_message = "No session data stored. Complete OAuth flow first."
        account.last_sync = datetime.utcnow()
        await db.commit()
        await db.refresh(account)
        return account

    # Decrypt session data
    try:
        session_data = decrypt_data(account.session_data)
    except Exception as e:
        account.status = GoogleAccountStatus.ERROR
        account.error_message = f"Failed to decrypt session data: {e}"
        account.last_sync = datetime.utcnow()
        await db.commit()
        await db.refresh(account)
        return account

    tokens = session_data.get("tokens", {})
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not access_token:
        account.status = GoogleAccountStatus.ERROR
        account.error_message = "No access token in session data"
        account.last_sync = datetime.utcnow()
        await db.commit()
        await db.refresh(account)
        return account

    async def _refresh(client: httpx.AsyncClient) -> Optional[dict]:
        """Exchange refresh_token for new tokens. Returns new token dict or None."""
        try:
            client_id, client_secret = await _get_oauth_credentials(db)
        except HTTPException:
            return None
        try:
            resp = await client.post("https://oauth2.googleapis.com/token", data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            })
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Google token refresh unreachable: {e}")
        if resp.status_code != 200:
            return None
        new_tokens = resp.json()
        if "refresh_token" not in new_tokens:
            new_tokens["refresh_token"] = refresh_token
        return new_tokens

    # Validate access token with Google's tokeninfo endpoint.
    # All HTTP happens inside one open client; transport errors -> 502, never 500.
    try:
        async with _google_client() as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": access_token},
            )
            if response.status_code == 200:
                token_info = response.json()
                try:
                    expires_in = int(token_info.get("expires_in", 0))
                except (TypeError, ValueError):
                    expires_in = 0
                if expires_in < 300 and refresh_token:
                    new_tokens = await _refresh(client)
                    if new_tokens is None:
                        account.status = GoogleAccountStatus.EXPIRED
                        account.error_message = "Token expired and refresh failed"
                        account.last_sync = datetime.utcnow()
                        await db.commit()
                        await db.refresh(account)
                        return account
                    session_data["tokens"] = new_tokens
                    account.session_data = encrypt_data(session_data)
                account.status = GoogleAccountStatus.CONNECTED
                account.error_message = None
                account.last_sync = datetime.utcnow()
            elif response.status_code == 400 and "invalid_token" in response.text:
                if refresh_token:
                    new_tokens = await _refresh(client)
                    if new_tokens is not None:
                        session_data["tokens"] = new_tokens
                        account.session_data = encrypt_data(session_data)
                        account.status = GoogleAccountStatus.CONNECTED
                        account.error_message = None
                        account.last_sync = datetime.utcnow()
                    else:
                        account.status = GoogleAccountStatus.EXPIRED
                        account.error_message = "Access token expired and refresh failed"
                        account.last_sync = datetime.utcnow()
                else:
                    account.status = GoogleAccountStatus.EXPIRED
                    account.error_message = "Access token expired and no refresh token available"
                    account.last_sync = datetime.utcnow()
            else:
                account.status = GoogleAccountStatus.ERROR
                account.error_message = f"Token validation failed: {response.text}"
                account.last_sync = datetime.utcnow()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Google tokeninfo unreachable: {e}")

    await db.commit()
    await db.refresh(account)
    return account


# OAuth Authorization URL endpoint
@router.get("/{account_id}/auth-url")
async def get_google_auth_url(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Generate Google OAuth authorize URL with state."""
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    client_id, _ = await _get_oauth_credentials(db)

    # Generate state token
    state = secrets.token_urlsafe(32)

    # Store state in account session_data for validation in callback
    session_data = {}
    if account.session_data:
        try:
            session_data = decrypt_data(account.session_data)
        except Exception:
            session_data = {}
    session_data["oauth_state"] = state
    account.session_data = encrypt_data(session_data)

    await db.commit()

    # Build Google OAuth URL (parameters URL-encoded)
    from urllib.parse import urlencode
    redirect_uri = _get_redirect_uri()
    scope = "openid email profile https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/youtube.upload"

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    })

    return {"auth_url": auth_url, "state": state}


# OAuth Callback endpoint
@router.post("/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    account_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Handle Google OAuth callback - exchange code for tokens."""
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    # Validate state
    session_data = {}
    if account.session_data:
        try:
            session_data = decrypt_data(account.session_data)
        except Exception:
            session_data = {}
    stored_state = session_data.get("oauth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    client_id, client_secret = await _get_oauth_credentials(db)

    # Exchange code for tokens (transport errors -> 502, never 500)
    redirect_uri = _get_redirect_uri()
    token_url = "https://oauth2.googleapis.com/token"

    try:
        async with _google_client() as client:
            response = await client.post(token_url, data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Google token exchange unreachable: {e}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed: {response.text}"
        )

    token_data = response.json()

    # Store tokens encrypted
    session_data["tokens"] = token_data
    session_data.pop("oauth_state", None)  # Clear used state
    account.session_data = encrypt_data(session_data)
    account.status = GoogleAccountStatus.CONNECTED
    account.error_message = None

    await db.commit()
    await db.refresh(account)

    return {"success": True, "message": "Google account connected successfully", "account_id": str(account.id)}


# Refresh token endpoint
@router.post("/{account_id}/refresh")
async def refresh_google_token(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Refresh Google OAuth access token using refresh token."""
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    if not account.session_data:
        raise HTTPException(status_code=400, detail="No session data")

    session_data = decrypt_data(account.session_data)
    tokens = session_data.get("tokens", {})
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    client_id, client_secret = await _get_oauth_credentials(db)

    token_url = "https://oauth2.googleapis.com/token"
    try:
        async with _google_client() as client:
            response = await client.post(token_url, data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            })
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Google token refresh unreachable: {e}")

    if response.status_code != 200:
        account.status = GoogleAccountStatus.EXPIRED
        account.error_message = f"Token refresh failed: {response.text}"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Token refresh failed: {response.text}"
        )

    new_tokens = response.json()
    # Merge new tokens (preserve refresh_token if not returned)
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token

    session_data["tokens"] = new_tokens
    account.session_data = encrypt_data(session_data)
    account.status = GoogleAccountStatus.CONNECTED
    account.error_message = None

    await db.commit()

    return {"success": True, "message": "Token refreshed successfully", "account_id": str(account.id)}


# Browser login (Di order 2026-11-17 22:22 WIB): login Google biasa lewat
# Chromium per akun, TANPA Cloud Console. Password diambil terenkripsi dari
# DB (POST /{id}/password); sesi tersimpan di profil browser persisten.
@router.post("/{account_id}/browser-login")
async def browser_login_google_account(
    account_id: UUID,
    body: Optional[BrowserLoginRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Login browser untuk satu akun Google. 200 + logged_in:false (bukan
    error) bila login ditolak / kena challenge 2FA-captcha / tanpa password
    tersimpan — alasan ada di `reason`/`detail`. Playwright/Chromium tidak
    tersedia -> 502 jujur."""
    from app.services.browser_login import GoogleServiceUnavailable as _GSU
    body = body or BrowserLoginRequest()
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")
    try:
        return await browser_login_account(
            db, account, force_relogin=body.force_relogin
        )
    except _GSU as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{account_id}/browser-session")
async def get_browser_session_status(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Status sesi browser akun (tanpa membuka browser): metadata sesi
    terakhir + apakah profil browser persisten sudah ada."""
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")
    meta = read_session_meta(current_user.id, account.id)
    profile_dir = profile_dir_for(current_user.id, account.id)
    return {
        "account_id": str(account.id),
        "email": account.email,
        "has_password": bool(account.password_encrypted),
        "profile_exists": profile_dir.exists(),
        "profile_dir": str(profile_dir),
        "session": meta,
    }


# Password management for Flow Bridge
@router.post("/{account_id}/password")
async def set_google_account_password(
    account_id: UUID,
    body: GoogleAccountPasswordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Set encrypted password for Google account (used by Flow Bridge).
    Password is accepted via JSON body only — never via query string
    (it would land in server/proxy logs and browser history)."""
    password = body.password
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    account.password_encrypted = encrypt_data({"value": password})
    await db.commit()

    return {"message": "Password updated successfully"}


@router.get("/{account_id}/password/check")
async def check_google_account_password(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Check if Google account has a password set (for Flow Bridge)."""
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    return {"has_password": bool(account.password_encrypted)}


@router.post("/{account_id}/password/verify")
async def verify_google_account_password(
    account_id: UUID,
    body: GoogleAccountPasswordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Verify Google account password (for Flow Bridge automation).
    Password via JSON body only — never via query string."""
    password = body.password
    result = await db.execute(
        select(GoogleAccount).where(and_(
            GoogleAccount.id == account_id,
            GoogleAccount.user_id == current_user.id
        ))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    if not account.password_encrypted:
        return {"valid": False, "message": "No password set"}

    try:
        stored = decrypt_data(account.password_encrypted)
        stored_password = stored.get("value", "")
        return {"valid": stored_password == password}
    except Exception:
        return {"valid": False, "message": "Failed to verify password"}