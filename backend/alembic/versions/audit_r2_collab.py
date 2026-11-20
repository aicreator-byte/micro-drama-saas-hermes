"""Perbaikan audit ronde 2 (20 Nov 2026), P1-2: state kolaborasi persisten.

Revision ID: audit_r2_collab
Revises: round2_future_dev
Create Date: 2026-11-20

Tabel collab_room_states (versi edit per proyek) + collab_presence
(user online per proyek) — ganti state in-memory CollabManager supaya
tahan restart dan konsisten antar worker.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'audit_r2_collab'
down_revision: Union[str, None] = 'round2_future_dev'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'collab_room_states',
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('project_id'),
    )
    op.create_table(
        'collab_presence',
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('field', sa.String(length=255), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('project_id', 'user_id'),
    )


def downgrade() -> None:
    op.drop_table('collab_presence')
    op.drop_table('collab_room_states')
