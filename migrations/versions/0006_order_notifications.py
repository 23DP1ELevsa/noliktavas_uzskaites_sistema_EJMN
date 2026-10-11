"""Preserve application contact details and deliver profile notifications."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT

revision = "0006_order_notifications"
down_revision = "0005_offer_terms"
branch_labels = None
depends_on = None

ID_TYPE = sa.BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")


def upgrade():
    op.add_column("orders", sa.Column("customer_snapshot", sa.JSON(), nullable=True))
    op.create_table("notifications",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("user_id", ID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", ID_TYPE, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("is_read", sa.Boolean(create_constraint=True, name="is_read_boolean"), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("user_id", "order_id", "kind", name="uq_notifications_recipient_order_kind"),
        sa.CheckConstraint("kind IN ('submitted', 'approved', 'declined')", name="valid_kind"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_order_id", "notifications", ["order_id"])


def downgrade():
    op.drop_table("notifications")
    op.drop_column("orders", "customer_snapshot")
