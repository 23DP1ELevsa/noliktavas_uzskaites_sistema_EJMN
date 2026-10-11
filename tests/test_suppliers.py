from decimal import Decimal

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Category, Offer, Order, OrderItem, Product, Supplier, User
from conftest import MIGRATIONS
from test_admin import admin_data, login_admin


@pytest.fixture
def supplier_inventory(database_app):
    client = database_app.test_client()
    login_admin(client)
    client.get('/admin/suppliers/new')
    with client.session_transaction() as session:
        token = session['product_csrf_token']
    data = {'name': 'Testa piegādātājs', 'contact_person': 'Anna Kalniņa',
            'email': 'anna@example.test', 'phone': '+371 20000000',
            'website': 'https://example.test', 'delivery_price': '2,50',
            'is_active': '1', 'csrf_token': token}
    return client, data


def create_supplier(inventory):
    client, data = inventory
    response = client.post('/admin/suppliers/new', data=data)
    assert response.status_code == 302
    return db.session.scalar(db.select(Supplier))


def linked_offer(supplier):
    admin = db.session.scalar(db.select(User).where(User.role == 'admin'))
    product = Product(name='Piegādātāja prece', sku='SUPPLIER-ITEM', category=Category(name='Piegādātāju preces'))
    offer = Offer(product=product, supplier=supplier, supplier_name=supplier.name,
                  created_by_admin=admin, unit_price=Decimal('10.00'), delivery_price=supplier.delivery_price,
                  stock_qty=20, vat_included=True)
    db.session.add(offer)
    db.session.commit()
    return offer, admin


def test_supplier_create_read_update_delete_and_filters(supplier_inventory):
    client, data = supplier_inventory
    supplier = create_supplier(supplier_inventory)
    identifier = supplier.id
    assert supplier.name_key == data['name'].casefold()
    assert supplier.delivery_price == Decimal('2.50')
    html = client.get(f'/admin/suppliers/{identifier}').get_data(as_text=True)
    for value in (data['name'], data['contact_person'], data['email'], data['phone'], data['website'], '2.50 €'):
        assert value in html
    assert data['name'] in client.get('/admin/suppliers?q=anna').get_data(as_text=True)
    assert data['name'] not in client.get('/admin/suppliers?status=inactive').get_data(as_text=True)
    assert client.get(f'/admin/suppliers/{identifier}/edit').status_code == 200
    changed = dict(data, name='Jauns piegādātājs', email='', phone='', website='', delivery_price='0')
    client.post(f'/admin/suppliers/{identifier}/edit', data=changed)
    db.session.refresh(supplier)
    assert supplier.name == changed['name'] and supplier.email is None
    assert supplier.delivery_price == Decimal('0.00')
    assert client.get(f'/admin/suppliers/{identifier}/delete').status_code == 200
    assert db.session.get(Supplier, identifier) is not None
    client.post(f'/admin/suppliers/{identifier}/delete', data={'csrf_token': data['csrf_token'], 'confirmed': '1'})
    assert db.session.get(Supplier, identifier) is None
    assert 'Vēl nav piegādātāju' in client.get('/admin/suppliers').get_data(as_text=True)


@pytest.mark.parametrize('field,value', [
    ('name', ''), ('name', ' '), ('name', 'a' * 256), ('contact_person', 'a' * 151),
    ('contact_person', 'Bad\x00name'), ('email', 'invalid'), ('email', 'a' * 256),
    ('phone', '123'), ('phone', '+371 letters'), ('phone', '9' * 51),
    ('website', 'javascript:alert(1)'), ('website', 'https://'),
    ('website', 'https://user:password@example.test'), ('website', 'https://example.test:bad'),
    ('website', 'https://example.test/space here'), ('website', 'https://example.test/' + 'a' * 2048),
    ('delivery_price', ''), ('delivery_price', '-1'), ('delivery_price', '1.234'),
    ('delivery_price', 'NaN'), ('delivery_price', '1e2'), ('delivery_price', '100000000'),
])
def test_invalid_supplier_data_is_reported_and_not_saved(supplier_inventory, field, value):
    client, data = supplier_inventory
    response = client.post('/admin/suppliers/new', data=dict(data, **{field: value}))
    assert response.status_code == 422
    html = response.get_data(as_text=True)
    assert 'aria-invalid="true"' in html and f'id="{field}-error"' in html
    assert data['contact_person'] in html or field == 'contact_person'
    assert db.session.scalar(db.select(db.func.count(Supplier.id))) == 0


