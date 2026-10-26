"""Exercise stock through checkout, imports and administrator decisions."""

import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from flask_migrate import downgrade, upgrade
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.extensions import db
from backend.app.models import CartItem, Offer, Order, Supplier, User
from backend.app.services.offer_import import save_imported_offers
from conftest import MIGRATIONS
from test_comparison import comparison_data, sign_in
from test_cart_checkout import add_profile, add_to_cart, review_data
from test_order_workflow import submit, sign_in_admin


def balance(offer):
    db.session.refresh(offer)
    return offer.stock_qty, offer.allocated_qty


def decide(client, order, decision):
    token = sign_in_admin(client, order.id)
    return client.post(f"/admin/orders/{order.id}", data={
        "csrf_token": token, "decision": decision, "admin_note": "Testa lēmums.",
    })


def test_submission_reduces_only_selected_offer_and_retry_does_not_repeat(comparison_data):
    client, product, offers, _ = comparison_data
    response, data = submit(comparison_data)
    assert response.status_code == 302
    assert balance(offers[0]) == (18, 2)
    assert balance(offers[1]) == (15, 0)
    assert db.session.scalar(db.select(Order)).stock_deducted
    assert "18" in client.get(f"/catalog/products/{product.id}").get_data(as_text=True)
    client.post("/orders/checkout", data=data)
    assert balance(offers[0]) == (18, 2)
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 1


@pytest.mark.parametrize("decision,expected", [("approve", (18, 2)), ("decline", (20, 0))])
def test_decision_and_repeated_decision_change_stock_once(comparison_data, decision, expected):
    client, _, offers, _ = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    assert decide(client, order, decision).status_code == 302
    assert balance(offers[0]) == expected
    assert decide(client, order, decision).status_code == 409
    assert balance(offers[0]) == expected


def test_last_units_can_be_approved_and_second_buyer_cannot_purchase_them(comparison_data):
    client, _, offers, buyer = comparison_data
    offers[0].stock_qty = 2
    db.session.commit()
    submit(comparison_data)
    assert balance(offers[0]) == (0, 2)
    order = db.session.scalar(db.select(Order))
    assert decide(client, order, "approve").status_code == 302
    other = User(email="second-stock@test.lv", full_name="Other", role="user")
    other.set_password("Password123!")
    db.session.add(other)
    db.session.commit()
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": other.email, "password": "Password123!"})
    client.get("/cart")
    with client.session_transaction() as session:
        token = session["cart_csrf_token"]
    add_to_cart(client, token, offers[0], 1)
    assert db.session.scalar(db.select(CartItem)) is None
    assert balance(offers[0]) == (0, 2)


@pytest.mark.parametrize("stage", ["submission", "decline"])
def test_failed_transaction_rolls_back_stock_and_order(comparison_data, monkeypatch, stage):
    from backend.app.routes import admin_orders, orders
    client, _, offers, _ = comparison_data
    if stage == "submission":
        target, name = orders, "notify_submission"
    else:
        submit(comparison_data)
        target, name = admin_orders, "notify_decision"
    original = getattr(target, name)

    def fail(order):
        original(order)
        db.session.flush()
        raise SQLAlchemyError("test failure after stock update")

    monkeypatch.setattr(target, name, fail)
    if stage == "submission":
        response, _ = submit(comparison_data)
        expected = (20, 0)
    else:
        response = decide(client, db.session.scalar(db.select(Order)), "decline")
        expected = (18, 2)
    assert response.status_code == 503
    assert balance(offers[0]) == expected


@pytest.mark.parametrize("source", ["CSV", "JSON"])
@pytest.mark.parametrize("decision", ["approve", "decline"])
def test_reimport_retains_local_allocations(comparison_data, source, decision):
    client, product, offers, _ = comparison_data
    offer = offers[0]
    offer.supplier = Supplier(name=offer.supplier_name, name_key=offer.supplier_name.casefold())
    offer.supplier_sku = "STOCK-TEST"
    db.session.commit()
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    row = dict(product_sku=product.sku, supplier_id=offer.supplier_id, supplier_sku=offer.supplier_sku,
               currency="EUR", unit_price="2.00", vat_included=True, min_order_qty=1,
               stock_qty=20, delivery_days=5, delivery_price="10.00")
    for _ in range(2):
        save_imported_offers([row], source=source, admin_id=offer.created_by_admin_id)
        assert balance(offer) == (18, 2)
    assert decide(client, order, decision).status_code == 302
    save_imported_offers([row], source=source, admin_id=offer.created_by_admin_id)
    assert balance(offer) == ((18, 2) if decision == "approve" else (20, 0))


