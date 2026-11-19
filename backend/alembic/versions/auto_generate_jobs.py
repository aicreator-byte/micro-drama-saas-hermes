"""Add auto-generate jobs + steps tables (Fase 1 auto-generate)

Revision ID: auto_generate_jobs
Revises: google_fallback_flow
Create Date: 2026-11-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


# revision identifiers, used by Alembic.
revision: str = 'auto_generate_jobs'
down_revision: Union[str, None] = 'google_fallback_flow'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    id_type = sa.String(36) if is_sqlite else PG_UUID(as_uuid=True)

    op.create_table(
        'auto_generate_jobs',
        sa.Column('id', id_type, nullable=False),
        sa.Column('project_id', id_type, nullable=False),
        sa.Column('user_id', id_type, nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('genre', sa.String(length=100), nullable=True),
        sa.Column('num_episodes', sa.Integer(), nullable=False),
        sa.Column('premise', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed',
                                     name='autogeneratejobstatus'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auto_generate_jobs_project_id'), 'auto_generate_jobs', ['project_id'], unique=False)
    op.create_index(op.f('ix_auto_generate_jobs_user_id'), 'auto_generate_jobs', ['user_id'], unique=False)

    op.create_table(
        'auto_generate_steps',
        sa.Column('id', id_type, nullable=False),
        sa.Column('job_id', id_type, nullable=False),
        sa.Column('step_key', sa.String(length=50), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'skipped',
                                     name='autogeneratestepstatus'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['auto_generate_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'step_key', name='uq_job_step'),
    )
    op.create_index(op.f('ix_auto_generate_steps_job_id'), 'auto_generate_steps', ['job_id'], unique=False)
    op.create_index('ix_step_job_order', 'auto_generate_steps', ['job_id', 'step_order'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_step_job_order', table_name='auto_generate_steps')
    op.drop_index(op.f('ix_auto_generate_steps_job_id'), table_name='auto_generate_steps')
    op.drop_table('auto_generate_steps')
    op.drop_index(op.f('ix_auto_generate_jobs_user_id'), table_name='auto_generate_jobs')
    op.drop_index(op.f('ix_auto_generate_jobs_project_id'), table_name='auto_generate_jobs')
    op.drop_table('auto_generate_jobs')
    # Drop the enum types on PostgreSQL (SQLite has no real enum types).
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        sa.Enum(name='autogeneratestepstatus').drop(bind, checkfirst=True)
        sa.Enum(name='autogeneratejobstatus').drop(bind, checkfirst=True)
