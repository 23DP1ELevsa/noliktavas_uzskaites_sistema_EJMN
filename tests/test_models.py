from datetime import datetime
from contextlib import contextmanager
from decimal import Decimal

import pytest
from flask_migrate import check, downgrade, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.app.extensions import db, load_user
from backend.app.models import (
    Cart, CartItem, Category, CompanyProfile, Offer, Order, OrderItem, Product, User,
)
from conftest import MIGRATIONS


@contextmanager
def constraint_violation():
    # PyMySQL classifies MariaDB CHECK error 4025 as OperationalError.
    with pytest.raises((IntegrityError, OperationalError)) as failure:
        yield
    if isinstance(failure.value, OperationalError):
        assert failure.value.orig.args[0] in {4025, 3819}


@pytest.fixture
def records(database_app):
    admin = User(email="admin@example.test", full_name="Administrators", role="admin")
    admin.set_password("test-password")
    user = User(email="user@example.test", full_name="Jānis Bērziņš")
    user.set_password("another-password")
    profile = CompanyProfile(user=user, company_name="SIA Pircējs", registration_no="40000000000",
                             address="Rīga, Testa iela 1")
    category = Category(name="Elektronika")
    product = Product(category=category, sku="USB-001", name="USB-C kabelis")
    offer = Offer(product=product, created_by_admin=admin, supplier_name="Piegādātājs",
                  unit_price=Decimal("8.99"), vat_included=True, stock_qty=10,
                  delivery_price=Decimal("2.00"))
    cart = Cart(user=user)
    cart_item = CartItem(cart=cart, offer=offer, quantity=2)
    order = Order(user=user, company_profile=profile, total_amount=Decimal("19.98"))
    item = OrderItem(order=order, offer=offer, product_name=product.name,
                     supplier_name=offer.supplier_name, unit_price=offer.unit_price,
                     quantity=2, delivery_price=offer.delivery_price,
                     line_total=Decimal("19.98"), vat_included=True)
    db.session.add_all([admin, user, profile, category, product, offer, cart, cart_item, order, item])
    db.session.commit()
    return {"admin": admin, "user": user, "profile": profile, "category": category,
            "product": product, "offer": offer, "cart": cart, "cart_item": cart_item,
            "order": order, "item": item}


def test_save_and_reload_all_nine_tables(database_app, records):
    identifiers = {name: row.id for name, row in records.items()}
    db.session.remove()
    user = db.session.get(User, identifiers["user"])
    assert user.full_name == "Jānis Bērziņš"
    assert user.company_profile.company_name == "SIA Pircējs"
    assert user.cart.items[0].offer.product.category.name == "Elektronika"
    order = user.orders[0]
    assert order.company_profile.user == user
    assert order.items[0].offer.created_by_admin.role == "admin"
    assert order.items[0].offer.created_by_admin.orders == []
    assert order.total_amount == Decimal("19.98")
    assert order.items[0].unit_price == Decimal("8.99")
    assert order.items[0].line_total == order.items[0].quantity * order.items[0].unit_price + order.items[0].delivery_price
    for model in [CompanyProfile, Category, Product, Offer, Cart, CartItem, Order, OrderItem]:
        assert len(db.session.scalars(db.select(model)).all()) == 1


def test_defaults_and_distinct_user_relationships(database_app, records):
    assert records["user"].role == "user"
    assert records["user"].is_active is True
    assert records["user"].created_at is not None
    assert records["product"].unit == "gab."
    assert records["product"].is_active is True
    assert records["offer"].min_order_qty == 1
    assert records["offer"].data_source == "manual"
    assert records["cart"].status == "active"
    assert records["order"].status == "iesniegts"
    assert records["order"].processed_by_admin is None
    assert records["order"].processed_at is None
    records["order"].processed_by_admin = records["admin"]
    records["order"].processed_at = datetime(2026, 10, 4, 10, 0)
    records["order"].status = "apstiprināts"
    db.session.commit()
    assert records["admin"].orders_processed == [records["order"]]
    assert records["order"].user == records["user"]