def test_supplier_shortage_does_not_create_stock_when_order_is_declined(comparison_data):
    client, _, offers, _ = comparison_data
    submit(comparison_data)
    offer = offers[0]
    offer.imported_stock_qty, offer.stock_qty = 1, 0
    db.session.commit()
    order = db.session.scalar(db.select(Order))
    assert decide(client, order, "approve").status_code == 409
    assert decide(client, order, "decline").status_code == 302
    assert balance(offer) == (1, 0)


@pytest.mark.parametrize("decision,expected", [("approve", (18, 2)), ("decline", (20, 0))])
def test_legacy_order_is_not_returned_or_deducted_twice(comparison_data, decision, expected):
    client, _, offers, _ = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    # Simulate the state of an order created before 0008.
    order.stock_deducted = False
    offers[0].stock_qty, offers[0].allocated_qty = 20, 0
    db.session.commit()
    assert decide(client, order, decision).status_code == 302
    assert balance(offers[0]) == expected


def test_stock_migration_preserves_history_and_does_not_retroactively_deduct(comparison_data):
    submit(comparison_data)
    db.session.remove()
    downgrade(directory=MIGRATIONS, revision="0007_offer_import_identity")
    with db.engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM order_items")) == 1
        assert connection.scalar(text("SELECT stock_qty FROM offers ORDER BY id LIMIT 1")) == 18
    upgrade(directory=MIGRATIONS)
    db.session.remove()
    assert not db.session.scalar(db.select(Order)).stock_deducted
    assert db.session.scalar(db.select(Offer).order_by(Offer.id)).stock_qty == 18


def test_two_buyers_cannot_checkout_the_same_last_units(comparison_data, database_app, monkeypatch):
    if db.engine.dialect.name != "mysql":
        pytest.skip("Requires MySQL row locks and separate connections.")
    from backend.app.routes import orders
    client, _, offers, buyer = comparison_data
    offer = offers[0]
    offer.stock_qty = 2
    other = User(email="racing-buyer@test.lv", full_name="Other", role="user")
    other.set_password("Password123!")
    db.session.add(other)
    db.session.commit()
    token = sign_in(client)
    add_profile(buyer)
    add_to_cart(client, token, offer, 2)
    data = review_data(client, token)
    offer_id, other_id, other_email = offer.id, other.id, other.email
    db.session.remove()
    second = database_app.test_client()
    # Each client needs its own Flask-Login cache during setup too.
    with database_app.app_context():
        second.post("/auth/login", data={"email": other_email, "password": "Password123!"})
        second.get("/cart")
        with second.session_transaction() as session:
            token2 = session["cart_csrf_token"]
        add_profile(db.session.get(User, other_id))
        add_to_cart(second, token2, db.session.get(Offer, offer_id), 2)
        data2 = review_data(second, token2)
        db.session.remove()
    db.session.remove()  # Release setup reads before independent request transactions.
    barrier = Barrier(2)
    original = orders.load_cart_summary

    def synchronized(user_id, *, lock=False):
        if lock:
            barrier.wait(timeout=10)
        return original(user_id, lock=lock)

    monkeypatch.setattr(orders, "load_cart_summary", synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(c.post, "/orders/checkout", data=d)
                   for c, d in [(client, data), (second, data2)]]
        responses = [f.result(timeout=20) for f in futures]
    assert all(r.status_code == 302 for r in responses)
    assert sum(r.headers["Location"].endswith("/cart") for r in responses) == 1
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 1
    assert db.session.scalar(db.select(db.func.count(CartItem.id))) == 1
    assert balance(db.session.get(Offer, offer_id)) == (0, 2)
