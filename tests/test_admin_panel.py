from decimal import Decimal

import pytest

from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Category, Offer, Order, OrderItem, Product, Supplier, User
from test_admin import admin_data, login_admin


@pytest.fixture
def panel_inventory(database_app):
    client = database_app.test_client()
    login_admin(client)
    assert client.get('/admin').status_code == 200
    client.get('/admin/suppliers/new')
    with client.session_transaction() as session:
        token = session['product_csrf_token']
    assert client.post('/admin/suppliers/new', data={
        'csrf_token': token, 'name': 'Panelī izveidots piegādātājs',
        'delivery_price': '3,50', 'is_active': '1'}).status_code == 302
    supplier = db.session.scalar(db.select(Supplier))
    category = Category(name='Paneļa kategorija')
    db.session.add(category)
    db.session.commit()
    response = client.post(f'/admin/products/new?supplier_id={supplier.id}', data={
        'csrf_token': token, 'name': 'Administratora prece', 'sku': 'ADMIN-001',
        'category_id': category.id, 'unit': 'gab.', 'is_active': '1'})
    product = db.session.scalar(db.select(Product))
    assert response.status_code == 302
    assert '/admin/supplier-products/new?' in response.location
    assert f'supplier_id={supplier.id}' in response.location and f'product_id={product.id}' in response.location
    assert client.get(response.location).status_code == 200
    data = {'csrf_token': token, 'supplier_id': str(supplier.id), 'product_id': str(product.id),
            'supplier_sku': 'SUP-001', 'unit_price': '12,50', 'vat_included': '1', 'vat_rate': '21', 'currency': 'EUR',
            'stock_qty': '30', 'min_order_qty': '2', 'delivery_days': '3', 'is_active': '1'}
    return client, supplier, product, data


def create_offer(inventory):
    client, supplier, _, data = inventory
    response = client.post('/admin/supplier-products/new', data=data)
    assert response.status_code == 302 and response.location.endswith(f'/admin/suppliers/{supplier.id}')
    return db.session.scalar(db.select(Offer))


def test_admin_manually_adds_supplier_product_and_offer(panel_inventory):
    client, supplier, product, data = panel_inventory
    offer = create_offer(panel_inventory)
    assert offer.created_by_admin.role == 'admin' and offer.data_source == 'manual'
    assert offer.supplier_id == supplier.id and offer.product_id == product.id
    assert offer.unit_price == Decimal('12.50') and offer.delivery_price == Decimal('3.50')
    assert offer.vat_included and offer.stock_qty == 30 and offer.min_order_qty == 2 and offer.delivery_days == 3
    comparison = client.get(f'/catalog/products/{product.id}?quantity=2').get_data(as_text=True)
    assert supplier.name in comparison and '12.50' in comparison
    for path in ['/admin', '/admin/supplier-products', f'/admin/suppliers/{supplier.id}',
                 f'/admin/products/{product.id}', f'/admin/supplier-products/{offer.id}/edit']:
        response = client.get(path)
        assert response.status_code == 200
        assert 'aria-label="Paneļa sadaļas"' in response.get_data(as_text=True)
    assert product.name in client.get('/admin/supplier-products?q=ADMIN-001').get_data(as_text=True)
    assert product.name not in client.get('/admin/supplier-products?q=neeksistē').get_data(as_text=True)
    assert client.post(f'/admin/supplier-products/{offer.id}/edit', data=dict(data, unit_price='15.00', stock_qty='12')).status_code == 302
    db.session.refresh(offer)
    assert offer.unit_price == Decimal('15.00') and offer.stock_qty == 12


