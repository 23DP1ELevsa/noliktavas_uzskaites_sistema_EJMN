from decimal import Decimal
import re

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Category, Offer, Product, Supplier
from .admin import admin_bp, admin_required, _check_product_csrf, _product_csrf_token


@admin_bp.get("")
@admin_bp.get("/")
@admin_required
def dashboard():
    sections = [
        ("Piegādātāji", "Kontaktinformācija, piegādes maksa un piegādātāja preces.", Supplier, "suppliers", "supplier_form", "Pievienot piegādātāju"),
        ("Preces", "Preču nosaukumi, attēli, apraksti un kategorijas.", Product, "products", "product_form", "Pievienot preci"),
        ("Piegādātāju preces", "Cenas, PVN, atlikumi un pasūtīšanas nosacījumi.", Offer, "supplier_products", "offer_form", "Piesaistīt preci"),
        ("Kategorijas", "Preču kataloga iedalījums.", Category, "categories", "create_category", "Pievienot kategoriju"),
    ]
    cards = [dict(title=title, description=description,
                  count=db.session.scalar(db.select(db.func.count(model.id))),
                  list_url=url_for("admin." + listing), add_url=url_for("admin." + adding), action=action)
             for title, description, model, listing, adding, action in sections]
    return render_template("admin/dashboard.html", cards=cards)


@admin_bp.get("/supplier-products")
@admin_required
def supplier_products():
    q = request.args.get("q", "").strip()[:255]
    query = db.select(Offer).join(Product).options(joinedload(Offer.product), joinedload(Offer.supplier))
    if q:
        query = query.where(db.or_(Product.name.icontains(q, autoescape=True),
                                  Offer.supplier_name.icontains(q, autoescape=True),
                                  Product.sku.icontains(q, autoescape=True)))
    items = db.session.scalars(query.order_by(Offer.supplier_name, Product.name, Offer.id)).all()
    return render_template("admin/supplier_products.html", offers=items, q=q)


def _selected_id(value, model):
    value = str(value)
    if value.isascii() and value.isdigit() and len(value) <= 19 and 0 < int(value) <= 9223372036854775807:
        return db.session.get(model, int(value))
    return None


@admin_bp.route("/supplier-products/new", methods=["GET", "POST"])
@admin_bp.route("/supplier-products/<int:offer_id>/edit", methods=["GET", "POST"])
@admin_required
def offer_form(offer_id=None):
    offer = db.get_or_404(Offer, offer_id) if offer_id is not None else None
    fields = ("supplier_id", "product_id", "supplier_sku", "unit_price", "vat_included", "stock_qty", "min_order_qty", "delivery_days")
    errors = {}
    if request.method == "POST":
        _check_product_csrf()
        data = {field: request.form.get(field, "").strip() for field in fields}
        data["is_active"] = request.form.get("is_active") == "1"
    else:
        data = {field: str(getattr(offer, field) if getattr(offer, field) is not None else "") if offer else "" for field in fields}
        data["vat_included"] = ("1" if offer.vat_included else "0") if offer else ""
        data["is_active"] = offer.is_active if offer else True
        if not offer:
            data.update(supplier_id=request.args.get("supplier_id", ""), product_id=request.args.get("product_id", ""),
                        stock_qty="0", min_order_qty="1", delivery_days="0")
    supplier = _selected_id(data["supplier_id"], Supplier)
    product = _selected_id(data["product_id"], Product)
    if request.method == "POST":
        if supplier is None:
            errors["supplier_id"] = "Izvēlieties esošu piegādātāju."
        if product is None:
            errors["product_id"] = "Izvēlieties esošu preci."
        if len(data["supplier_sku"]) > 100:
            errors["supplier_sku"] = "Kods nedrīkst pārsniegt 100 rakstzīmes."
        price_text = data["unit_price"].replace(",", ".")
        if not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,2})?", price_text):
            errors["unit_price"] = "Norādiet cenu no 0 līdz 99 999 999,99 €, ar ne vairāk kā divām zīmēm aiz komata."
        if offer:
            if product and product.id != offer.product_id:
                errors["product_id"] = "Esošam ierakstam nevar mainīt preci. Izveidojiet jaunu ierakstu."
            if supplier and offer.supplier_id is not None and supplier.id != offer.supplier_id:
                errors["supplier_id"] = "Esošam ierakstam nevar mainīt piegādātāju. Izveidojiet jaunu ierakstu."
        for field in ("stock_qty", "min_order_qty", "delivery_days"):
            value = data[field]
            minimum = 1 if field == "min_order_qty" else 0
            if not value.isascii() or not value.isdigit() or len(value) > 10 or not minimum <= int(value) <= 2147483647:
                errors[field] = f"Norādiet veselu skaitli no {minimum} līdz 2 147 483 647."
        if data["vat_included"] not in {"0", "1"}:
            errors["vat_included"] = "Norādiet, vai PVN ir iekļauts cenā."
        if not errors:
            item = offer or Offer(created_by_admin_id=current_user.id, data_source="manual")
            item.supplier = supplier
            item.supplier_name = supplier.name
            item.product = product
            item.supplier_sku = data["supplier_sku"] or None
            item.unit_price = Decimal(price_text)
            item.vat_included = data["vat_included"] == "1"
            item.is_active = data["is_active"]
            item.delivery_price = supplier.delivery_price
            for field in ("stock_qty", "min_order_qty", "delivery_days"):
                setattr(item, field, int(data[field]))
            db.session.add(item)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors["supplier_id"] = "Neizdevās saglabāt. Pārbaudiet piegādātāju un preci."
            else:
                flash("Piegādātāja prece saglabāta.", "success")
                return redirect(url_for("admin.supplier_detail", supplier_id=supplier.id))
    suppliers = db.session.scalars(db.select(Supplier).order_by(Supplier.name)).all()
    products = db.session.scalars(db.select(Product).order_by(Product.name)).all()
    data["unit_price"] = data["unit_price"].replace(",", ".")
    return render_template("admin/offer_form.html", offer=offer, form_data=data, errors=errors,
                           suppliers=suppliers, products=products, supplier=supplier,
                           csrf_token=_product_csrf_token()), (422 if errors else 200)
