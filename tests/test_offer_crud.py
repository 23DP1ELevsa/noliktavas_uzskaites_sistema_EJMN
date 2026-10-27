from datetime import datetime
from decimal import Decimal

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Offer, Order, OrderItem, Supplier, User
from conftest import MIGRATIONS
from test_admin import admin_data
from test_admin_panel import panel_inventory, create_offer


def test_manual_offer_reports_duplicate_supplier_code(panel_inventory):
    client, _, _, data = panel_inventory
    offer = create_offer(panel_inventory)
    response = client.post('/admin/supplier-products/new', data=data)
    assert response.status_code == 422
    assert 'id="supplier_sku-error"' in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Offer.id))) == 1
    assert client.post(f'/admin/supplier-products/{offer.id}/edit', data=data).status_code == 302


@pytest.mark.parametrize('field,value', [
    ('vat_rate', ''), ('vat_rate', '-1'), ('vat_rate', '100.01'), ('vat_rate', 'NaN'),
    ('vat_rate', '1.234'), ('vat_rate', '1e2'), ('vat_rate', '9' * 100),
    ('currency', ''), ('currency', 'USD'), ('currency', 'eur'),
])
def test_offer_terms_are_validated(panel_inventory, field, value):
    client, _, _, data = panel_inventory
    response = client.post('/admin/supplier-products/new', data=dict(data, **{field: value}))
    assert response.status_code == 422 and f'id="{field}-error"' in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Offer.id))) == 0


def test_vat_currency_filters_and_update_time(panel_inventory):
    client, _, product, data = panel_inventory
    offer = create_offer(panel_inventory)
    assert offer.vat_rate == Decimal('21.00') and offer.currency == 'EUR'
    offer.updated_at = datetime(2000, 1, 1)
    db.session.commit()
    response = client.post(f'/admin/supplier-products/{offer.id}/edit', data=dict(data, vat_rate='12,5', currency='EUR'))
    assert response.status_code == 302
    db.session.refresh(offer)
    assert offer.vat_rate == Decimal('12.50') and offer.updated_at > datetime(2000, 1, 1)
    html = client.get('/admin/supplier-products?q=SUP-001&status=active').get_data(as_text=True)
    assert product.name in html and '12.5 %' in html and 'EUR' in html and 'Atjaunināts:' in html
    assert product.name not in client.get('/admin/supplier-products?status=inactive').get_data(as_text=True)
    assert '12.5 %' in client.get(f'/catalog/products/{product.id}').get_data(as_text=True)


def test_unused_offer_is_deleted_only_after_confirmation(panel_inventory):
    client, supplier, product, data = panel_inventory
    offer = create_offer(panel_inventory)
    identifier = offer.id
    path = f'/admin/supplier-products/{identifier}/delete'
    assert 'Apstiprināt dzēšanu' in client.get(path).get_data(as_text=True)
    assert db.session.get(Offer, identifier) is not None
    assert client.post(path, data={'csrf_token': data['csrf_token']}).status_code == 400
    for invalid in ['', 'wrong', 'ā']:
        assert client.post(path, data={'csrf_token': invalid, 'confirmed': '1'}).status_code == 400
    assert db.session.get(Offer, identifier) is not None
    response = client.post(path, data={'csrf_token': data['csrf_token'], 'confirmed': '1'}, follow_redirects=True)
    assert response.status_code == 200 and 'Piedāvājums dzēsts.' in response.get_data(as_text=True)
    assert db.session.get(Offer, identifier) is None
    assert db.session.get(Supplier, supplier.id) is not None
    assert client.get(path).status_code == 404
    assert client.get(f'/catalog/products/{product.id}').status_code == 200


