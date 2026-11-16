from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.models import User, GoogleAccount, GoogleAccountStatus, Project
from app.schemas import GoogleAccountCreate, GoogleAccountUpdate, GoogleAccountResponse
from app.utils.encryption import encrypt_data, decrypt_data

router = APIRouter(prefix="/google-accounts", tags=["google-accounts"])


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

    # Encrypt session data if provided
    encrypted_session = None
    # session_data is not in GoogleAccountCreate schema, handled on update

    account = GoogleAccount(
        user_id=current_user.id,
        email=account_data.email,
        display_name=account_data.display_name,
        session_data=encrypted_session,
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

    # Decrypt session data for response
    for account in accounts:
        if account.session_data:
            account.session_data = decrypt_data(account.session_data)
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

    if account.session_data:
        account.session_data = decrypt_data(account.session_data)
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

    if account.session_data:
        account.session_data = decrypt_data(account.session_data)
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
    Sync Google account session (placeholder for browser automation).
    In production, this would use Playwright to refresh the session.
    Validates stored session data; marks expired/error if invalid.
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

    # Validate stored session data
    if not account.session_data:
        account.status = GoogleAccountStatus.ERROR
        account.error_message = "No session data stored. Complete OAuth flow first."
        account.last_sync = datetime.utcnow()
        await db.commit()
        await db.refresh(account)
        if account.session_data:
            account.session_data = decrypt_data(account.session_data)
        return account

    # Placeholder: In production, use Playwright to validate/refresh session against Google
    # For now, we assume session_data exists but cannot be verified without real OAuth
    # Mark as disconnected since we can't verify it's still valid
    account.status = GoogleAccountStatus.DISCONNECTED
    account.error_message = "Session validation requires browser automation (not implemented). Session data exists but cannot be verified."
    account.last_sync = datetime.utcnow()
    await db.commit()
    await db.refresh(account)

    if account.session_data:
        account.session_data = decrypt_data(account.session_data)
    return account