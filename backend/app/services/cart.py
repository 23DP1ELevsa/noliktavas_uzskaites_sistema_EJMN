"""Current cart contents and Decimal totals shared by cart and checkout."""

from decimal import Decimal
import hashlib
import json

from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Cart, CartItem, Offer, Product
from .comparison import comparison_rows


MAX_ORDER_TOTAL = Decimal("9999999999.99")


def load_cart_summary(user_id, *, lock=False):
    cart_query = db.select(Cart).where(Cart.user_id == user_id)
    if lock:
        cart_query = cart_query.with_for_update().execution_options(populate_existing=True)
    cart = db.session.scalar(cart_query)
    items = []
    if cart:
        query = db.select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        else:
            query = query.options(joinedload(CartItem.offer).joinedload(Offer.product))
        items = db.session.scalars(query).all()
    if lock and items:
        # Refresh under locks before checking availability and allocating stock.
        offers = db.session.scalars(db.select(Offer).where(Offer.id.in_([item.offer_id for item in items]))
                                    .order_by(Offer.id).with_for_update()
                                    .execution_options(populate_existing=True)).all()
        db.session.scalars(db.select(Product).where(Product.id.in_([offer.product_id for offer in offers]))
                           .order_by(Product.id).with_for_update()
                           .execution_options(populate_existing=True)).all()
    rows, suppliers = [], {}
    for item in items:
        row = comparison_rows([item.offer], item.quantity, "total-asc")[0]
        row["item"] = item
        if not item.offer.is_active or not item.offer.product.is_active or not item.offer.supplier_active:
            row["error"] = "Piedāvājums vairs nav aktīvs."
        rows.append(row)
        name = item.offer.supplier_name
        group = suppliers.setdefault(name, {"supplier": name, "rows": [],
                                           "subtotal": Decimal("0.00"), "delivery": Decimal("0.00")})
        group["rows"].append(row)
        group["subtotal"] += row["subtotal"]
        group["delivery"] += item.offer.delivery_price
    groups = sorted(suppliers.values(), key=lambda group: group["supplier"].casefold())
    for group in groups:
        group["total"] = group["subtotal"] + group["delivery"]
    subtotal = sum((row["subtotal"] for row in rows), Decimal("0.00"))
    delivery = sum((row["offer"].delivery_price for row in rows), Decimal("0.00"))
    statuses = {row["offer"].vat_included for row in rows}
    vat_note = ("Cenas ar PVN." if statuses == {True} else "Cenas bez PVN; PVN nav pieskaitīts."
                if statuses == {False} else "Daļa cenu ir bez PVN; šīm cenām PVN nav pieskaitīts.")
    error = "Kopsumma pārsniedz vienam pieteikumam atļauto summu. Samaziniet grozu." if subtotal + delivery > MAX_ORDER_TOTAL else None
    return {"cart": cart, "rows": rows, "groups": groups, "subtotal": subtotal,
            "delivery_total": delivery, "total": subtotal + delivery, "vat_note": vat_note,
            "checkout_error": error,
            "can_checkout": bool(rows) and not error and not any(row["error"] for row in rows)}


def checkout_fingerprint(summary, profile):
    values = [(row["item"].id, row["offer"].id, row["item"].quantity,
               str(row["offer"].unit_price), str(row["offer"].delivery_price),
               row["offer"].vat_included, row["offer"].supplier_name, row["offer"].product.name,
               row["offer"].delivery_days, str(row["offer"].vat_rate), row["offer"].currency) for row in summary["rows"]]
    company = [profile.id, profile.company_name, profile.registration_no, profile.vat_no,
               profile.address, profile.effective_delivery_address, profile.phone,
               profile.user.full_name, profile.user.email] if profile else None
    return hashlib.sha256(json.dumps([values, company], ensure_ascii=False).encode()).hexdigest()