@pytest.mark.parametrize('relation', ['cart', 'order'])
def test_used_offer_is_deactivated_preserving_links(panel_inventory, relation):
    client, supplier, product, data = panel_inventory
    offer = create_offer(panel_inventory)
    admin = db.session.scalar(db.select(User).where(User.role == 'admin'))
    if relation == 'cart':
        item = CartItem(cart=Cart(user=admin), offer=offer, quantity=2)
    else:
        profile = admin.company_profile
        order = Order(user=admin, company_profile=profile, total_amount=Decimal('28.50'))
        db.session.add(order)
        item = OrderItem(order=order, offer=offer, supplier=supplier, product_name=product.name,
                         supplier_name=supplier.name, unit_price=offer.unit_price, quantity=2,
                         delivery_price=offer.delivery_price, line_total=Decimal('28.50'),
                         vat_included=True, vat_rate=offer.vat_rate, currency=offer.currency)
    db.session.add(item)
    db.session.commit()
    path = f'/admin/supplier-products/{offer.id}/delete'
    assert 'Apstiprināt deaktivizēšanu' in client.get(path).get_data(as_text=True)
    client.post(path, data={'csrf_token': data['csrf_token'], 'confirmed': '1'})
    db.session.refresh(offer)
    db.session.refresh(item)
    assert not offer.is_active and item.offer_id == offer.id
    assert supplier.name not in client.get(f'/catalog/products/{product.id}').get_data(as_text=True)
    if relation == 'order':
        client.post(f'/admin/supplier-products/{offer.id}/edit', data=dict(data, vat_rate='0', unit_price='20'))
        db.session.refresh(item)
        assert item.vat_rate == Decimal('21.00') and item.unit_price == Decimal('12.50') and item.currency == 'EUR'


@pytest.mark.parametrize('method', ['get', 'post'])
def test_offer_delete_requires_admin(database_app, method):
    client = database_app.test_client()
    assert getattr(client, method)('/admin/supplier-products/1/delete').status_code == 302
    client.post('/auth/register', data=admin_data())
    assert getattr(client, method)('/admin/supplier-products/1/delete').status_code == 403


def test_offer_terms_migration_preserves_existing_cart_order_and_prices(panel_inventory):
    _, supplier, product, _ = panel_inventory
    offer = create_offer(panel_inventory)
    admin = db.session.scalar(db.select(User).where(User.role == 'admin'))
    db.session.add(CartItem(cart=Cart(user=admin), offer=offer, quantity=2))
    profile = admin.company_profile
    order = Order(user=admin, company_profile=profile, total_amount=Decimal('28.50'))
    db.session.add(order)
    db.session.add(OrderItem(order=order, offer=offer, supplier=supplier, product_name=product.name,
                            supplier_name=supplier.name, unit_price=offer.unit_price, quantity=2,
                            delivery_price=offer.delivery_price, line_total=Decimal('28.50'), vat_included=True))
    db.session.commit()
    db.session.remove()
    downgrade(directory=MIGRATIONS, revision='0004_suppliers')
    assert 'vat_rate' not in {column['name'] for column in inspect(db.engine).get_columns('offers')}
    with db.engine.connect() as connection:
        assert connection.scalar(text('SELECT COUNT(*) FROM cart_items')) == 1
        assert connection.scalar(text('SELECT COUNT(*) FROM order_items')) == 1
    upgrade(directory=MIGRATIONS)
    db.session.remove()
    restored = db.session.scalar(db.select(Offer))
    item = db.session.scalar(db.select(OrderItem))
    assert restored.unit_price == Decimal('12.50') and restored.vat_rate is None and restored.currency == 'EUR'
    assert item.line_total == Decimal('28.50') and item.vat_rate is None and item.currency == 'EUR'
    assert db.session.scalar(db.select(CartItem)).quantity == 2


def test_manual_offer_blocks_second_active_code_for_same_supplier_product(panel_inventory):
    client, supplier, product, data = panel_inventory
    old = create_offer(panel_inventory)
    second = dict(data, supplier_sku="SUP-002", unit_price="7.20")
    response = client.post("/admin/supplier-products/new", data=second)
    assert response.status_code == 422
    assert 'id="product_id-error"' in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Offer.id))) == 1
    # An inactive historical offer is permitted, and the first can be edited.
    second.pop("is_active")
    assert client.post("/admin/supplier-products/new", data=second).status_code == 302
    assert db.session.scalar(db.select(db.func.count(Offer.id))) == 2
    assert client.post(f"/admin/supplier-products/{old.id}/edit", data=data).status_code == 302
