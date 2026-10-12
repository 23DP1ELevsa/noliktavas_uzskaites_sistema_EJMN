"""Prevent duplicate supplier offer codes without rebuilding offer tables."""

from alembic import op
import sqlalchemy as sa


revision = "0007_offer_import_identity"
down_revision = "0006_order_notifications"
branch_labels = None
depends_on = None


def upgrade():
    duplicate = op.get_bind().execute(sa.text(
        "SELECT supplier_id, supplier_sku FROM offers "
        "WHERE supplier_id IS NOT NULL AND supplier_sku IS NOT NULL "
        "GROUP BY supplier_id, supplier_sku HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate is not None:
        raise RuntimeError("Duplicate supplier offer codes exist. Resolve duplicate supplier_id / "
                           "supplier_sku entries in /admin/supplier-products before running db upgrade. "
                           "No offers were deleted.")
    op.create_index("uq_offers_supplier_sku", "offers", ["supplier_id", "supplier_sku"], unique=True)


def downgrade():
    op.drop_index("uq_offers_supplier_sku", table_name="offers")