def test_supplier_name_is_unique_ignoring_case_and_spacing(supplier_inventory):
    client, data = supplier_inventory
    supplier = create_supplier(supplier_inventory)
    assert client.post('/admin/suppliers/new', data=dict(data, name='  TESTA   PIEGĀDĀTĀJS ')).status_code == 422
    assert client.post(f'/admin/suppliers/{supplier.id}/edit', data=data).status_code == 302


def test_supplier_edit_updates_current_offers_but_preserves_order_snapshot(supplier_inventory):
    client, data = supplier_inventory
    supplier = create_supplier(supplier_inventory)
    offer, admin = linked_offer(supplier)
    order = Order(user=admin, company_profile=admin.company_profile, total_amount=Decimal('12.50'))
    db.session.add(order)
    item = OrderItem(order=order, supplier=supplier, offer=offer, product_name=offer.product.name,
                     supplier_name=supplier.name, unit_price=offer.unit_price, quantity=1,
                     delivery_price=offer.delivery_price, line_total=Decimal('12.50'), vat_included=True)
    db.session.add(item)
    db.session.commit()
    client.post(f'/admin/suppliers/{supplier.id}/edit', data=dict(data, name='Jauns nosaukums', delivery_price='4.75'))
    db.session.refresh(offer)
    db.session.refresh(item)
    assert offer.supplier_name == 'Jauns nosaukums' and offer.delivery_price == Decimal('4.75')
    assert item.supplier_name == data['name'] and item.delivery_price == Decimal('2.50')
    assert item.line_total == Decimal('12.50')


def test_inactive_supplier_is_not_orderable_and_reactivation_preserves_offer_status(supplier_inventory):
    client, data = supplier_inventory
    supplier = create_supplier(supplier_inventory)
    offer, admin = linked_offer(supplier)
    cart_item = CartItem(cart=Cart(user=admin), offer=offer, quantity=1)
    db.session.add(cart_item)
    db.session.commit()
    assert client.get('/catalog').json['items'][0]['offer_count'] == 1
    client.post(f'/admin/suppliers/{supplier.id}/status', data={'csrf_token': data['csrf_token'], 'is_active': '0'})
    db.session.refresh(supplier)
    assert not supplier.is_active and offer.is_active
    assert client.get('/catalog').json['items'][0]['offer_count'] == 0
    assert client.get('/catalog?in_stock=true').json['items'] == []
    assert supplier.name not in client.get(f'/catalog/products/{offer.product_id}').get_data(as_text=True)
    client.get('/cart')
    with client.session_transaction() as session:
        cart_token = session['cart_csrf_token']
    assert 'vairs nav aktīvs' in client.get('/cart').get_data(as_text=True)
    assert client.post('/cart/items', data={'csrf_token': cart_token, 'offer_id': offer.id, 'quantity': '1'}).status_code == 404
    assert client.get('/orders/checkout').headers['Location'].endswith('/cart')
    client.post(f'/admin/suppliers/{supplier.id}/status', data={'csrf_token': data['csrf_token'], 'is_active': '1'})
    assert client.get('/catalog').json['items'][0]['offer_count'] == 1
    offer.is_active = False
    db.session.commit()
    client.post(f'/admin/suppliers/{supplier.id}/status', data={'csrf_token': data['csrf_token'], 'is_active': '1'})
    assert not offer.is_active


def test_supplier_with_order_cannot_be_deleted_even_after_offer_is_removed(supplier_inventory):
    client, data = supplier_inventory
    supplier = create_supplier(supplier_inventory)
    offer, admin = linked_offer(supplier)
    identifier = supplier.id
    order = Order(user=admin, company_profile=admin.company_profile, total_amount=Decimal('12.50'))
    db.session.add(order)
    item = OrderItem(order=order, supplier=supplier, offer=offer, product_name=offer.product.name,
                     supplier_name=supplier.name, unit_price=10, quantity=1, delivery_price=Decimal('2.50'),
                     line_total=Decimal('12.50'), vat_included=True)
    db.session.add(item)
    db.session.commit()
    # Offers alone also prevent deletion.
    response = client.post(f'/admin/suppliers/{identifier}/delete', data={'csrf_token': data['csrf_token'], 'confirmed': '1'})
    assert response.status_code == 302 and db.session.get(Supplier, identifier) is not None
    db.session.delete(offer)
    db.session.commit()
    assert item.supplier_id == identifier
    html = client.get(f'/admin/suppliers/{identifier}/delete').get_data(as_text=True)
    assert 'nevar dzēst' in html
    client.post(f'/admin/suppliers/{identifier}/delete', data={'csrf_token': data['csrf_token'], 'confirmed': '1'})
    assert db.session.get(Supplier, identifier) is not None
    db.session.delete(supplier)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize('path,method', [('/admin/suppliers', 'get'), ('/admin/suppliers/new', 'get'),
    ('/admin/suppliers/new', 'post'), ('/admin/suppliers/1', 'get'), ('/admin/suppliers/1/edit', 'post'),
    ('/admin/suppliers/1/status', 'post'), ('/admin/suppliers/1/delete', 'get'), ('/admin/suppliers/1/delete', 'post')])
