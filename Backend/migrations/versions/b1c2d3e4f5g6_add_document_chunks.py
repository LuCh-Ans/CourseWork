from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, FLOAT

revision = 'b1c2d3e4f5g6'
down_revision = 'a1b2c3d4e5f6'  # последняя твоя миграция

def upgrade():
    op.create_table('document_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', ARRAY(FLOAT), nullable=True),
    )

def downgrade():
    op.drop_table('document_chunks')