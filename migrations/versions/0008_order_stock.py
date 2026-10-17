"""Track local stock allocations without changing historical orders or balances."""

from alembic import op
import sqlalchemy as sa

revision = "0008_order_stock"
down_revision = "0007_offer_import_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("offers", sa.Column("allocated_qty", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("offers", sa.Column("imported_stock_qty", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("stock_deducted", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    # Native DROP COLUMN avoids SQLite batch copies cascading into order items.
    op.drop_column("orders", "stock_deducted")
    op.drop_column("offers", "imported_stock_qty")
    op.drop_column("offers", "allocated_qty")
