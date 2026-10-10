from ..extensions import db
from .common import CreatedMixin, IdentityMixin, ID_TYPE, TABLE_OPTIONS, active_column


class Category(IdentityMixin, db.Model):
    __tablename__ = "categories"
    __table_args__ = TABLE_OPTIONS

    name = db.Column(db.String(150), nullable=False, unique=True)
    description = db.Column(db.Text)
    products = db.relationship("Product", back_populates="category", passive_deletes="all")


class Product(IdentityMixin, CreatedMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = TABLE_OPTIONS

    category_id = db.Column(ID_TYPE, db.ForeignKey("categories.id", ondelete="RESTRICT"),
                            nullable=False, index=True)
    sku = db.Column(db.String(100), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False)
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    description = db.Column(db.Text)
    unit = db.Column(db.String(30), nullable=False, default="gab.", server_default="gab.")
    image_url = db.Column(db.String(2048))
    is_active = active_column()

    category = db.relationship("Category", back_populates="products")
    offers = db.relationship("Offer", back_populates="product", passive_deletes="all")


class Offer(IdentityMixin, db.Model):
    __tablename__ = "offers"
    __table_args__ = (
        db.CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
        db.CheckConstraint("min_order_qty >= 1", name="min_order_qty_positive"),
        db.CheckConstraint("stock_qty >= 0", name="stock_qty_nonnegative"),
        db.CheckConstraint("delivery_price >= 0", name="delivery_price_nonnegative"),
        db.CheckConstraint("delivery_days >= 0", name="delivery_days_nonnegative"),
        db.CheckConstraint("data_source IN ('manual', 'CSV', 'JSON', 'API')", name="valid_data_source"),
        TABLE_OPTIONS,
    )

    product_id = db.Column(ID_TYPE, db.ForeignKey("products.id", ondelete="RESTRICT"),
                           nullable=False, index=True)
    created_by_admin_id = db.Column(ID_TYPE, db.ForeignKey("users.id", ondelete="RESTRICT"),
                                    nullable=False, index=True)
    supplier_name = db.Column(db.String(255), nullable=False)
    supplier_sku = db.Column(db.String(100))
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    # VAT must be supplied explicitly: silently assuming its status changes meaning.
    vat_included = db.Column(db.Boolean(create_constraint=True, name="vat_included_boolean"), nullable=False)
    min_order_qty = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    stock_qty = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    delivery_price = db.Column(db.Numeric(10, 2), nullable=False, default=0, server_default="0")
    delivery_days = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    data_source = db.Column(db.String(20), nullable=False, default="manual", server_default="manual")
    updated_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp(),
                           onupdate=db.func.current_timestamp())
    is_active = active_column()

    product = db.relationship("Product", back_populates="offers")
    created_by_admin = db.relationship("User", back_populates="offers_created")
    cart_items = db.relationship("CartItem", back_populates="offer", passive_deletes="all")
    order_items = db.relationship("OrderItem", back_populates="offer", passive_deletes="all")
