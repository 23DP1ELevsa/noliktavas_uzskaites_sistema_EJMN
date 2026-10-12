"""Manage suppliers and retain their links to historical order items."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

revision = "0004_suppliers"
down_revision = "0003_company_delivery"
branch_labels = None
depends_on = None

ID_TYPE = sa.BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")


def upgrade():
    op.create_table("suppliers",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_key", sa.String(510), nullable=False),
        sa.Column("contact_person", sa.String(150)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("website", sa.String(2048)),
        sa.Column("delivery_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(create_constraint=True, name="is_active_boolean"), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name_key", name="uq_suppliers_name_key"),
        sa.CheckConstraint("delivery_price >= 0", name="delivery_price_nonnegative"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")
    connection = op.get_bind()
    for table in ("offers", "order_items"):
        if connection.dialect.name == "sqlite":
            # Native ADD COLUMN preserves cart/order rows, unlike recreating the
            # offers table with SQLite's cascading foreign keys enabled.
            op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN supplier_id INTEGER "
                               f"CONSTRAINT fk_{table}_supplier_id_suppliers REFERENCES suppliers(id)"))
        else:
            op.add_column(table, sa.Column("supplier_id", ID_TYPE, nullable=True))
            op.create_foreign_key(f"fk_{table}_supplier_id_suppliers", table, "suppliers", ["supplier_id"], ["id"])
        op.create_index(f"ix_{table}_supplier_id", table, ["supplier_id"])
    suppliers = sa.table("suppliers", sa.column("id"), sa.column("name"), sa.column("name_key"),
                         sa.column("delivery_price"), sa.column("is_active"))
    identifiers, offer_suppliers = {}, {}
    def supplier_for(name, price, active):
        normalized = " ".join(name.split())
        key = normalized.casefold()
        if key not in identifiers:
            result = connection.execute(suppliers.insert().values(name=normalized, name_key=key,
                                                                  delivery_price=price, is_active=active))
            identifiers[key] = result.lastrowid
        return identifiers[key]
    for offer in connection.execute(sa.text("SELECT id, supplier_name, delivery_price FROM offers ORDER BY id")).mappings().all():
        identifier = supplier_for(offer["supplier_name"], offer["delivery_price"], True)
        offer_suppliers[offer["id"]] = identifier
        connection.execute(sa.text("UPDATE offers SET supplier_id=:supplier WHERE id=:id"),
                           {"supplier": identifier, "id": offer["id"]})
    for item in connection.execute(sa.text("SELECT id, offer_id, supplier_name, delivery_price FROM order_items ORDER BY id")).mappings().all():
        identifier = offer_suppliers.get(item["offer_id"])
        if identifier is None:
            identifier = supplier_for(item["supplier_name"], item["delivery_price"], False)
        connection.execute(sa.text("UPDATE order_items SET supplier_id=:supplier WHERE id=:id"),
                           {"supplier": identifier, "id": item["id"]})


def downgrade():
    connection = op.get_bind()
    for table in ("order_items", "offers"):
        if connection.dialect.name != "sqlite":
            op.drop_constraint(f"fk_{table}_supplier_id_suppliers", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_supplier_id", table_name=table)
        op.drop_column(table, "supplier_id")
    op.drop_table("suppliers")