@pytest.mark.parametrize("duplicate", ["email", "sku", "category", "profile", "cart", "cart_item"])
def test_unique_constraints(database_app, records, duplicate):
    rows = {
        "email": lambda: User(email=records["user"].email, password_hash="hash", full_name="Duplicate"),
        "sku": lambda: Product(category_id=records["category"].id, sku="USB-001", name="Duplicate"),
        "category": lambda: Category(name="Elektronika"),
        "profile": lambda: CompanyProfile(user_id=records["user"].id, company_name="Other",
                                          registration_no="123", address="Rīga"),
        "cart": lambda: Cart(user_id=records["user"].id),
        "cart_item": lambda: CartItem(cart_id=records["cart"].id, offer_id=records["offer"].id, quantity=1),
    }
    db.session.add(rows[duplicate]())
    with constraint_violation():
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("record,field,value", [
    ("offer", "unit_price", -1), ("offer", "stock_qty", -1),
    ("offer", "min_order_qty", 0), ("offer", "delivery_price", -1),
    ("offer", "delivery_days", -1), ("offer", "data_source", "unsupported"),
    ("cart_item", "quantity", 0), ("item", "quantity", -1),
    ("item", "unit_price", -1), ("item", "delivery_price", -1),
    ("item", "line_total", -1), ("order", "total_amount", -1),
    ("order", "status", "unknown"), ("user", "role", "guest"),
    ("cart", "status", "closed"), ("product", "name", None),
])
def test_invalid_values_are_rejected(database_app, records, record, field, value):
    setattr(records[record], field, value)
    with constraint_violation():
        db.session.commit()
    db.session.rollback()


def test_foreign_keys_reject_missing_parent(database_app):
    db.session.add(Product(category_id=999999, sku="INVALID", name="Invalid"))
    with constraint_violation():
        db.session.commit()
    db.session.rollback()


def test_snapshot_survives_offer_changes_and_deletion(database_app, records):
    item_id = records["item"].id
    records["offer"].unit_price = Decimal("100.00")
    records["offer"].supplier_name = "Changed supplier"
    records["product"].name = "Changed product"
    db.session.commit()
    # Load the collections too, checking ORM and database deletion agree.
    assert records["offer"].order_items
    assert records["offer"].cart_items
    db.session.delete(records["offer"])
    db.session.commit()
    db.session.remove()
    item = db.session.get(OrderItem, item_id)
    assert item.offer_id is None
    assert item.product_name == "USB-C kabelis"
    assert item.supplier_name == "Piegādātājs"
    assert item.unit_price == Decimal("8.99")
    assert item.line_total == Decimal("19.98")
    assert db.session.scalar(db.select(db.func.count()).select_from(CartItem)) == 0


@pytest.mark.parametrize("record", ["category", "product", "user", "admin", "profile"])
def test_referenced_records_cannot_be_deleted(database_app, records, record):
    db.session.delete(records[record])
    with constraint_violation():
        db.session.commit()
    db.session.rollback()


def test_deleting_cart_cascades_to_items(database_app, records):
    db.session.delete(records["cart"])
    db.session.commit()
    assert db.session.scalar(db.select(db.func.count()).select_from(CartItem)) == 0
    assert db.session.get(Offer, records["offer"].id) is not None


def test_failed_order_transaction_leaves_no_partial_order(database_app, records):
    order = Order(user_id=records["user"].id, company_profile_id=records["profile"].id,
                  total_amount=Decimal("1.00"))
    db.session.add(order)
    db.session.flush()
    new_order_id = order.id
    db.session.add(OrderItem(order=order, product_name="Test", supplier_name="Supplier",
                             unit_price=1, quantity=0, delivery_price=0, line_total=1, vat_included=False))
    with constraint_violation():
        db.session.commit()
    db.session.rollback()
    assert db.session.get(Order, new_order_id) is None
    assert db.session.scalar(db.select(db.func.count()).select_from(Order)) == 1


def test_passwords_and_login_loader(database_app, records):
    user = records["user"]
    assert user.password_hash != "another-password"
    assert user.check_password("another-password")
    assert not user.check_password("wrong-password")
    assert load_user(str(user.id)) == user
    for identifier in [None, "invalid", "0", "-1", "99999999999999999999999"]:
        assert load_user(identifier) is None
    user.is_active = False
    db.session.commit()
    assert load_user(str(user.id)) is None


def test_server_defaults_apply_to_direct_sql(database_app):
    db.session.execute(text(
        "INSERT INTO users (email, password_hash, full_name) VALUES ('sql@example.test', 'hash', 'SQL User')"
    ))
    db.session.commit()
    user = db.session.scalar(db.select(User))
    assert user.role == "user" and user.is_active and user.created_at is not None


def test_migrations_are_repeatable_and_match_models(database_app, records):
    upgrade(directory=MIGRATIONS)
    assert db.session.get(User, records["user"].id) is not None
    check(directory=MIGRATIONS)
    assert set(inspect(db.engine).get_table_names()) == set(db.metadata.tables) | {"alembic_version"}
    result = database_app.test_cli_runner().invoke(args=["db-check"])
    assert result.exit_code == 0
    assert "all 9 application tables" in result.output


def test_initial_migration_can_be_reversed_and_reapplied(database_app):
    downgrade(directory=MIGRATIONS, revision="base")
    assert set(inspect(db.engine).get_table_names()) <= {"alembic_version"}
    result = database_app.test_cli_runner().invoke(args=["db-check"])
    assert result.exit_code != 0 and "Missing tables" in result.output
    upgrade(directory=MIGRATIONS)
    assert len(inspect(db.engine).get_table_names()) == 10
