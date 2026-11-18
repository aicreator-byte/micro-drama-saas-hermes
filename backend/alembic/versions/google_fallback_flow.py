"""Add Google-account fallback fields to flow_tasks

Revision ID: google_fallback_flow
Revises: phase2_settings_oauth
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


# revision identifiers, used by Alembic.
revision: str = 'google_fallback_flow'
down_revision: Union[str, None] = 'phase2_settings_oauth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    id_type = sa.String(36) if is_sqlite else PG_UUID(as_uuid=True)

    op.add_column('flow_tasks',
        sa.Column('active_account_id', id_type, nullable=True))
    op.add_column('flow_tasks',
        sa.Column('fallback_history', sa.JSON(), nullable=True))
    op.add_column('flow_tasks',
        sa.Column('error_message', sa.Text(), nullable=True))

    if not is_sqlite:
        op.create_foreign_key(
            'fk_flow_tasks_active_account_id', 'flow_tasks', 'google_accounts',
            ['active_account_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.drop_constraint('fk_flow_tasks_active_account_id', 'flow_tasks', type_='foreignkey')
    op.drop_column('flow_tasks', 'error_message')
    op.drop_column('flow_tasks', 'fallback_history')
    op.drop_column('flow_tasks', 'active_account_id')
