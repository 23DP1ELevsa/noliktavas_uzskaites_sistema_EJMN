from ..extensions import db
from .common import CreatedMixin, IdentityMixin, ID_TYPE, TABLE_OPTIONS


class Notification(IdentityMixin, CreatedMixin, db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        db.UniqueConstraint("user_id", "order_id", "kind", name="uq_notifications_recipient_order_kind"),
        db.CheckConstraint("kind IN ('submitted', 'approved', 'declined')", name="valid_kind"),
        TABLE_OPTIONS,
    )

    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean(create_constraint=True, name="is_read_boolean"), nullable=False,
                        default=False, server_default=db.false())
