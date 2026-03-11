"""Deduplicate content_slots and add unique constraint

Revision ID: fix_duplicate_slots_001
Revises: add_image_style_001
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_duplicate_slots_001'
down_revision = 'add_image_style_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Identify duplicate slot IDs to delete.
    # For each (scheduled_date, slot_number), keep the slot with the best status
    # (published > approved > options_ready > others) and earliest created_at as tiebreaker.
    conn.execute(sa.text("""
        CREATE TEMP TABLE _dup_slot_ids AS
        SELECT id FROM (
            SELECT id,
                ROW_NUMBER() OVER (
                    PARTITION BY scheduled_date, slot_number
                    ORDER BY
                        CASE status
                            WHEN 'published' THEN 1
                            WHEN 'approved' THEN 2
                            WHEN 'options_ready' THEN 3
                            WHEN 'generating' THEN 4
                            WHEN 'pending' THEN 5
                            WHEN 'failed' THEN 6
                            ELSE 7
                        END,
                        created_at ASC
                ) as rn
            FROM content_slots
        ) ranked
        WHERE rn > 1
    """))

    # Step 2: Clear FK self-references on duplicate slots
    conn.execute(sa.text("""
        UPDATE content_slots
        SET selected_option_id = NULL, published_post_id = NULL
        WHERE id IN (SELECT id FROM _dup_slot_ids)
    """))

    # Step 3: Clear article references to options of duplicate slots
    conn.execute(sa.text("""
        UPDATE scraped_articles
        SET used_in_post_id = NULL, is_used = false
        WHERE used_in_post_id IN (
            SELECT po.id FROM post_options po
            WHERE po.slot_id IN (SELECT id FROM _dup_slot_ids)
        )
    """))

    # Step 4: Delete published posts for duplicate slots
    conn.execute(sa.text("""
        DELETE FROM published_posts
        WHERE slot_id IN (SELECT id FROM _dup_slot_ids)
    """))

    # Step 5: Delete post options for duplicate slots
    conn.execute(sa.text("""
        DELETE FROM post_options
        WHERE slot_id IN (SELECT id FROM _dup_slot_ids)
    """))

    # Step 6: Delete duplicate slots
    conn.execute(sa.text("""
        DELETE FROM content_slots
        WHERE id IN (SELECT id FROM _dup_slot_ids)
    """))

    conn.execute(sa.text("DROP TABLE _dup_slot_ids"))

    # Step 7: Add unique constraint to prevent future duplicates
    op.create_unique_constraint(
        'uq_content_slots_date_slot',
        'content_slots',
        ['scheduled_date', 'slot_number']
    )


def downgrade() -> None:
    op.drop_constraint('uq_content_slots_date_slot', 'content_slots', type_='unique')
