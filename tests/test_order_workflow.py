from decimal import Decimal

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.extensions import db
from backend.app.models import CartItem, Notification, Order, User
from conftest import MIGRATIONS
from test_comparison import comparison_data, sign_in
from test_cart_checkout import add_profile, add_to_cart, review_data


def submit(comparison_data, **overrides):
    client, _, offers, buyer = comparison_data
    token = sign_in(client)
    add_profile(buyer)
    add_to_cart(client, token, offers[0], 2)
    data = dict(review_data(client, token), delivery_address='Rīga, Jaunā piegāde 7',
                phone='+371 20000000', note='Lūdzu piegādāt pēcpusdienā.')
    data.update(overrides)
    response = client.post('/orders/checkout', data=data)
    return response, data


def sign_in_admin(client, order_id):
    client.get('/auth/logout')
    client.post('/auth/login', data={'email': 'supplier@example.test', 'password': 'password123'})
    assert client.get(f'/admin/orders/{order_id}').status_code == 200
    with client.session_transaction() as session:
        return session['product_csrf_token']


@pytest.mark.parametrize('decision,status,kind', [('approve', 'apstiprināts', 'approved'), ('decline', 'noraidīts', 'declined')])
def test_submit_review_decide_and_notify_both_profiles(comparison_data, decision, status, kind):
    client, _, _, buyer = comparison_data
    response, data = submit(comparison_data)
    assert response.status_code == 302
    order = db.session.scalar(db.select(Order))
    assert order.total_amount == Decimal('14.00') and order.status == 'iesniegts'
    assert order.customer_snapshot['delivery_address'] == data['delivery_address']
    assert order.customer_snapshot['phone'] == data['phone']
    assert db.session.scalar(db.select(db.func.count(CartItem.id))) == 0
    notifications = db.session.scalars(db.select(Notification)).all()
    assert len(notifications) == 2 and all(not n.is_read for n in notifications)
    assert 'nodots administratoram' in client.get('/auth/profile').get_data(as_text=True)
    assert f'Pieteikums #{order.id}' in client.get('/orders').get_data(as_text=True)
    buyer.company_profile.delivery_address = 'Vēlāk mainīta adrese'
    buyer.full_name = 'Vēlāk mainīts vārds'
    db.session.commit()
    csrf = sign_in_admin(client, order.id)
    detail = client.get(f'/admin/orders/{order.id}').get_data(as_text=True)
    assert data['delivery_address'] in detail and 'Buyer' in detail
    assert 'Vēlāk mainīta adrese' not in detail and 'Vēlāk mainīts vārds' not in detail
    assert 'Saņemts jauns pieteikums' in client.get('/auth/profile').get_data(as_text=True)
    response = client.post(f'/admin/orders/{order.id}', data={'csrf_token': csrf, 'decision': decision, 'admin_note': 'Komentārs klientam.'})
    assert response.status_code == 302
    db.session.refresh(order)
    assert order.status == status and order.processed_at is not None
    assert order.processed_by_admin.role == 'admin' and order.admin_note == 'Komentārs klientam.'
    notices = db.session.scalars(db.select(Notification).where(Notification.kind == kind)).all()
    assert len(notices) == 2
    assert not any(n.is_read for n in notices)
    assert f'ir {status}' in client.get('/auth/profile').get_data(as_text=True)
    assert client.post(f'/admin/orders/{order.id}', data={'csrf_token': csrf, 'decision': 'decline'}).status_code == 409
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 4
    client.get('/auth/logout')
    sign_in(client)
    profile = client.get('/auth/profile').get_data(as_text=True)
    assert f'ir {status}' in profile
    detail = client.get(f'/orders/{order.id}').get_data(as_text=True)
    assert 'Komentārs klientam.' in detail and data['delivery_address'] in detail
    notification = db.session.scalar(db.select(Notification).where(Notification.user_id == buyer.id, Notification.kind == kind))
    with client.session_transaction() as session:
        token = session['cart_csrf_token']
    assert client.post(f'/auth/notifications/{notification.id}/read', data={'csrf_token': token}).status_code == 302
    db.session.refresh(notification)
    assert notification.is_read


@pytest.mark.parametrize('field,value', [('delivery_address', ''), ('delivery_address', 'a' * 256),
    ('delivery_address', 'Bad\x00address'), ('phone', 'letters'), ('phone', '123'), ('note', 'a' * 1001)])
