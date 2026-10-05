from ..extensions import db
from .common import CreatedMixin, IdentityMixin, ID_TYPE, TABLE_OPTIONS


class Cart(IdentityMixin, CreatedMixin, db.Model):
    __tablename__ = "carts"
    __table_args__ = (db.CheckConstraint("status = 'active'", name="valid_status"), TABLE_OPTIONS)

    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default="active", server_default="active")
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp(),
                           onupdate=db.func.current_timestamp())
    user = db.relationship("User", back_populates="cart")
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan",
                            passive_deletes=True)


class CartItem(IdentityMixin, CreatedMixin, db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (
        db.UniqueConstraint("cart_id", "offer_id", name="uq_cart_items_cart_offer"),
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        TABLE_OPTIONS,
    )

    cart_id = db.Column(ID_TYPE, db.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    offer_id = db.Column(ID_TYPE, db.ForeignKey("offers.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    cart = db.relationship("Cart", back_populates="items")
    offer = db.relationship("Offer", back_populates="cart_items")


class Order(IdentityMixin, CreatedMixin, db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.CheckConstraint("status IN ('iesniegts', 'apstiprināts', 'noraidīts')", name="valid_status"),
        db.CheckConstraint("total_amount >= 0", name="total_amount_nonnegative"),
        TABLE_OPTIONS,
    )

    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    company_profile_id = db.Column(ID_TYPE, db.ForeignKey("company_profiles.id", ondelete="RESTRICT"),
                                   nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default="iesniegts", server_default="iesniegts")
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    admin_note = db.Column(db.Text)
    processed_by_admin_id = db.Column(ID_TYPE, db.ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    processed_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="orders", foreign_keys=[user_id])
    company_profile = db.relationship("CompanyProfile", back_populates="orders")
    processed_by_admin = db.relationship("User", back_populates="orders_processed",
                                         foreign_keys=[processed_by_admin_id])
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan",
                            passive_deletes=True)


class OrderItem(IdentityMixin, db.Model):
    __tablename__ = "order_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
        db.CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
        db.CheckConstraint("delivery_price >= 0", name="delivery_price_nonnegative"),
        db.CheckConstraint("line_total >= 0", name="line_total_nonnegative"),
        TABLE_OPTIONS,
    )

    order_id = db.Column(ID_TYPE, db.ForeignKey("orders.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    offer_id = db.Column(ID_TYPE, db.ForeignKey("offers.id", ondelete="SET NULL"), index=True)
    product_name = db.Column(db.String(255), nullable=False)
    supplier_name = db.Column(db.String(255), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    delivery_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(12, 2), nullable=False)
    vat_included = db.Column(db.Boolean(create_constraint=True, name="vat_included_boolean"), nullable=False)

    order = db.relationship("Order", back_populates="items")
    offer = db.relationship("Offer", back_populates="order_items")
