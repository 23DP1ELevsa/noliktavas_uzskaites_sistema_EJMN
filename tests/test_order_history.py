from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from backend.app.extensions import db
from backend.app.models import Order, User
from test_comparison import comparison_data, sign_in
from test_order_workflow import submit


def test_history_filters_sorts_paginates_and_isolates_current_user(comparison_data):
    client, _, _, buyer = comparison_data
    submit(comparison_data)
    first = db.session.scalar(db.select(Order))
    profile = buyer.company_profile
    first.created_at = datetime(2026, 1, 1)
    other = User(email='private@example.test', full_name='Cits klients', password_hash='hash')
    db.session.add(other)
    db.session.flush()
    # The profile FK here is intentionally shared to verify filtering uses owner ID.
    private = Order(user_id=other.id, company_profile_id=profile.id, status='apstiprināts',
                    total_amount=Decimal('123.45'), created_at=datetime(2027, 1, 1))
    db.session.add(private)
    own = []
    for i in range(13):
        item = Order(user_id=buyer.id, company_profile_id=profile.id, total_amount=Decimal('10.00'),
                     status='apstiprināts' if i % 2 else 'noraidīts',
                     created_at=datetime(2026, 2, 1) + timedelta(days=i))
        db.session.add(item)
        own.append(item)
    db.session.commit()
    newest = own[-1]
    html = client.get('/orders').get_data(as_text=True)
    assert f'Pieteikums #{newest.id}</a>' in html and f'Pieteikums #{first.id}</a>' not in html
    assert f'Pieteikums #{private.id}</a>' not in html and '14 pieteikumi' in html
    assert html.index(f'Pieteikums #{own[-1].id}</a>') < html.index(f'Pieteikums #{own[-2].id}</a>')
    html = client.get('/orders?page=2').get_data(as_text=True)
    assert f'Pieteikums #{first.id}</a>' in html and f'Pieteikums #{newest.id}</a>' not in html
    html = client.get('/orders?sort=date-asc').get_data(as_text=True)
    assert html.index(f'Pieteikums #{first.id}</a>') < html.index(f'Pieteikums #{own[0].id}</a>')
    html = client.get(f'/orders?status=iesniegts&user_id={other.id}').get_data(as_text=True)
    assert f'Pieteikums #{first.id}</a>' in html and f'Pieteikums #{newest.id}</a>' not in html
    html = client.get('/orders?status=apstiprināts').get_data(as_text=True)
    assert f'Pieteikums #{own[1].id}</a>' in html and f'Pieteikums #{private.id}</a>' not in html
    assert f'Pieteikums #{own[0].id}</a>' not in html
    assert client.get(f'/orders/{private.id}').status_code == 404


def test_history_detail_uses_saved_prices_comment_and_decision_date(comparison_data):
    client, product, offers, _ = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    order.status = 'noraidīts'
    order.admin_note = 'Piegādes nosacījumi jāsaskaņo.'
    order.processed_at = datetime(2026, 10, 12, 9, 30)
    offers[0].unit_price = Decimal('999.00')
    product.name = 'Jauns preces nosaukums'
    db.session.commit()
    html = client.get(f'/orders/{order.id}').get_data(as_text=True)
    for text in ['Lēta vienība', 'Salīdzināma prece', '2.00 €', 'Piegādes nosacījumi jāsaskaņo.',
                 'Lēmums pieņemts:', '2026-10-12T09:30:00Z', 'href="/orders"']:
        assert text in html
    assert '999.00' not in html and 'Jauns preces nosaukums' not in html


@pytest.mark.parametrize('query', ['status=bad', 'sort=bad', 'page=0', 'page=-1', 'page=NaN', 'page=999999999999'])
def test_invalid_history_filters_are_rejected(comparison_data, query):
    client, _, _, _ = comparison_data
    sign_in(client)
    assert client.get('/orders?' + query).status_code == 400


def test_filtered_empty_history_shows_clear_selection_action(comparison_data):
    client, _, _, _ = comparison_data
    submit(comparison_data)
    html = client.get('/orders?status=apstiprināts').get_data(as_text=True)
    assert 'Šajā statusā pieteikumu nav.' in html and 'Rādīt visus pieteikumus' in html
    assert 'Jums vēl nav pieteikumu.' not in html