def test_invalid_checkout_details_preserve_cart(comparison_data, field, value):
    response, _ = submit(comparison_data, **{field: value})
    assert response.status_code == 422 and 'aria-invalid="true"' in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 0
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 0
    assert db.session.scalar(db.select(CartItem)).quantity == 2


def test_admin_access_csrf_input_and_notification_ownership(comparison_data):
    client, _, _, buyer = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    assert client.get('/admin/orders').status_code == 403
    assert client.post(f'/admin/orders/{order.id}').status_code == 403
    admin_notice = db.session.scalar(db.select(Notification).where(Notification.user_id != buyer.id))
    with client.session_transaction() as session:
        token = session['cart_csrf_token']
    assert client.post(f'/auth/notifications/{admin_notice.id}/read', data={'csrf_token': token}).status_code == 404
    own_notice = db.session.scalar(db.select(Notification).where(Notification.user_id == buyer.id))
    assert client.post(f'/auth/notifications/{own_notice.id}/read', data={}).status_code == 400
    csrf = sign_in_admin(client, order.id)
    for invalid in ['', 'wrong', 'ā']:
        assert client.post(f'/admin/orders/{order.id}', data={'csrf_token': invalid, 'decision': 'approve'}).status_code == 400
    assert client.post(f'/admin/orders/{order.id}', data={'csrf_token': csrf, 'decision': 'bad'}).status_code == 400
    assert client.post(f'/admin/orders/{order.id}', data={'csrf_token': csrf, 'decision': 'approve', 'admin_note': 'a' * 1001}).status_code == 422
    db.session.refresh(order)
    assert order.status == 'iesniegts'
    assert client.get('/admin/orders/999999').status_code == 404
    client.get('/auth/logout')
    assert client.get('/admin/orders').status_code == 302
    assert client.get('/orders').status_code == 302


def test_multiple_admins_get_submission_and_decision_once(comparison_data):
    other = User(email='admin2@example.test', full_name='Otrais administrators', role='admin', password_hash='hash')
    inactive = User(email='inactive@example.test', full_name='Neaktīvs', role='admin', password_hash='hash', is_active=False)
    db.session.add_all([other, inactive])
    db.session.commit()
    client, _, _, _ = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 3
    token = sign_in_admin(client, order.id)
    client.post(f'/admin/orders/{order.id}', data={'csrf_token': token, 'decision': 'approve'})
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 6
    assert db.session.scalar(db.select(Notification.id).where(Notification.user_id == inactive.id)) is None
    assert f'Pieteikums #{order.id}' not in client.get('/admin/orders').get_data(as_text=True)
    assert f'Pieteikums #{order.id}' in client.get('/admin/orders?status=apstiprināts').get_data(as_text=True)


def test_decision_failure_rolls_back_status_and_notifications(comparison_data, monkeypatch):
    from backend.app.routes import admin_orders
    client, _, _, _ = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    token = sign_in_admin(client, order.id)
    actual_notify = admin_orders.notify_decision
    def failed_notify(item):
        actual_notify(item)
        raise SQLAlchemyError('Test transaction failure')
    monkeypatch.setattr(admin_orders, 'notify_decision', failed_notify)
    response = client.post(f'/admin/orders/{order.id}', data={'csrf_token': token, 'decision': 'approve'})
    assert response.status_code == 503
    db.session.refresh(order)
    assert order.status == 'iesniegts' and order.processed_at is None
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 2


def test_submission_notification_failure_keeps_cart_and_creates_nothing(comparison_data, monkeypatch):
    from backend.app.routes import orders
    actual_notify = orders.notify_submission
    def failed_notify(item):
        actual_notify(item)
        raise SQLAlchemyError('Test notification transaction failure')
    monkeypatch.setattr(orders, 'notify_submission', failed_notify)
    response, _ = submit(comparison_data)
    assert response.status_code == 503
    assert db.session.scalar(db.select(db.func.count(Order.id))) == 0
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 0
    assert db.session.scalar(db.select(CartItem)).quantity == 2


def test_notifications_migration_retains_orders_and_prices(comparison_data):
    submit(comparison_data)
    db.session.remove()
    downgrade(directory=MIGRATIONS, revision='0005_offer_terms')
    with db.engine.connect() as connection:
        assert connection.scalar(text('SELECT COUNT(*) FROM orders')) == 1
        assert connection.scalar(text('SELECT total_amount FROM orders')) == 14
    upgrade(directory=MIGRATIONS)
    db.session.remove()
    order = db.session.scalar(db.select(Order))
    assert order.customer_snapshot is None and order.status == 'iesniegts'
    assert order.items[0].unit_price == Decimal('2.00')
