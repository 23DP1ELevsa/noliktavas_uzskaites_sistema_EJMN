from datetime import datetime
from decimal import Decimal

import pytest

from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Category, Offer, Product, User
from backend.app.services.comparison import comparison_rows, parse_quantity


@pytest.fixture
def comparison_data(database_app):
    admin = User(email="supplier@example.test", full_name="Admin", role="admin")
    admin.set_password("password123")
    buyer = User(email="buyer@example.test", full_name="Buyer", role="user")
    buyer.set_password("password123")
    product = Product(name="Salīdzināma prece", sku="COMPARE", description="Preces apraksts",
                      image_url="https://example.test/product.png", category=Category(name="Testa preces"))
    offers = [
        Offer(product=product, created_by_admin=admin, supplier_name="Lēta vienība",
              unit_price=Decimal("2.00"), delivery_price=Decimal("10.00"),
              stock_qty=20, min_order_qty=1, delivery_days=5, vat_included=True,
              updated_at=datetime(2026, 10, 11, 8, 30)),
        Offer(product=product, created_by_admin=admin, supplier_name="Lēta piegāde",
              unit_price=Decimal("3.00"), delivery_price=Decimal("0.00"),
              stock_qty=15, min_order_qty=2, delivery_days=1, vat_included=False),
        Offer(product=product, created_by_admin=admin, supplier_name="Nav atlikuma",
              unit_price=Decimal("4.00"), delivery_price=Decimal("0.00"),
              stock_qty=0, vat_included=True),
        Offer(product=product, created_by_admin=admin, supplier_name="Slēpts piedāvājums",
              unit_price=Decimal("1.00"), vat_included=True, is_active=False),
    ]
    db.session.add_all([buyer, *offers])
    db.session.commit()
    return database_app.test_client(), product, offers, buyer


def sign_in(client):
    client.post("/auth/login", data={"email": "buyer@example.test", "password": "password123"})
    client.get("/cart")
    with client.session_transaction() as session:
        return session["cart_csrf_token"]


def test_comparison_shows_all_fields_and_sorts_by_quantity_total(comparison_data):
    client, product, offers, _ = comparison_data
    html = client.get(f"/catalog/products/{product.id}?quantity=2").get_data(as_text=True)
    for text in (product.name, "Preces apraksts", product.image_url, "Noliktavā",
                 "Minimālais daudzums", "Piegādes maksa", "Piegādes termiņš",
                 "Dati atjaunināti", "2026-10-11T08:30:00Z", "Ar PVN", "Bez PVN", "14.00 €", "6.00 €"):
        assert text in html
    assert html.index("Lēta piegāde") < html.index("Lēta vienība")
    assert "Slēpts piedāvājums" not in html
    assert "Pieslēgties, lai pievienotu grozam" in html
    html = client.get(f"/catalog/products/{product.id}?quantity=12").get_data(as_text=True)
    assert html.index("Lēta vienība") < html.index("Lēta piegāde")
    html = client.get(f"/catalog/products/{product.id}?quantity=2&sort=total-desc").get_data(as_text=True)
    assert html.index("Lēta vienība") < html.index("Lēta piegāde")
    assert comparison_rows(offers[:2], 2, "delivery")[0]["offer"] == offers[1]
    assert comparison_rows(offers[:2], 2, "total-asc")[0]["total"] == Decimal("6.00")


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "NaN", "", "2147483648", "9" * 500])
def test_invalid_quantity_is_reported_without_server_error(comparison_data, value):
    client, product, _, _ = comparison_data
    response = client.get(f"/catalog/products/{product.id}", query_string={"quantity": value})
    assert response.status_code == 200
    assert 'role="alert"' in response.get_data(as_text=True)
    with pytest.raises(ValueError):
        parse_quantity(value)


def test_no_offers_inactive_product_and_invalid_sort(comparison_data):
    client, product, offers, _ = comparison_data
    assert 'role="alert"' in client.get(f"/catalog/products/{product.id}?sort=bad").get_data(as_text=True)
    for offer in offers:
        offer.is_active = False
    db.session.commit()
    assert "vēl nav aktīvu piedāvājumu" in client.get(f"/catalog/products/{product.id}").get_data(as_text=True)
    product.is_active = False
    db.session.commit()
    assert client.get(f"/catalog/products/{product.id}").status_code == 404


