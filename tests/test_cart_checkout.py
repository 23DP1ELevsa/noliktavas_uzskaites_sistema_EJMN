from decimal import Decimal

import pytest
from sqlalchemy.exc import OperationalError

from backend.app.extensions import db
from backend.app.models import CartItem, CompanyProfile, Offer, Order, Product, User
from backend.app.services.cart import load_cart_summary
from test_comparison import comparison_data, sign_in


def add_to_cart(client, token, offer, quantity):
    return client.post("/cart/items", data={"csrf_token": token, "offer_id": offer.id, "quantity": quantity})


def add_profile(buyer):
    profile = CompanyProfile(user=buyer, company_name="Testa uzņēmums", registration_no="40100000001",
                             address="Rīga, Adrese 1", delivery_address="Rīga, Piegāde 2")
    db.session.add(profile)
    db.session.commit()
    return profile


def review_data(client, token):
    assert client.get("/orders/checkout").status_code == 200
    with client.session_transaction() as session:
        return {"csrf_token": token, "review_token": session["checkout_review"]["token"]}


def test_supplier_groups_have_separate_exact_subtotals_and_delivery(comparison_data):
    client, product, offers, buyer = comparison_data
    token = sign_in(client)
    second_product = Product(name="Otra prece", sku="SECOND", category=product.category)
    db.session.add(second_product)
    same_supplier = Offer(product=second_product, created_by_admin=offers[0].created_by_admin,
                          supplier_name=offers[0].supplier_name, unit_price=Decimal("0.10"),
                          delivery_price=Decimal("2.50"), stock_qty=50, vat_included=True)
    db.session.add(same_supplier)
    db.session.commit()
    for offer, quantity in ((offers[0], 2), (offers[1], 3), (same_supplier, 3)):
        add_to_cart(client, token, offer, quantity)
    summary = load_cart_summary(buyer.id)
    assert len(summary["groups"]) == 2
    assert summary["subtotal"] == Decimal("13.30")
    assert summary["delivery_total"] == Decimal("12.50")
    assert summary["total"] == Decimal("25.80")
    group = next(group for group in summary["groups"] if group["supplier"] == offers[0].supplier_name)
    assert len(group["rows"]) == 2
    assert group["subtotal"] == Decimal("4.30") and group["delivery"] == Decimal("12.50")
    html = client.get("/cart").get_data(as_text=True)
    assert html.count('class="supplier-group"') == 2
    assert "13.30 €" in html and "12.50 €" in html and "25.80 €" in html
    assert "Daļa cenu ir bez PVN" in html
    assert 'href="/orders/checkout"' in html
    item = db.session.scalar(db.select(CartItem).where(CartItem.offer_id == same_supplier.id))
    client.post(f"/cart/items/{item.id}/remove", data={"csrf_token": token})
    assert load_cart_summary(buyer.id)["total"] == Decimal("23.00")


def test_empty_or_invalid_cart_cannot_proceed_to_checkout(comparison_data):
    client, _, offers, buyer = comparison_data
    token = sign_in(client)
    assert client.get("/orders/checkout").status_code == 302
    assert 'href="/orders/checkout"' not in client.get("/cart").get_data(as_text=True)
    add_to_cart(client, token, offers[0], 5)
    offers[0].stock_qty = 4
    db.session.commit()
    summary = load_cart_summary(buyer.id)
    assert not summary["can_checkout"]
    html = client.get("/cart").get_data(as_text=True)
    assert "Nepietiekams atlikums" in html and 'href="/orders/checkout"' not in html
    assert client.get("/orders/checkout").headers["Location"].endswith("/cart")


def test_checkout_uses_profile_and_creates_snapshot_then_clears_cart(comparison_data):
    client, product, offers, buyer = comparison_data
    token = sign_in(client)
    profile = add_profile(buyer)
    offers[0].vat_rate = Decimal('21.00')
    offers[1].vat_rate = Decimal('12.00')
    db.session.commit()
    add_to_cart(client, token, offers[0], 2)
    add_to_cart(client, token, offers[1], 3)
    data = review_data(client, token)
    html = client.get("/orders/checkout").get_data(as_text=True)
    assert profile.company_name in html and profile.delivery_address in html
    data = review_data(client, token)
    response = client.post("/orders/checkout", data=dict(data, total="0.01"))
    assert response.status_code == 302
    order = db.session.scalar(db.select(Order))
    assert order.user_id == buyer.id and order.company_profile_id == profile.id
    assert order.status == "iesniegts" and order.total_amount == Decimal("23.00")
    assert len(order.items) == 2
    assert {item.vat_rate for item in order.items} == {Decimal('21.00'), Decimal('12.00')}
    assert {item.currency for item in order.items} == {'EUR'}
    assert sum(item.line_total for item in order.items) == order.total_amount
    assert db.session.scalar(db.select(db.func.count(CartItem.id))) == 0
    assert "Pieteikums iesniegts" in client.get(response.headers["Location"]).get_data(as_text=True)
    offers[0].unit_price = Decimal("99.99")
    product.name = "Jauns nosaukums"
    db.session.commit()
    assert order.items[0].unit_price == Decimal("2.00")
    assert order.items[0].product_name == "Salīdzināma prece"
    client.post("/orders/checkout", data=data)
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 1
    other = User(email="other-order@example.test", full_name="Other", role="user")
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": other.email, "password": "password123"})
    assert client.get(f"/orders/{order.id}").status_code == 404


