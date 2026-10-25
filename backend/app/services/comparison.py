"""Compare EUR offers including their declared VAT rate and delivery fee."""

from decimal import Decimal, ROUND_HALF_UP
import re
import secrets

from flask import abort, request, session


MAX_QUANTITY = 2147483647
SORT_OPTIONS = {"total-asc", "total-desc", "delivery", "supplier"}


def parse_quantity(value):
    # Daudzumam atļaujam tikai pozitīvu veselu skaitli datubāzes lauka robežās.
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value):
        raise ValueError("Norādiet daudzumu kā pozitīvu veselu skaitli.")
    quantity = int(value)
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError(f"Daudzumam jābūt no 1 līdz {MAX_QUANTITY}.")
    return quantity


def comparison_rows(offers, quantity, sort):
    rows = []
    for offer in offers:
        errors = []
        if quantity < offer.min_order_qty:
            errors.append(f"Minimālais daudzums: {offer.min_order_qty}.")
        if quantity > offer.stock_qty:
            errors.append(f"Nepietiekams atlikums. Noliktavā: {offer.stock_qty}.")
        subtotal = offer.unit_price * quantity
        vat_amount, vat_error = Decimal("0.00"), None
        if not offer.vat_included:
            if offer.vat_rate is None:
                vat_amount = None
                vat_error = "Nav norādīta PVN likme; kopsummu ar PVN nevar aprēķināt."
            else:
                # PVN noapaļojam visai preču summai, lai nerastos atšķirības par katru vienību.
                vat_amount = (subtotal * offer.vat_rate / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal_with_vat = subtotal + vat_amount if vat_amount is not None else None
        total_with_vat = (subtotal_with_vat + offer.delivery_price
                          if subtotal_with_vat is not None else None)
        rows.append({"offer": offer, "subtotal": subtotal,
                     # Saglabājam arī piegādātāja summas, ko izmanto grozs un noformēšana.
                     "total": subtotal + offer.delivery_price,
                     "subtotal_with_vat": subtotal_with_vat, "vat_amount": vat_amount,
                     "total_with_vat": total_with_vat, "vat_error": vat_error,
                     "error": " ".join(errors) or None})

    def total_key(row):
        # Piedāvājumi bez aprēķināmas PVN kopsummas vienmēr paliek saraksta beigās.
        value = row["total_with_vat"]
        return (value is None, (value if value is not None else Decimal("0.00"))
                * (-1 if sort == "total-desc" else 1), row["offer"].id)

    if sort == "supplier":
        rows.sort(key=lambda row: (row["offer"].supplier_name.casefold(), row["offer"].id))
    elif sort == "delivery":
        rows.sort(key=lambda row: (row["offer"].delivery_days, *total_key(row)))
    else:
        rows.sort(key=total_key)
    return rows


def cart_csrf_token():
    # Nejaušo formas drošības kodu piesaistām lietotāja sesijai.
    if "cart_csrf_token" not in session:
        session["cart_csrf_token"] = secrets.token_hex(32)
    return session["cart_csrf_token"]


def require_cart_csrf():
    # Drošības kodus salīdzinām ar compare_digest, lai salīdzinājuma laiks neatklātu to saturu.
    expected = session.get("cart_csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
        abort(400, description="Nederīgs formas drošības kods. Atveriet lapu atkārtoti.")
