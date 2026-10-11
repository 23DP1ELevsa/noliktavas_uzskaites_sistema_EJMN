from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Category, Offer, Product, Supplier, User
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
              stock_qty=15, min_order_qty=2, delivery_days=1, vat_included=False,
              vat_rate=Decimal("21.00")),
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
                 "Dati atjaunināti", "2026-10-11T08:30:00Z", "Ar PVN", "Bez PVN", "14.00 €", "7.26 €", "1.26 €"):
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
    assert comparison_rows(offers[:2], 2, "total-asc")[0]["total_with_vat"] == Decimal("7.26")


@pytest.mark.parametrize("price,quantity,rate,included,delivery,expected", [
    ("10.00", 3, "21.00", False, "4.50", "40.80"),
    ("10.00", 3, "21.00", True, "4.50", "34.50"),
    ("10.00", 3, None, True, "4.50", "34.50"),
    ("10.00", 3, "0.00", False, "4.50", "34.50"),
    ("0.05", 1, "10.00", False, "0.00", "0.06"),
    ("0.05", 3, "10.00", False, "0.00", "0.17"),
    ("0.99", 7, "12.50", False, "2.35", "10.15"),
])
def test_comparison_vat_rounding_and_delivery(price, quantity, rate, included, delivery, expected):
    offer = SimpleNamespace(id=1, unit_price=Decimal(price), delivery_price=Decimal(delivery),
                            vat_rate=Decimal(rate) if rate is not None else None,
                            vat_included=included, min_order_qty=1, stock_qty=100)
    row = comparison_rows([offer], quantity, "total-asc")[0]
    assert row["total_with_vat"] == Decimal(expected)
    assert row["total_with_vat"] == row["subtotal_with_vat"] + offer.delivery_price
    assert row["vat_error"] is None
    # Cart/checkout retain the supplier's declared prices and VAT status.
    assert row["total"] == offer.unit_price * quantity + offer.delivery_price


def test_vat_changes_ranking_and_unknown_rate_is_last_in_both_directions(comparison_data):
    client, product, offers, _ = comparison_data
    offers[0].unit_price, offers[0].delivery_price = Decimal("11.00"), Decimal("0.00")
    offers[1].unit_price = Decimal("10.00")
    offers[2].vat_included, offers[2].vat_rate = False, None
    db.session.commit()
    rows = comparison_rows(offers[:3], 2, "total-asc")
    assert [row["offer"].id for row in rows] == [offers[0].id, offers[1].id, offers[2].id]
    assert rows[0]["total_with_vat"] == Decimal("22.00")
    assert rows[1]["total_with_vat"] == Decimal("24.20")
    assert rows[2]["total_with_vat"] is None and rows[2]["vat_error"]
    rows = comparison_rows(offers[:3], 2, "total-desc")
    assert [row["offer"].id for row in rows] == [offers[1].id, offers[0].id, offers[2].id]
    for sort in ("total-asc", "total-desc"):
        html = client.get(f"/catalog/products/{product.id}?quantity=2&sort={sort}").get_data(as_text=True)
        assert "Nav norādīta PVN likme" in html
        assert "Nav aprēķināma" in html
        assert html.index("Nav atlikuma") > html.index("Lēta vienība")
        assert html.index("Nav atlikuma") > html.index("Lēta piegāde")


def test_comparison_reports_both_quantity_restrictions_and_keeps_common_quantity(comparison_data):
    client, product, offers, _ = comparison_data
    offers[0].min_order_qty, offers[0].stock_qty = 5, 1
    db.session.commit()
    row = comparison_rows([offers[0]], 2, "total-asc")[0]
    assert "Minimālais daudzums: 5." in row["error"]
    assert "Nepietiekams atlikums. Noliktavā: 1." in row["error"]
    assert row["total_with_vat"] == Decimal("14.00")
    html = client.get(f"/catalog/products/{product.id}?quantity=2").get_data(as_text=True)
    assert "Nav pieejams izvēlētajā daudzumā" in html
    assert "Minimālais daudzums: 5." in html and "Noliktavā: 1." in html
    assert "14.00 €" in html and "7.26 €" in html


def test_comparison_hides_active_offer_from_inactive_supplier(comparison_data):
    client, product, offers, _ = comparison_data
    offers[0].supplier = Supplier(name="Deaktivizēts", name_key="deaktivizēts", is_active=False)
    db.session.commit()
    html = client.get(f"/catalog/products/{product.id}?quantity=2").get_data(as_text=True)
    assert "Lēta vienība" not in html
    assert "Lēta piegāde" in html


def test_comparison_total_ties_are_stable(comparison_data):
    _, _, offers, _ = comparison_data
    offers[0].unit_price, offers[0].delivery_price = Decimal("3.00"), Decimal("0.00")
    offers[1].vat_included = True
    for sort in ("total-asc", "total-desc"):
        rows = comparison_rows(list(reversed(offers[:2])), 2, sort)
        assert [row["offer"].id for row in rows] == sorted(offer.id for offer in offers[:2])


def test_large_comparison_amount_is_rendered_without_float_rounding(comparison_data):
    client, product, offers, _ = comparison_data
    offer = offers[0]
    offer.unit_price = Decimal("99999999.99")
    offer.delivery_price = Decimal("99999999.99")
    offer.stock_qty = 2147483647
    offer.vat_included, offer.vat_rate = False, Decimal("100.00")
    db.session.commit()
    row = comparison_rows([offer], 2147483647, "total-asc")[0]
    expected = offer.unit_price * 2147483647 * 2 + offer.delivery_price
    assert row["total_with_vat"] == expected
    html = client.get(f"/catalog/products/{product.id}?quantity=2147483647").get_data(as_text=True)
    assert f'<strong class="offer-total">{expected} €</strong>' in html


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
