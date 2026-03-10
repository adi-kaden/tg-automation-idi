"""Add prompt_configs table

Revision ID: add_prompt_configs
Revises: add_image_data_column
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4

# revision identifiers
revision = 'add_prompt_configs'
down_revision = 'add_rejected_urls_001'
branch_labels = None
depends_on = None


# Default prompts to seed
DEFAULT_SYSTEM_PROMPT = """You are an expert social media content creator for IDIGOV Real Estate, a premium real estate company in Dubai, UAE. You create engaging Telegram posts in Russian for the Russian-speaking audience of Dubai property investors.

Your posts should:
1. Be informative yet engaging
2. Appeal to Russian-speaking property investors and expatriates in Dubai
3. Use a professional but approachable tone in Russian
4. Include relevant emojis sparingly (1-3 per post)
5. Be concise - ideal for Telegram reading

IMPORTANT: All content must be written in Russian. The target audience is Russian-speaking investors and business people interested in Dubai real estate."""

DEFAULT_GENERATION_PROMPT = """Based on the following news articles, create a compelling Telegram post in Russian for IDIGOV Real Estate's channel.

Content Type: {{content_type}}
Category: {{category}}
Tone: {{tone}}
Max Length: {{max_length}} characters

SOURCE ARTICLES:
{{articles}}

Generate a Telegram post with the following structure (ALL IN RUSSIAN):

1. TITLE (Russian): A catchy, engaging headline in Russian (max 100 chars)
2. BODY (Russian): The main post content in Russian (400-{{max_length}} chars). Include key facts, insights, and a subtle call-to-action if relevant. Do NOT include hashtags.
3. IMAGE_PROMPT: A detailed prompt for generating an accompanying image (describe the visual concept, style, colors - suitable for a real estate/Dubai context)
4. QUALITY_SCORE: Rate the newsworthiness and engagement potential (0.0-1.0)

Respond in JSON format:
{
    "title_ru": "...",
    "body_ru": "...",
    "image_prompt": "...",
    "quality_score": 0.85
}"""

DEFAULT_IMAGE_STYLE_PROMPT = """Style: Modern luxury Dubai architecture, professional real estate photography style, golden hour lighting, high-end finishes
Quality: High resolution, professional photography or illustration style
Mood: Professional, aspirational, modern
Colors: Warm tones, gold accents, blues reflecting Dubai's sky and sea
Note: No text or watermarks in the image"""


def upgrade() -> None:
    # Create table
    op.create_table(
        'prompt_configs',
        sa.Column('id', sa.Uuid(), nullable=False, default=uuid4),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('slot_number', sa.Integer(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('generation_prompt', sa.Text(), nullable=False),
        sa.Column('tone', sa.String(30), server_default='professional'),
        sa.Column('max_length_chars', sa.Integer(), server_default='1500'),
        sa.Column('image_style_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('image_aspect_ratio', sa.String(10), server_default='16:9'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_prompt_configs'),
        sa.CheckConstraint("scope IN ('global', 'slot_override')", name='ck_prompt_configs_scope'),
        sa.CheckConstraint(
            "(scope = 'global' AND slot_number IS NULL) OR "
            "(scope = 'slot_override' AND slot_number BETWEEN 1 AND 5)",
            name='ck_prompt_configs_slot_number'
        ),
        sa.UniqueConstraint('scope', 'slot_number', name='uq_prompt_configs_scope_slot'),
    )

    # Seed global config with defaults
    op.execute(
        sa.text(
            "INSERT INTO prompt_configs (id, scope, slot_number, system_prompt, generation_prompt, "
            "tone, max_length_chars, image_style_prompt, image_aspect_ratio, is_active) "
            "VALUES (:id, 'global', NULL, :sys, :gen, 'professional', 1500, :img, '16:9', true)"
        ).bindparams(
            id=str(uuid4()),
            sys=DEFAULT_SYSTEM_PROMPT,
            gen=DEFAULT_GENERATION_PROMPT,
            img=DEFAULT_IMAGE_STYLE_PROMPT,
        )
    )


def downgrade() -> None:
    op.drop_table('prompt_configs')
