"""Check current offers, accounting for stock already allocated to this order."""

from collections import Counter

from ..extensions import db
from ..models import Offer, OrderItem, Product, Supplier


def approval_issues(order, *, lock=False):
    items = db.session.scalars(db.select(OrderItem).where(OrderItem.order_id == order.id)
                               .order_by(OrderItem.id)).all()
    if not items:
        return ["Pieteikumā nav preču."]

    def current_rows(model, ids):
        query = db.select(model).where(model.id.in_(ids)).order_by(model.id)
        if lock:
            query = query.with_for_update()
        return db.session.scalars(query.execution_options(populate_existing=True)).all()

    offers = current_rows(Offer, {item.offer_id for item in items if item.offer_id is not None})
    products = {row.id: row for row in current_rows(Product, {offer.product_id for offer in offers})}
    suppliers = {row.id: row for row in current_rows(Supplier, {offer.supplier_id for offer in offers if offer.supplier_id is not None})}
    offers = {offer.id: offer for offer in offers}
    quantities = Counter()
    for item in items:
        quantities[item.offer_id] += item.quantity
    issues = []
    for item in items:
        offer = offers.get(item.offer_id)
        prefix = f"{item.product_name} ({item.supplier_name}): "
        if offer is None:
            issues.append(prefix + "piedāvājums vairs nav pieejams.")
            continue
        product, supplier = products.get(offer.product_id), suppliers.get(offer.supplier_id)
        if (not offer.is_active or product is None or not product.is_active
                or (offer.supplier_id is not None and (supplier is None or not supplier.is_active))):
            issues.append(prefix + "piedāvājums, prece vai piegādātājs vairs nav aktīvs.")
        quantity = quantities[item.offer_id]
        if not order.stock_deducted and quantity > offer.stock_qty:
            issues.append(prefix + f"pieprasītais daudzums ir {quantity}, atlikums — {offer.stock_qty}.")
        if (order.stock_deducted and offer.imported_stock_qty is not None
                and offer.allocated_qty > offer.imported_stock_qty):
            issues.append(prefix + "piegādātāja atlikums vairs nesedz rezervētos pasūtījumus.")
        if quantity < offer.min_order_qty:
            issues.append(prefix + f"minimālais pasūtījuma daudzums tagad ir {offer.min_order_qty}.")
        if (item.unit_price != offer.unit_price or item.delivery_price != offer.delivery_price
                or item.vat_included != offer.vat_included or item.vat_rate != offer.vat_rate
                or item.currency != offer.currency or item.supplier_id != offer.supplier_id):
            issues.append(prefix + "cena, PVN, piegādes maksa vai piegādātājs ir mainījies kopš iesniegšanas.")
    return issues
