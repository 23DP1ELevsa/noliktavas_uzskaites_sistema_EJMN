from decimal import Decimal
import re
from urllib.parse import urlsplit

from ..extensions import db
from ..models import Supplier


FIELDS = ("name", "contact_person", "email", "phone", "website", "delivery_price")


def supplier_form_data(form=None, supplier=None):
    if form is not None:
        data = {field: form.get(field, "").strip() for field in FIELDS}
        data["name"] = " ".join(data["name"].split())
        data["is_active"] = form.get("is_active") == "1"
    else:
        data = {field: str(getattr(supplier, field) or "") if supplier else "" for field in FIELDS}
        data["delivery_price"] = format(supplier.delivery_price, ".2f") if supplier else "0.00"
        data["is_active"] = supplier.is_active if supplier else True
    return data


def validate_supplier(data, supplier=None):
    errors = {}
    for field, label, limit in (("name", "Nosaukums", 255), ("contact_person", "Kontaktpersona", 150),
                                ("email", "E-pasts", 255), ("phone", "Tālrunis", 50), ("website", "Tīmekļa vietne", 2048)):
        if field == "name" and not data[field]:
            errors[field] = "Nosaukums ir obligāts lauks."
        elif len(data[field]) > limit:
            errors[field] = f"{label} nedrīkst pārsniegt {limit} rakstzīmes."
        elif any(ord(char) < 32 or ord(char) == 127 for char in data[field]):
            errors[field] = f"{label} nedrīkst saturēt vadības rakstzīmes."
    if data["name"] and "name" not in errors:
        query = db.select(Supplier.id).where(Supplier.name_key == data["name"].casefold())
        if supplier:
            query = query.where(Supplier.id != supplier.id)
        if db.session.scalar(query) is not None:
            errors["name"] = "Piegādātājs ar šādu nosaukumu jau pastāv."
    if data["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", data["email"]):
        errors["email"] = "Ievadiet derīgu e-pasta adresi."
    if data["phone"] and (not re.fullmatch(r"\+?[0-9() .-]+", data["phone"])
                           or not 7 <= len(re.sub(r"\D", "", data["phone"])) <= 15):
        errors["phone"] = "Ievadiet tālruni ar 7–15 cipariem, piemēram, +371 20000000."
    if data["website"]:
        try:
            parsed = urlsplit(data["website"])
            valid = parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password
            valid = valid and not any(char.isspace() or ord(char) < 32 for char in data["website"])
            parsed.port
        except ValueError:
            valid = False
        if not valid:
            errors["website"] = "Norādiet pilnu saiti, kas sākas ar https:// vai http://."
    price = data["delivery_price"].replace(",", ".")
    if not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,2})?", price):
        errors["delivery_price"] = "Norādiet maksu no 0 līdz 99999999.99 € ar ne vairāk kā divām zīmēm aiz komata."
    return errors


def supplier_values(data):
    return {"name": data["name"], "name_key": data["name"].casefold(),
            "contact_person": data["contact_person"] or None, "email": data["email"] or None,
            "phone": data["phone"] or None, "website": data["website"] or None,
            "delivery_price": Decimal(data["delivery_price"].replace(",", ".")), "is_active": data["is_active"]}
