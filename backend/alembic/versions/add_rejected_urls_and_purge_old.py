"""add rejected_article_urls table and purge old articles

Revision ID: add_rejected_urls_001
Revises: add_image_data_001
Create Date: 2026-03-09

"""
from typing import Sequence, Union
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_rejected_urls_001'
down_revision: Union[str, None] = 'add_image_data_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create rejected_article_urls table
    op.create_table(
        'rejected_article_urls',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('url', sa.String(length=2000), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('rejected_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rejected_article_urls')),
        sa.UniqueConstraint('url', name=op.f('uq_rejected_article_urls_url')),
    )
    op.create_index(op.f('ix_rejected_article_urls_url'), 'rejected_article_urls', ['url'])

    # One-time purge: delete existing scraped_articles older than 2 days
    # by EITHER published_at OR scraped_at (covers NULL published_at too)
    cutoff = datetime.utcnow() - timedelta(days=2)

    # Clear FK references first
    op.execute(
        sa.text(
            "UPDATE scraped_articles SET used_in_post_id = NULL "
            "WHERE used_in_post_id IS NOT NULL AND ("
            "  scraped_at < :cutoff "
            "  OR (published_at IS NOT NULL AND published_at < :cutoff)"
            ")"
        ).bindparams(cutoff=cutoff)
    )

    # Delete old articles by scraped_at or published_at
    op.execute(
        sa.text(
            "DELETE FROM scraped_articles "
            "WHERE scraped_at < :cutoff "
            "  OR (published_at IS NOT NULL AND published_at < :cutoff)"
        ).bindparams(cutoff=cutoff)
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_rejected_article_urls_url'), table_name='rejected_article_urls')
    op.drop_table('rejected_article_urls')
