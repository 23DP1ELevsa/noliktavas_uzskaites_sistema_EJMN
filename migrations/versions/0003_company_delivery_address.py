"""Store an optional delivery address separately from the company address."""

from alembic import op
import sqlalchemy as sa

revision = "0003_company_delivery"
down_revision = "0002_product_image"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_profiles", sa.Column("delivery_address", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("company_profiles", "delivery_address")
