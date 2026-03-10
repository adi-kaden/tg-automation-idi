"""Add image_style column to post_options

Revision ID: add_image_style_001
Revises: add_prompt_configs
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_image_style_001'
down_revision = 'add_prompt_configs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('post_options', sa.Column('image_style', sa.String(50), nullable=True))
    # Clear the seeded image_style_prompt so it doesn't override Claude's dynamic selection
    op.execute("UPDATE prompt_configs SET image_style_prompt = '' WHERE scope = 'global'")


def downgrade() -> None:
    op.drop_column('post_options', 'image_style')
