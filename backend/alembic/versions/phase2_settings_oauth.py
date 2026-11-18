"""Add AppSettings and GoogleAccount password_encrypted

Revision ID: phase2_settings_oauth
Revises: fb3fe9886bc2
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
import json

# revision identifiers, used by Alembic.
revision: str = 'phase2_settings_oauth'
down_revision: Union[str, None] = 'fb3fe9886bc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password_encrypted to google_accounts
    op.add_column('google_accounts',
        sa.Column('password_encrypted', sa.Text(), nullable=True)
    )

    # Create app_settings table
    # Use portable UUID type - String for SQLite, UUID for PostgreSQL
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'

    if is_sqlite:
        id_type = sa.String(36)
        json_type = sa.JSON()
    else:
        id_type = PG_UUID(as_uuid=True)
        json_type = sa.JSON()

    op.create_table('app_settings',
        sa.Column('id', id_type, nullable=False),
        sa.Column('ai_providers', json_type, nullable=True),
        sa.Column('google_oauth_client_id_encrypted', sa.Text(), nullable=True),
        sa.Column('google_oauth_client_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Insert default settings row with Nvidia provider
    import uuid
    from datetime import datetime
    default_ai_providers = [{
        "id": "nvidia-nemotron-ultra",
        "provider": "nvidia",
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "key_env": "NVIDIA_API_KEY",
        "enabled": True,
        "priority": 1,
        "base_url": "https://integrate.api.nvidia.com/v1"
    }]
    
    if is_sqlite:
        op.execute(
            sa.text("""
                INSERT INTO app_settings (id, ai_providers, created_at, updated_at)
                VALUES (:id, :ai_providers, :created_at, :updated_at)
            """).bindparams(
                id=str(uuid.uuid4()),
                ai_providers=json.dumps(default_ai_providers),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
    else:
        op.execute(
            sa.text("""
                INSERT INTO app_settings (id, ai_providers, created_at, updated_at)
                VALUES (gen_random_uuid(), :ai_providers::jsonb, NOW(), NOW())
            """).bindparams(
                ai_providers=json.dumps(default_ai_providers)
            )
        )


def downgrade() -> None:
    op.drop_table('app_settings')
    op.drop_column('google_accounts', 'password_encrypted')