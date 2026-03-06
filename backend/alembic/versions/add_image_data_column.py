"""add image_data column to post_options

Revision ID: add_image_data_001
Revises: eea4bad34a32
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_image_data_001'
down_revision: Union[str, None] = 'eea4bad34a32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add image_data column to post_options table
    op.add_column('post_options', sa.Column('image_data', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove image_data column
    op.drop_column('post_options', 'image_data')
