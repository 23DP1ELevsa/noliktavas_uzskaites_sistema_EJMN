from ..extensions import db
from .common import CreatedMixin, IdentityMixin, TABLE_OPTIONS, active_column


class Supplier(IdentityMixin, CreatedMixin, db.Model):
    __tablename__ = "suppliers"
    __table_args__ = (db.CheckConstraint("delivery_price >= 0", name="delivery_price_nonnegative"), TABLE_OPTIONS)

    name = db.Column(db.String(255), nullable=False)
    name_key = db.Column(db.String(510), nullable=False, unique=True)
    contact_person = db.Column(db.String(150))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    website = db.Column(db.String(2048))
    delivery_price = db.Column(db.Numeric(10, 2), nullable=False, default=0, server_default="0")
    is_active = active_column()
    offers = db.relationship("Offer", back_populates="supplier", passive_deletes="all")
    order_items = db.relationship("OrderItem", back_populates="supplier", passive_deletes="all")
