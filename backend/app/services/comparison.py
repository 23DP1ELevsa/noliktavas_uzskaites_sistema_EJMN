"""Offer comparison uses declared prices; VAT rates are not stored in the catalog."""

import re
import secrets

from flask import abort, request, session


MAX_QUANTITY = 2147483647
SORT_OPTIONS = {"total-asc", "total-desc", "delivery", "supplier"}


def parse_quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value):
        raise ValueError("Norādiet daudzumu kā pozitīvu veselu skaitli.")
    quantity = int(value)
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError(f"Daudzumam jābūt no 1 līdz {MAX_QUANTITY}.")
    return quantity


def comparison_rows(offers, quantity, sort):
    rows = []
    for offer in offers:
        error = None
        if quantity < offer.min_order_qty:
            error = f"Minimālais daudzums: {offer.min_order_qty}."
        elif quantity > offer.stock_qty:
            error = f"Nepietiekams atlikums. Noliktavā: {offer.stock_qty}."
        rows.append({"offer": offer, "subtotal": offer.unit_price * quantity,
                     "total": offer.unit_price * quantity + offer.delivery_price,
                     "error": error})
    if sort == "supplier":
        rows.sort(key=lambda row: (row["offer"].supplier_name.casefold(), row["offer"].id))
    elif sort == "delivery":
        rows.sort(key=lambda row: (row["offer"].delivery_days, row["total"], row["offer"].id))
    else:
        rows.sort(key=lambda row: (row["total"] * (-1 if sort == "total-desc" else 1),
                                  row["offer"].id))
    return rows


def cart_csrf_token():
    if "cart_csrf_token" not in session:
        session["cart_csrf_token"] = secrets.token_hex(32)
    return session["cart_csrf_token"]


def require_cart_csrf():
    expected = session.get("cart_csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
        abort(400, description="Nederīgs formas drošības kods. Atveriet lapu atkārtoti.")
