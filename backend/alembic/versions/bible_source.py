"""Add SeriesBible.source ('manual' | 'auto') — future-dev 19 Nov 2026.

Langkah 1 auto-generate melindungi bible manual dari timpa diam-diam;
kolom ini menandai asal bible. Default 'manual' supaya bible yang sudah
ada (pra-migrasi) ikut terlindungi, bukan malah ditimpa.

Revision ID: bible_source
Revises: auto_generate_jobs
Create Date: 2026-11-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bible_source'
down_revision: Union[str, None] = 'auto_generate_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'series_bibles',
        sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'),
    )


def downgrade() -> None:
    op.drop_column('series_bibles', 'source')
