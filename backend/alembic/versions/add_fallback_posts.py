"""Add fallback_posts table and make published_posts.option_id nullable

Revision ID: add_fallback_posts_001
Revises: add_voice_album_001
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "add_fallback_posts_001"
down_revision = "add_voice_album_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # fallback_posts table — evergreen content the watchdog publishes when a
    # live slot can't be recovered. Ensures the channel never goes silent.
    op.create_table(
        "fallback_posts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title_ru", sa.String(500), nullable=False),
        sa.Column("body_ru", sa.Text(), nullable=False),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("image_data", sa.Text(), nullable=True),
        sa.Column(
            "content_type",
            sa.String(30),
            server_default="any",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "times_used",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fallback_posts_is_active", "fallback_posts", ["is_active"]
    )
    op.create_index(
        "ix_fallback_posts_content_type", "fallback_posts", ["content_type"]
    )

    # Make published_posts.option_id nullable so fallback publishes (which
    # have no PostOption) can be recorded in published_posts too.
    op.alter_column(
        "published_posts",
        "option_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "published_posts",
        "option_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_index(
        "ix_fallback_posts_content_type", table_name="fallback_posts"
    )
    op.drop_index(
        "ix_fallback_posts_is_active", table_name="fallback_posts"
    )
    op.drop_table("fallback_posts")
