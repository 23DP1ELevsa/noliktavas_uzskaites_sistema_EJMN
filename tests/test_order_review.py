from decimal import Decimal

import pytest

from backend.app.extensions import db
from backend.app.models import Notification, Order, OrderItem, Supplier
from test_comparison import comparison_data
from test_order_workflow import submit, sign_in_admin


@pytest.mark.parametrize('change', ['stock', 'minimum', 'price', 'delivery', 'vat', 'vat_rate',
                                    'offer_inactive', 'product_inactive', 'supplier_inactive', 'missing', 'empty'])
def test_approval_rechecks_current_offers_and_preserves_submitted_order(comparison_data, change):
    client, product, offers, _ = comparison_data
    if change == 'supplier_inactive':
        offers[0].supplier = Supplier(name='Lēta vienība', name_key='lēta vienība')
        db.session.commit()
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    csrf = sign_in_admin(client, order.id)
    offer = offers[0]
    if change == 'stock':
        offer.imported_stock_qty = 1
        offer.stock_qty = 0
    elif change == 'minimum':
        offer.min_order_qty = 3
    elif change == 'price':
        offer.unit_price = Decimal('9.00')
    elif change == 'delivery':
        offer.delivery_price = Decimal('11.00')
    elif change == 'vat':
        offer.vat_included = False
    elif change == 'vat_rate':
        offer.vat_rate = Decimal('21.00')
    elif change == 'offer_inactive':
        offer.is_active = False
    elif change == 'product_inactive':
        product.is_active = False
    elif change == 'supplier_inactive':
        offer.supplier.is_active = False
    elif change == 'missing':
        order.items[0].offer = None
    else:
        order.items.clear()
    db.session.commit()
    # Data changed after the administrator opened the form.
    response = client.post(f'/admin/orders/{order.id}', data={
        'csrf_token': csrf, 'decision': 'approve', 'admin_note': 'Saglabājams komentārs',
    })
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert 'Apstiprināšana nav pieejama' in html and 'Saglabājams komentārs' in html
    db.session.refresh(order)
    assert order.status == 'iesniegts' and order.total_amount == Decimal('14.00')
    assert order.processed_at is None and order.processed_by_admin_id is None and order.admin_note is None
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 2
    if order.items:
        assert order.items[0].unit_price == Decimal('2.00')
    # Unavailable offers must not prevent rejection with an explanation.
    response = client.post(f'/admin/orders/{order.id}', data={
        'csrf_token': csrf, 'decision': 'decline', 'admin_note': 'Piedāvājums vairs neatbilst pieteikumam.',
    })
    assert response.status_code == 302
    db.session.refresh(order)
    assert order.status == 'noraidīts' and order.processed_by_admin.full_name == 'Admin'
    assert order.processed_at is not None
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 4


def test_approval_checks_total_quantity_for_duplicate_offer_lines(comparison_data):
    client, _, offers, _ = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    source = order.items[0]
    duplicate = OrderItem(order=order, offer=offers[0], supplier_id=source.supplier_id,
                          product_name=source.product_name, supplier_name=source.supplier_name,
                          unit_price=source.unit_price, quantity=source.quantity,
                          delivery_price=source.delivery_price, line_total=source.line_total,
                          vat_included=source.vat_included, vat_rate=source.vat_rate, currency=source.currency)
    db.session.add(duplicate)
    offers[0].stock_qty = 3
    # Exercise historical, unallocated order lines, including duplicate offers.
    offers[0].allocated_qty = 0
    order.stock_deducted = False
    order.total_amount = Decimal('28.00')
    db.session.commit()
    csrf = sign_in_admin(client, order.id)
    response = client.post(f'/admin/orders/{order.id}', data={'csrf_token': csrf, 'decision': 'approve'})
    assert response.status_code == 409
    assert 'pieprasītais daudzums ir 4, atlikums — 3' in response.get_data(as_text=True)


@pytest.mark.parametrize('decision', ['approve', 'decline'])
def test_processed_order_cannot_be_decided_again(comparison_data, decision):
    client, _, _, _ = comparison_data
    submit(comparison_data)
    order = db.session.scalar(db.select(Order))
    csrf = sign_in_admin(client, order.id)
    assert client.post(f'/admin/orders/{order.id}', data={
        'csrf_token': csrf, 'decision': decision, 'admin_note': 'Sākotnējais lēmums.',
    }).status_code == 302
    db.session.refresh(order)
    original = (order.status, order.admin_note, order.processed_at, order.processed_by_admin_id)
    for next_decision in ['approve', 'decline']:
        assert client.post(f'/admin/orders/{order.id}', data={
            'csrf_token': csrf, 'decision': next_decision, 'admin_note': 'Cits lēmums.',
        }).status_code == 409
        db.session.refresh(order)
        assert (order.status, order.admin_note, order.processed_at, order.processed_by_admin_id) == original
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 4