def test_supplier_management_requires_admin(database_app, path, method):
    client = database_app.test_client()
    assert getattr(client, method)(path).status_code == 302
    client.post('/auth/register', data=admin_data())
    assert getattr(client, method)(path).status_code == 403


def test_supplier_mutations_require_csrf_and_delete_confirmation(supplier_inventory):
    client, data = supplier_inventory
    supplier = create_supplier(supplier_inventory)
    for path in ('/admin/suppliers/new', f'/admin/suppliers/{supplier.id}/edit',
                 f'/admin/suppliers/{supplier.id}/status', f'/admin/suppliers/{supplier.id}/delete'):
        for invalid in ('', 'wrong', 'ā'):
            assert client.post(path, data=dict(data, csrf_token=invalid)).status_code == 400
    assert client.post(f'/admin/suppliers/{supplier.id}/delete', data={'csrf_token': data['csrf_token']}).status_code == 400
    assert client.post(f'/admin/suppliers/{supplier.id}/status', data={'csrf_token': data['csrf_token'], 'is_active': 'bad'}).status_code == 400
    for suffix in ('', '/edit', '/delete'):
        assert client.get('/admin/suppliers/999999' + suffix).status_code == 404


def test_supplier_migration_preserves_cart_order_snapshots_and_varied_delivery_prices(database_app):
    db.session.remove()
    downgrade(directory=MIGRATIONS, revision='0003_company_delivery')
    with db.engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id,email,password_hash,full_name,role) VALUES (1,'existing@test.example','hash','Admin','admin')"))
        connection.execute(text("INSERT INTO company_profiles (id,user_id,company_name,registration_no,address) VALUES (1,1,'Company','123','Riga')"))
        connection.execute(text("INSERT INTO categories (id,name) VALUES (1,'Category')"))
        connection.execute(text("INSERT INTO products (id,category_id,sku,name) VALUES (1,1,'SKU','Product')"))
        for identifier, name, price in ((1, 'SIA Piegādātājs', '2.50'), (2, 'sia piegādātājs', '4.00')):
            connection.execute(text("INSERT INTO offers (id,product_id,created_by_admin_id,supplier_name,unit_price,vat_included,stock_qty,delivery_price) VALUES (:id,1,1,:name,10,1,20,:price)"), {'id': identifier, 'name': name, 'price': price})
        connection.execute(text("INSERT INTO carts (id,user_id) VALUES (1,1)"))
        connection.execute(text("INSERT INTO cart_items (cart_id,offer_id,quantity) VALUES (1,1,2)"))
        connection.execute(text("INSERT INTO orders (id,user_id,company_profile_id,total_amount) VALUES (1,1,1,22.50)"))
        connection.execute(text("INSERT INTO order_items (order_id,offer_id,product_name,supplier_name,unit_price,quantity,delivery_price,line_total,vat_included) VALUES (1,1,'Product','Old name',10,2,2.50,22.50,1)"))
        connection.execute(text("INSERT INTO order_items (order_id,product_name,supplier_name,unit_price,quantity,delivery_price,line_total,vat_included) VALUES (1,'Deleted product','Vēsturisks',1,1,0,1,1)"))
    upgrade(directory=MIGRATIONS)
    db.session.remove()
    offers = db.session.scalars(db.select(Offer).order_by(Offer.id)).all()
    assert offers[0].supplier_id == offers[1].supplier_id
    assert offers[0].delivery_price == Decimal('2.50') and offers[1].delivery_price == Decimal('4.00')
    assert db.session.scalar(db.select(CartItem)).quantity == 2
    items = db.session.scalars(db.select(OrderItem).order_by(OrderItem.id)).all()
    assert items[0].supplier_id == offers[0].supplier_id
    assert items[0].supplier_name == 'Old name' and items[0].line_total == Decimal('22.50')
    assert items[1].supplier.name == 'Vēsturisks' and not items[1].supplier.is_active