def test_cart_persists_merges_updates_and_removes(comparison_data):
    client, product, offers, buyer = comparison_data
    token = sign_in(client)
    data = {"csrf_token": token, "offer_id": offers[0].id, "quantity": "2"}
    response = client.post("/cart/items", data=data, follow_redirects=True)
    assert "pievienoti grozam" in response.get_data(as_text=True)
    assert client.post("/cart/items", data=data).status_code == 302
    item = db.session.scalar(db.select(CartItem))
    assert item.quantity == 4 and item.cart.user_id == buyer.id
    assert "18.00 €" in client.get("/cart").get_data(as_text=True)
    client.get("/auth/logout")
    sign_in(client)
    assert product.name in client.get("/cart").get_data(as_text=True)
    client.post(f"/cart/items/{item.id}/update", data={"csrf_token": token, "quantity": "7"})
    db.session.refresh(item)
    assert item.quantity == 7
    assert "24.00 €" in client.get("/cart").get_data(as_text=True)
    identifier = item.id
    client.post(f"/cart/items/{identifier}/remove", data={"csrf_token": token})
    assert db.session.get(CartItem, identifier) is None
    assert "Grozs vēl ir tukšs" in client.get("/cart").get_data(as_text=True)


@pytest.mark.parametrize("offer_index,quantity", [(0, "0"), (0, "-1"), (0, "1.5"),
                          (0, "2147483648"), (0, "21"), (1, "1"), (2, "1")])
def test_cart_rejects_invalid_or_unavailable_quantity(comparison_data, offer_index, quantity):
    client, _, offers, _ = comparison_data
    token = sign_in(client)
    response = client.post("/cart/items", data={"csrf_token": token,
                          "offer_id": offers[offer_index].id, "quantity": quantity}, follow_redirects=True)
    assert response.status_code == 200
    assert 'flash-error' in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(CartItem.id))) == 0


def test_cart_rechecks_stock_and_activity_and_enforces_ownership(comparison_data):
    client, product, offers, _ = comparison_data
    token = sign_in(client)
    data = {"csrf_token": token, "offer_id": offers[0].id, "quantity": "15"}
    client.post("/cart/items", data=data)
    item = db.session.scalar(db.select(CartItem))
    client.post("/cart/items", data=data)
    db.session.refresh(item)
    assert item.quantity == 15
    offers[0].stock_qty = 10
    db.session.commit()
    assert "Nepietiekams atlikums" in client.get("/cart").get_data(as_text=True)
    client.post(f"/cart/items/{item.id}/update", data={"csrf_token": token, "quantity": "11"})
    db.session.refresh(item)
    assert item.quantity == 15
    product.is_active = False
    db.session.commit()
    assert client.post("/cart/items", data=data).status_code == 404
    assert "vairs nav aktīvs" in client.get("/cart").get_data(as_text=True)
    other = User(email="other@example.test", full_name="Other", role="user")
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": other.email, "password": "password123"})
    assert product.name not in client.get("/cart").get_data(as_text=True)
    for action in ("update", "remove"):
        assert client.post(f"/cart/items/{item.id}/{action}", data={"csrf_token": token, "quantity": "2"}).status_code == 404
    assert db.session.get(CartItem, item.id) is not None


def test_cart_requires_login_and_csrf(comparison_data):
    client, _, offers, _ = comparison_data
    for path in ("/cart/items", "/cart/items/1/update", "/cart/items/1/remove"):
        assert client.post(path).status_code == 302
    assert client.get("/cart").status_code == 302
    token = sign_in(client)
    for invalid in (None, "invalid", "ā"):
        data = {"offer_id": offers[0].id, "quantity": "2"}
        if invalid is not None:
            data["csrf_token"] = invalid
        for path in ("/cart/items", "/cart/items/1/update", "/cart/items/1/remove"):
            assert client.post(path, data=data).status_code == 400
    assert client.post("/cart/items", data={"csrf_token": token, "offer_id": offers[3].id, "quantity": "1"}).status_code == 404
    assert db.session.scalar(db.select(db.func.count(Cart.id))) == 0
