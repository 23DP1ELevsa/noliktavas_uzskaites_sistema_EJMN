"""Add an optional image URL to catalog products."""

from alembic import op
import sqlalchemy as sa

revision = "0002_product_image"
down_revision = "0001_stockflow"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("image_url", sa.String(2048), nullable=True))


def downgrade():
    op.drop_column("products", "image_url")
