from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from backend.app.extensions import db
from backend.app.models import Order, User
from test_comparison import comparison_data
from test_order_workflow import submit, sign_in_admin


def test_admin_list_filters_sorts_and_paginates_all_clients(comparison_data):
    client, _, _, buyer = comparison_data
    submit(comparison_data)
    first = db.session.scalar(db.select(Order))
    first.created_at = datetime(2026, 1, 1)
    other = User(email='another@example.test', full_name='Cits klients', password_hash='hash')
    db.session.add(other)
    db.session.flush()
    orders = []
    for i in range(13):
        order = Order(user_id=other.id if i % 2 else buyer.id,
                      company_profile_id=buyer.company_profile.id,
                      status='apstiprināts' if i % 2 else 'iesniegts',
                      total_amount=Decimal('20.00'), created_at=datetime(2026, 2, 1) + timedelta(days=i))
        db.session.add(order)
        orders.append(order)
    db.session.commit()
    sign_in_admin(client, first.id)
    html = client.get('/admin/orders').get_data(as_text=True)
    assert '8 pieteikumi atlasē' in html and '8</strong> gaida izskatīšanu' in html
    assert f'Pieteikums #{orders[0].id}</a>' in html
    assert f'Pieteikums #{orders[1].id}</a>' not in html
    html = client.get('/admin/orders?status=all').get_data(as_text=True)
    assert '14 pieteikumi atlasē' in html and '1. lapa no 2' in html
    assert f'Pieteikums #{first.id}</a>' not in html
    assert html.index(f'Pieteikums #{orders[-1].id}</a>') < html.index(f'Pieteikums #{orders[-2].id}</a>')
    html = client.get('/admin/orders?status=all&page=2').get_data(as_text=True)
    assert f'Pieteikums #{first.id}</a>' in html
    assert f'Pieteikums #{orders[-1].id}</a>' not in html
    html = client.get('/admin/orders?status=apstiprināts&sort=date-asc').get_data(as_text=True)
    assert '6 pieteikumi atlasē' in html and 'Cits klients' in html
    assert html.index(f'Pieteikums #{orders[1].id}</a>') < html.index(f'Pieteikums #{orders[3].id}</a>')
    assert f'Pieteikums #{first.id}</a>' not in html
    html = client.get('/admin/orders?status=all&sort=date-asc').get_data(as_text=True)
    assert 'status=all&amp;sort=date-asc&amp;page=2' in html


def test_admin_view_uses_submitted_company_contacts_address_and_prices(comparison_data):
    client, product, offers, buyer = comparison_data
    _, submitted = submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    company_name = order.customer_snapshot['company_name']
    buyer.company_profile.company_name = 'Vēlāk mainīts uzņēmums'
    buyer.company_profile.phone = '+37129999999'
    offers[0].unit_price = Decimal('999.00')
    product.name = 'Vēlāk mainīta prece'
    db.session.commit()
    sign_in_admin(client, order.id)
    html = client.get('/admin/orders').get_data(as_text=True)
    assert company_name in html and '14.00 €' in html
    assert f'href="/admin/orders/{order.id}"' in html
    html = client.get(f'/admin/orders/{order.id}').get_data(as_text=True)
    for value in [company_name, submitted['phone'], submitted['delivery_address'],
                  'buyer@example.test', 'Lēta vienība', 'Salīdzināma prece', 'Piegāde', '10.00 €']:
        assert value in html
    assert '999.00' not in html and 'Vēlāk mainīts uzņēmums' not in html


@pytest.mark.parametrize('query', ['status=bad', 'sort=bad', 'page=0', 'page=-1', 'page=NaN', 'page=999999999999'])
def test_admin_list_rejects_invalid_filters(comparison_data, query):
    client, _, _, _ = comparison_data
    submit(comparison_data)
    sign_in_admin(client, db.session.scalar(db.select(Order.id)))
    assert client.get('/admin/orders?' + query).status_code == 400


def test_admin_list_and_detail_require_admin_role(comparison_data):
    client, _, _, _ = comparison_data
    submit(comparison_data)
    order_id = db.session.scalar(db.select(Order.id))
    for path in ['/admin/orders', '/admin/orders?status=all&page=2', f'/admin/orders/{order_id}']:
        assert client.get(path).status_code == 403
    client.get('/auth/logout')
    assert client.get('/admin/orders').status_code == 302
    assert client.get(f'/admin/orders/{order_id}').status_code == 302


def test_admin_empty_status_offers_all_orders(comparison_data):
    client, _, _, _ = comparison_data
    submit(comparison_data)
    sign_in_admin(client, db.session.scalar(db.select(Order.id)))
    html = client.get('/admin/orders?status=noraidīts').get_data(as_text=True)
    assert 'Šajā statusā pieteikumu nav.' in html and 'Rādīt visus pieteikumus' in html
    assert 'href="/admin/orders?status=all"' in html
