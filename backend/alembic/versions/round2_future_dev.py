"""Future-dev round 2 (20 Nov 2026): tabel billing, timeline video,
cek konsistensi karakter, dan job subtitle.

Revision ID: round2_future_dev
Revises: bible_source
Create Date: 2026-11-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'round2_future_dev'
down_revision: Union[str, None] = 'bible_source'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('INACTIVE', 'TRIALING', 'ACTIVE', 'PAST_DUE', 'CANCELED', name='subscriptionstatus'), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_customer_id', sa.String(length=255), nullable=True),
        sa.Column('provider_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_subscription_user'),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_table(
        'billing_events',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_billing_events_user_id', 'billing_events', ['user_id'])
    op.create_table(
        'video_timelines',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('episode_id', UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('clips', sa.JSON(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('fps', sa.Integer(), nullable=False),
        sa.Column('resolution', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('episode_id', name='uq_timeline_episode'),
    )
    op.create_index('ix_video_timelines_episode_id', 'video_timelines', ['episode_id'])
    op.create_table(
        'character_consistency_checks',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.Enum('RUNNING', 'COMPLETED', 'FAILED', name='consistencycheckstatus'), nullable=False),
        sa.Column('checked_episodes', sa.JSON(), nullable=True),
        sa.Column('issues', sa.JSON(), nullable=True),
        sa.Column('issue_count', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_character_consistency_checks_project_id', 'character_consistency_checks', ['project_id'])
    op.create_table(
        'subtitle_jobs',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('episode_id', UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('source_filename', sa.String(length=255), nullable=True),
        sa.Column('source_path', sa.String(length=500), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='subtitlejobstatus'), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('engine', sa.String(length=50), nullable=True),
        sa.Column('model_size', sa.String(length=20), nullable=False),
        sa.Column('segments', sa.JSON(), nullable=True),
        sa.Column('srt_path', sa.String(length=500), nullable=True),
        sa.Column('vtt_path', sa.String(length=500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_subtitle_jobs_project_id', 'subtitle_jobs', ['project_id'])


def downgrade() -> None:
    op.drop_table('subtitle_jobs')
    op.drop_table('character_consistency_checks')
    op.drop_table('video_timelines')
    op.drop_table('billing_events')
    op.drop_table('subscriptions')
    sa.Enum(name='subtitlejobstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='consistencycheckstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='subscriptionstatus').drop(op.get_bind(), checkfirst=True)
