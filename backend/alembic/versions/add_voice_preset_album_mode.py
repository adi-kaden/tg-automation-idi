"""Add voice_preset, album_mode, and album image fields

Revision ID: add_voice_album_001
Revises: fix_duplicate_slots_001
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "add_voice_album_001"
down_revision = "fix_duplicate_slots_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # voice_preset on prompt_configs
    op.add_column(
        "prompt_configs",
        sa.Column("voice_preset", sa.String(30), server_default="professional", nullable=False),
    )

    # album_mode on content_slots
    op.add_column(
        "content_slots",
        sa.Column("album_mode", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # album image fields on post_options
    op.add_column(
        "post_options",
        sa.Column("album_image_prompts", sa.Text(), nullable=True),
    )
    op.add_column(
        "post_options",
        sa.Column("album_images_data", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("post_options", "album_images_data")
    op.drop_column("post_options", "album_image_prompts")
    op.drop_column("content_slots", "album_mode")
    op.drop_column("prompt_configs", "voice_preset")
