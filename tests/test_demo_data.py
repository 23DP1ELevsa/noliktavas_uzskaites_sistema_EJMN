from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Category, CompanyProfile, Offer, Product, User
from backend.app.services import demo_data


def counts():
    return {model.__tablename__: db.session.scalar(db.select(db.func.count()).select_from(model))
            for model in (User, CompanyProfile, Category, Product, Offer, Cart, CartItem)}


def seed(app, *args, **kwargs):
    result = app.test_cli_runner().invoke(args=["seed-demo", *args], **kwargs)
    assert result.exit_code == 0, result.output
    return result


def test_seed_creates_complete_demo_dataset(database_app):
    result = seed(database_app)
    assert counts() == {
        "users": 2, "company_profiles": 1, "categories": 4, "products": 10,
        "offers": 18, "carts": 1, "cart_items": 2,
    }
    assert "offers=18" in result.output
    assert db.session.scalar(db.select(db.func.count(db.distinct(Offer.supplier_name)))) == 3
    offers = db.session.scalars(db.select(Offer)).all()
    assert all(offer.created_by_admin.role == "admin" for offer in offers)
    assert all(offer.product.sku.startswith("DEMO-") for offer in offers)
    assert len({offer.unit_price for offer in offers}) > 5
    assert len({offer.min_order_qty for offer in offers}) > 3
    assert any(offer.stock_qty == 0 for offer in offers)
    assert any(0 < offer.stock_qty < offer.min_order_qty for offer in offers)
    assert {offer.vat_included for offer in offers} == {True, False}
    buyer = db.session.scalar(db.select(User).where(User.email == demo_data.USER_EMAIL))
    assert buyer.company_profile.company_name == "Demo Uzņēmums SIA"
    rows = buyer.cart.items
    assert len({item.offer.supplier_name for item in rows}) == 2
    assert all(item.offer.min_order_qty <= item.quantity <= item.offer.stock_qty for item in rows)
    total = sum(item.quantity * item.offer.unit_price + item.offer.delivery_price for item in rows)
    assert total == Decimal("48.48")


def test_seed_is_repeatable_and_preserves_ids_and_passwords(database_app):
    seed(database_app)
    before = counts()
    ids = {model.__tablename__: list(db.session.scalars(db.select(model.id).order_by(model.id)))
           for model in (User, CompanyProfile, Category, Product, Offer, Cart, CartItem)}
    hashes = list(db.session.scalars(db.select(User.password_hash).order_by(User.id)))
    result = seed(database_app)
    assert counts() == before
    assert "Created: users=0, company_profiles=0, categories=0, products=0, offers=0, carts=0, cart_items=0" in result.output
    for model in (User, CompanyProfile, Category, Product, Offer, Cart, CartItem):
        assert list(db.session.scalars(db.select(model.id).order_by(model.id))) == ids[model.__tablename__]
    assert list(db.session.scalars(db.select(User.password_hash).order_by(User.id))) == hashes


def test_seed_preserves_edits_passwords_and_emptied_cart(database_app):
    seed(database_app)
    offer = db.session.scalar(db.select(Offer).where(Offer.supplier_sku == "DEMO-NT-USB"))
    offer.unit_price = Decimal("11.23")
    offer.supplier_name = "Renamed demo supplier"
    offer.is_active = False
    offer.product.name = "Edited demo product"
    buyer = db.session.scalar(db.select(User).where(User.email == demo_data.USER_EMAIL))
    buyer.set_password("changed-password")
    buyer.is_active = False
    buyer.company_profile.address = "Changed address"
    db.session.execute(delete(CartItem))
    db.session.commit()
    offer_id, buyer_id = offer.id, buyer.id
    seed(database_app, "--user-password", "different-password")
    db.session.remove()
    offer = db.session.get(Offer, offer_id)
    buyer = db.session.get(User, buyer_id)
    assert offer.unit_price == Decimal("11.23")
    assert offer.supplier_name == "Renamed demo supplier" and not offer.is_active
    assert offer.product.name == "Edited demo product"
    assert buyer.check_password("changed-password") and not buyer.is_active
    assert buyer.company_profile.address == "Changed address"
    assert counts()["cart_items"] == 0 and counts()["offers"] == 18


def test_seed_reuses_categories_and_keeps_unrelated_records(database_app):
    category = Category(name="Elektronika", description="Team description")
    product = Product(category=category, sku="TEAM-001", name="Team product")
    db.session.add(product)
    db.session.commit()
    category_id, product_id = category.id, product.id
    seed(database_app)
    assert counts()["categories"] == 4 and counts()["products"] == 11
    assert db.session.get(Category, category_id).description == "Team description"
    assert db.session.get(Product, product_id).name == "Team product"
    cable = db.session.scalar(db.select(Product).where(Product.sku == "DEMO-USB-C-001"))
    assert cable.category_id == category_id


@pytest.mark.parametrize("email", [demo_data.ADMIN_EMAIL, demo_data.USER_EMAIL])
def test_seed_does_not_change_existing_account_roles(database_app, email):
    conflicting_role = "user" if email == demo_data.ADMIN_EMAIL else "admin"
    account = User(email=email, full_name="Existing account", role=conflicting_role,
                   password_hash="existing-hash")
    db.session.add(account)
    db.session.commit()
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "different role" in result.output
    assert counts() == {"users": 1, "company_profiles": 0, "categories": 0,
                        "products": 0, "offers": 0, "carts": 0, "cart_items": 0}
    assert account.role == conflicting_role and account.password_hash == "existing-hash"


