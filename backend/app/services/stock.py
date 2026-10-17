"""Stock changes belong to the same transaction as the order/decision."""

from collections import Counter

from ..extensions import db
from ..models import Offer


def allocate(offer, quantity):
    """Caller holds the offer lock and has checked the requested quantity."""
    offer.stock_qty -= quantity
    offer.allocated_qty += quantity


def release_order_stock(order):
    """Caller holds the order lock; a declined legacy order has nothing to return."""
    if not order.stock_deducted:
        return
    quantities = Counter()
    for item in order.items:
        if item.offer_id is not None:
            quantities[item.offer_id] += item.quantity
    offers = db.session.scalars(db.select(Offer).where(Offer.id.in_(quantities))
                               .order_by(Offer.id).with_for_update()
                               .execution_options(populate_existing=True)).all()
    for offer in offers:
        quantity = quantities[offer.id]
        offer.allocated_qty -= quantity
        if offer.imported_stock_qty is None:
            offer.stock_qty += quantity
        else:
            offer.stock_qty = max(0, offer.imported_stock_qty - offer.allocated_qty)
    order.stock_deducted = False
