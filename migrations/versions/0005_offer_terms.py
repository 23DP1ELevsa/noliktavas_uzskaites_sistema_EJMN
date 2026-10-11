"""Store offer VAT rates and currency, including order snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "0005_offer_terms"
down_revision = "0004_suppliers"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("offers", "order_items"):
        if op.get_bind().dialect.name == "sqlite":
            # Native ADD COLUMN avoids cascading deletion of child rows.
            op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN vat_rate NUMERIC(5, 2) "
                               f"CONSTRAINT ck_{table}_vat_rate_range CHECK (vat_rate IS NULL OR (vat_rate >= 0 AND vat_rate <= 100))"))
            op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'EUR' "
                               f"CONSTRAINT ck_{table}_currency_supported CHECK (currency = 'EUR')"))
        else:
            op.add_column(table, sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True))
            op.add_column(table, sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"))
            op.create_check_constraint(op.f(f"ck_{table}_vat_rate_range"), table, "vat_rate IS NULL OR (vat_rate >= 0 AND vat_rate <= 100)")
            op.create_check_constraint(op.f(f"ck_{table}_currency_supported"), table, "currency = 'EUR'")


def downgrade():
    for table in ("order_items", "offers"):
        if op.get_bind().dialect.name != "sqlite":
            op.drop_constraint(op.f(f"ck_{table}_currency_supported"), table, type_="check")
            op.drop_constraint(op.f(f"ck_{table}_vat_rate_range"), table, type_="check")
        op.drop_column(table, "currency")
        op.drop_column(table, "vat_rate")