@pytest.mark.parametrize('field,value', [
    ('supplier_id', ''), ('supplier_id', '999999'), ('supplier_id', '9' * 100),
    ('product_id', ''), ('product_id', '999999'), ('product_id', '1.5'),
    ('unit_price', ''), ('unit_price', '-1'), ('unit_price', 'NaN'), ('unit_price', 'Infinity'),
    ('unit_price', '1.234'), ('unit_price', '1e2'), ('unit_price', '100000000'),
    ('vat_included', ''), ('vat_included', 'true'), ('stock_qty', '-1'),
    ('stock_qty', '2147483648'), ('min_order_qty', '0'), ('min_order_qty', '1.5'),
    ('delivery_days', '-1'), ('delivery_days', '9' * 100), ('supplier_sku', 'a' * 101),
])
def test_offer_validation_keeps_values_and_saves_nothing(panel_inventory, field, value):
    client, _, _, data = panel_inventory
    response = client.post('/admin/supplier-products/new', data=dict(data, **{field: value}))
    assert response.status_code == 422
    html = response.get_data(as_text=True)
    assert f'id="{field}-error"' in html and 'aria-invalid="true"' in html
    assert db.session.scalar(db.select(db.func.count(Offer.id))) == 0


def test_offer_deactivation_preserves_cart_and_order_history(panel_inventory):
    client, supplier, product, data = panel_inventory
    offer = create_offer(panel_inventory)
    admin = db.session.scalar(db.select(User).where(User.role == 'admin'))
    cart = Cart(user=admin)
    cart_item = CartItem(cart=cart, offer=offer, quantity=2)
    db.session.add(cart_item)
    order = Order(user=admin, company_profile=admin.company_profile, total_amount=Decimal('28.50'))
    db.session.add(order)
    order_item = OrderItem(order=order, supplier=supplier, offer=offer, product_name=product.name,
                           supplier_name=supplier.name, unit_price=Decimal('12.50'), quantity=2,
                           delivery_price=Decimal('3.50'), line_total=Decimal('28.50'), vat_included=True)
    db.session.add_all([cart_item, order_item])
    db.session.commit()
    inactive = dict(data, unit_price='20.00')
    inactive.pop('is_active')
    assert client.post(f'/admin/supplier-products/{offer.id}/edit', data=inactive).status_code == 302
    db.session.refresh(offer)
    db.session.refresh(order_item)
    assert not offer.is_active and offer.unit_price == Decimal('20.00')
    assert db.session.get(CartItem, cart_item.id).quantity == 2
    assert order_item.unit_price == Decimal('12.50') and order_item.line_total == Decimal('28.50')
    assert supplier.name not in client.get(f'/catalog/products/{product.id}').get_data(as_text=True)
    assert client.post(f'/admin/supplier-products/{offer.id}/edit', data=data).status_code == 302
    assert supplier.name in client.get(f'/catalog/products/{product.id}').get_data(as_text=True)


def test_existing_offer_identity_and_csrf_are_protected(panel_inventory):
    client, _, product, data = panel_inventory
    offer = create_offer(panel_inventory)
    other = Product(category=product.category, name='Cita prece', sku='OTHER', unit='gab.')
    db.session.add(other)
    db.session.commit()
    assert client.post(f'/admin/supplier-products/{offer.id}/edit', data=dict(data, product_id=str(other.id))).status_code == 422
    db.session.refresh(offer)
    assert offer.product_id == product.id
    for path in ['/admin/supplier-products/new', f'/admin/supplier-products/{offer.id}/edit']:
        for token in ['', 'wrong', 'ā']:
            assert client.post(path, data=dict(data, csrf_token=token)).status_code == 400
    assert client.get('/admin/supplier-products/999999/edit').status_code == 404


@pytest.mark.parametrize('path,method', [('/admin', 'get'), ('/admin/supplier-products', 'get'),
    ('/admin/supplier-products/new', 'get'), ('/admin/supplier-products/new', 'post'),
    ('/admin/supplier-products/1/edit', 'get'), ('/admin/supplier-products/1/edit', 'post')])
def test_panel_requires_admin(database_app, path, method):
    client = database_app.test_client()
    assert getattr(client, method)(path).status_code == 302
    client.post('/auth/register', data=admin_data())
    assert getattr(client, method)(path).status_code == 403


def test_admin_login_opens_panel_and_respects_next(database_app):
    client = database_app.test_client()
    login_admin(client)
    client.get('/auth/logout')
    response = client.post('/auth/login', data={'email': admin_data()['email'], 'password': admin_data()['password']})
    assert response.location.endswith('/admin/')
    client.get('/auth/logout')
    response = client.post('/auth/login?next=/admin/suppliers', data={'email': admin_data()['email'], 'password': admin_data()['password']})
    assert response.location.endswith('/admin/suppliers')
