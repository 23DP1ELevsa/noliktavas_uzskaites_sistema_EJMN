"""Repeatable demo data loading; existing records are never reset or deleted."""

from collections import Counter
from decimal import Decimal
import json

from ..config import PROJECT_ROOT
from ..extensions import db
from ..models import Cart, CartItem, Category, CompanyProfile, Offer, Product, User


ADMIN_EMAIL = "admin.demo@stockflow.test"
USER_EMAIL = "user.demo@stockflow.test"
DEFAULT_ADMIN_PASSWORD = "DemoAdmin123!"
DEFAULT_USER_PASSWORD = "DemoUser123!"
DEMO_CATALOG = PROJECT_ROOT / "data_samples" / "demo_catalog.json"


class DemoDataError(ValueError):
    pass


def seed_demo_data(admin_password, user_password):
    """Stage missing records in the current transaction; the caller commits it."""
    for role, password in (("admin", admin_password), ("user", user_password)):
        if len(password) < 8:
            raise DemoDataError(f"The {role} password must contain at least 8 characters.")

    data = json.loads(DEMO_CATALOG.read_text(encoding="utf-8"))
    created = Counter({name: 0 for name in (
        "users", "company_profiles", "categories", "products", "offers", "carts", "cart_items",
    )})

    def add(record):
        db.session.add(record)
        db.session.flush()
        created[record.__tablename__] += 1
        return record

    def account(email, name, role, password):
        existing = db.session.scalar(db.select(User).where(User.email == email))
        if existing is not None:
            if existing.role != role:
                raise DemoDataError(
                    f"Account {email} already has a different role; it was not changed."
                )
            return existing
        user = User(email=email, full_name=name, role=role)
        user.set_password(password)
        return add(user)

    admin = account(ADMIN_EMAIL, "Demo Administrators", "admin", admin_password)
    buyer = account(USER_EMAIL, "Demo Pircējs", "user", user_password)
    if db.session.scalar(db.select(CompanyProfile).where(CompanyProfile.user_id == buyer.id)) is None:
        add(CompanyProfile(
            user=buyer, company_name="Demo Uzņēmums SIA", registration_no="DEMO-40000000001",
            address="Demonstrācijas iela 1, Rīga", vat_no=None, phone=None,
        ))

    categories = {}
    for fields in data["categories"]:
        category = db.session.scalar(db.select(Category).where(Category.name == fields["name"]))
        categories[fields["name"]] = category if category is not None else add(Category(**fields))

    products = {}
    for fields in data["products"]:
        product = db.session.scalar(db.select(Product).where(Product.sku == fields["sku"]))
        if product is None:
            values = {key: value for key, value in fields.items() if key != "category"}
            product = add(Product(category=categories[fields["category"]], **values))
        products[fields["sku"]] = product

    offers = {}
    for fields in data["offers"]:
        product = products[fields["product_sku"]]
        # A reserved supplier SKU identifies a demo offer even after price or name edits.
        matches = db.session.scalars(db.select(Offer).where(
            Offer.product_id == product.id, Offer.supplier_sku == fields["supplier_sku"],
        )).all()
        if len(matches) > 1:
            raise DemoDataError(
                f"Multiple offers use demo SKU {fields['supplier_sku']}; resolve the duplicate first."
            )
        if matches:
            offer = matches[0]
        else:
            values = {key: value for key, value in fields.items() if key != "product_sku"}
            for field in ("unit_price", "delivery_price"):
                values[field] = Decimal(values[field])
            offer = add(Offer(product=product, created_by_admin=admin, data_source="manual", **values))
        offers[fields["supplier_sku"]] = offer

    # Do not refill an existing cart: its owner may have checked out or removed items.
    if db.session.scalar(db.select(Cart).where(Cart.user_id == buyer.id)) is None:
        cart = add(Cart(user=buyer))
        for fields in data["cart_items"]:
            offer = offers[fields["supplier_sku"]]
            quantity = fields["quantity"]
            if not (offer.is_active and offer.product.is_active
                    and offer.min_order_qty <= quantity <= offer.stock_qty):
                continue  # Preserve edited offers without inserting invalid cart rows.
            add(CartItem(cart=cart, offer=offer, quantity=quantity))

    return dict(created)