@pytest.mark.parametrize("change", ["price", "delivery", "quantity", "company"])
def test_changed_review_requires_confirmation_without_creating_an_order(comparison_data, change):
    client, _, offers, buyer = comparison_data
    token = sign_in(client)
    profile = add_profile(buyer)
    add_to_cart(client, token, offers[0], 2)
    data = review_data(client, token)
    if change == "price":
        offers[0].unit_price = Decimal("4.00")
    elif change == "delivery":
        offers[0].delivery_price = Decimal("3.00")
    elif change == "quantity":
        db.session.scalar(db.select(CartItem)).quantity = 3
    else:
        profile.delivery_address = "Cita adrese"
    db.session.commit()
    response = client.post("/orders/checkout", data=data, follow_redirects=True)
    assert "dati ir mainījušies" in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 0
    assert db.session.scalar(db.select(CartItem)) is not None


@pytest.mark.parametrize("change", ["stock", "offer", "product"])
def test_checkout_rechecks_availability(comparison_data, change):
    client, product, offers, buyer = comparison_data
    token = sign_in(client)
    add_profile(buyer)
    add_to_cart(client, token, offers[0], 2)
    data = review_data(client, token)
    if change == "stock":
        offers[0].stock_qty = 1
    elif change == "offer":
        offers[0].is_active = False
    else:
        product.is_active = False
    db.session.commit()
    response = client.post("/orders/checkout", data=data)
    assert response.headers["Location"].endswith("/cart")
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 0
    assert db.session.scalar(db.select(CartItem)) is not None


def test_checkout_requires_login_profile_csrf_and_review(comparison_data):
    client, _, offers, buyer = comparison_data
    assert client.get("/orders/checkout").status_code == 302
    assert client.post("/orders/checkout").status_code == 302
    token = sign_in(client)
    add_to_cart(client, token, offers[0], 2)
    html = client.get("/orders/checkout").get_data(as_text=True)
    assert "Papildināt uzņēmuma profilu" in html
    assert 'type="submit" disabled' in html
    assert client.post("/orders/checkout", data={}).status_code == 400
    client.post("/orders/checkout", data=review_data(client, token))
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 0
    add_profile(buyer)
    client.post("/orders/checkout", data={"csrf_token": token, "review_token": "wrong"})
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 0


def test_database_failure_shows_message_and_rolls_back_cart_update(comparison_data, monkeypatch):
    client, _, offers, _ = comparison_data
    token = sign_in(client)
    add_to_cart(client, token, offers[0], 2)
    item = db.session.scalar(db.select(CartItem))
    original_commit = db.session.commit
    def fail_commit():
        db.session.flush()
        raise OperationalError("sensitive query", {}, Exception("database unavailable"))
    monkeypatch.setattr(db.session, "commit", fail_commit)
    response = client.post(f"/cart/items/{item.id}/update", data={"csrf_token": token, "quantity": "3"})
    assert response.status_code == 503
    html = response.get_data(as_text=True)
    assert "Darbību neizdevās pabeigt" in html and "sensitive query" not in html
    monkeypatch.setattr(db.session, "commit", original_commit)
    db.session.refresh(item)
    assert item.quantity == 2


def test_failed_submission_preserves_cart_and_does_not_leave_partial_order(comparison_data, monkeypatch):
    client, _, offers, buyer = comparison_data
    token = sign_in(client)
    add_profile(buyer)
    add_to_cart(client, token, offers[0], 2)
    data = review_data(client, token)
    def fail_commit():
        db.session.flush()
        raise OperationalError("statement", {}, Exception("offline"))
    monkeypatch.setattr(db.session, "commit", fail_commit)
    assert client.post("/orders/checkout", data=data).status_code == 503
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 0
    assert db.session.scalar(db.select(CartItem)).quantity == 2