def test_seed_rolls_back_all_changes_on_invalid_offer(database_app, monkeypatch):
    data = json.loads(demo_data.DEMO_CATALOG.read_text(encoding="utf-8"))
    data["offers"][-1]["unit_price"] = "-1.00"
    monkeypatch.setattr(demo_data, "DEMO_CATALOG", SimpleNamespace(
        read_text=lambda **kwargs: json.dumps(data),
    ))
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "not saved" in result.output
    assert all(value == 0 for value in counts().values())


def test_seed_reports_invalid_json_without_changes(database_app, monkeypatch):
    monkeypatch.setattr(demo_data, "DEMO_CATALOG", SimpleNamespace(read_text=lambda **kwargs: "{"))
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "demo_catalog.json" in result.output
    assert all(value == 0 for value in counts().values())


def test_seed_rejects_duplicate_offer_identity(database_app):
    seed(database_app)
    original = db.session.scalar(db.select(Offer).where(Offer.supplier_sku == "DEMO-NT-USB"))
    db.session.add(Offer(product_id=original.product_id, created_by_admin_id=original.created_by_admin_id,
                         supplier_name="Another name", supplier_sku=original.supplier_sku,
                         unit_price=1, vat_included=True))
    db.session.commit()
    before = counts()
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "Multiple offers" in result.output
    assert counts() == before


def test_seed_restores_missing_offer_without_resetting_others(database_app):
    seed(database_app)
    offer = db.session.scalar(db.select(Offer).where(Offer.supplier_sku == "DEMO-BS-SCREWS"))
    db.session.delete(offer)
    db.session.commit()
    result = seed(database_app)
    assert "offers=1" in result.output
    assert counts()["offers"] == 18


def test_demo_accounts_can_log_in_with_hashed_passwords(database_app):
    seed(database_app)
    client = database_app.test_client()
    for email, password, role in (
        (demo_data.ADMIN_EMAIL, demo_data.DEFAULT_ADMIN_PASSWORD, "admin"),
        (demo_data.USER_EMAIL, demo_data.DEFAULT_USER_PASSWORD, "user"),
    ):
        user = db.session.scalar(db.select(User).where(User.email == email))
        assert user.role == role and user.password_hash != password
        assert user.check_password(password)
        response = client.post("/auth/login", data={"email": email, "password": password})
        assert response.status_code == 302
        with client.session_transaction() as session:
            assert session["_user_id"] == str(user.id)
        client.get("/auth/logout")


def test_demo_passwords_can_be_supplied_via_environment(database_app):
    result = seed(database_app, env={
        "DEMO_ADMIN_PASSWORD": "custom-admin-password", "DEMO_USER_PASSWORD": "custom-user-password",
    })
    admin = db.session.scalar(db.select(User).where(User.email == demo_data.ADMIN_EMAIL))
    buyer = db.session.scalar(db.select(User).where(User.email == demo_data.USER_EMAIL))
    assert admin.check_password("custom-admin-password")
    assert buyer.check_password("custom-user-password")
    assert "custom-admin-password" not in result.output


def test_seed_rejects_short_password_before_writing(database_app):
    result = database_app.test_cli_runner().invoke(args=["seed-demo", "--admin-password", "short"])
    assert result.exit_code != 0 and "8 characters" in result.output
    assert all(value == 0 for value in counts().values())


def test_demo_data_exercises_catalog_comparison_and_filters(database_app):
    seed(database_app)
    client = database_app.test_client()
    assert client.get("/catalog").json["count"] == 9
    cable = client.get("/catalog?q=kabelis").json["items"][0]
    assert cable["price"] == 8.49
    assert {offer["supplier_name"] for offer in cable["offers"]} == {
        "Demo NordTech", "Demo Baltic Supply",
    }
    assert len(cable["offers"]) == 2
    response = client.get("/catalog", query_string={
        "q": "kabelis", "supplier": "Demo NordTech", "min_price": "9", "max_price": "10", "in_stock": "true",
    })
    assert response.json["count"] == 1 and response.json["items"][0]["price"] == 9.99
    unavailable = client.get("/catalog?in_stock=false").json["items"]
    assert {item["sku"] for item in unavailable} == {"DEMO-CLEANER-001", "DEMO-GLOVES-001"}


def test_demo_categories_are_available_on_current_catalog_page(database_app):
    seed(database_app)
    client = database_app.test_client()
    page = client.get("/catalog/page")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'data-catalog-url="/catalog"' in html
    for category in db.session.scalars(db.select(Category)):
        assert category.name in html
        assert f'data-category="{category.id}"' in html
    assert 'href="/catalog/page"' in client.get("/").get_data(as_text=True)


def test_seed_requires_migrations_and_reports_a_clear_error():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "db upgrade" in result.output


def test_recreated_cart_skips_previously_modified_unavailable_offer(database_app):
    seed(database_app)
    cart = db.session.scalar(db.select(Cart))
    db.session.delete(cart)
    offer = db.session.scalar(db.select(Offer).where(Offer.supplier_sku == "DEMO-NT-USB"))
    offer.stock_qty = 0
    db.session.commit()
    seed(database_app)
    items = db.session.scalars(db.select(CartItem)).all()
    assert len(items) == 1 and items[0].offer.supplier_sku == "DEMO-OH-PAPER"
