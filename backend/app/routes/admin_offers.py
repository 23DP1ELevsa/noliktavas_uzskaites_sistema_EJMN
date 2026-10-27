from decimal import Decimal
from datetime import datetime, timezone
import re

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import CartItem, Category, Offer, Order, OrderItem, Product, Supplier
from ..services.admin_pagination import paginate_admin
from .admin import admin_bp, admin_required, _check_product_csrf, _product_csrf_token


@admin_bp.get("")
@admin_bp.get("/")
@admin_required
def dashboard():
    sections = [
        ("Piegādātāji", "Kontaktinformācija, piegādes maksa un piegādātāja preces.", Supplier, "suppliers", "supplier_form", "Pievienot piegādātāju"),
        ("Preces", "Preču nosaukumi, attēli, apraksti un kategorijas.", Product, "products", "product_form", "Pievienot preci"),
        ("Piedāvājumi", "Piegādātāju cenas, PVN, atlikumi un pasūtīšanas nosacījumi.", Offer, "supplier_products", "offer_form", "Pievienot piedāvājumu"),
        ("Kategorijas", "Preču kataloga iedalījums.", Category, "categories", "create_category", "Pievienot kategoriju"),
    ]
    cards = [dict(title=title, description=description,
                  count=db.session.scalar(db.select(db.func.count(model.id))),
                  list_url=url_for("admin." + listing), add_url=url_for("admin." + adding), action=action)
             for title, description, model, listing, adding, action in sections]
    cards.insert(0, dict(title="Pieteikumi", description="Klientu pieteikumi, to dati un lēmumi.",
                        count=db.session.scalar(db.select(db.func.count(Order.id)).where(Order.status == "iesniegts")),
                        add_url=url_for("admin.applications"), list_url=url_for("admin.applications", status="all"),
                        action="Izskatīt pieteikumus", secondary="Visi pieteikumi"))
    return render_template("admin/dashboard.html", cards=cards)


@admin_bp.get("/supplier-products")
@admin_required
def supplier_products():
    q = request.args.get("q", "").strip()[:255]
    status = request.args.get("status", "all")
    query = db.select(Offer).join(Product).options(joinedload(Offer.product), joinedload(Offer.supplier))
    if q:
        query = query.where(db.or_(Product.name.icontains(q, autoescape=True),
                                  Offer.supplier_name.icontains(q, autoescape=True),
                                  Product.sku.icontains(q, autoescape=True),
                                  Offer.supplier_sku.icontains(q, autoescape=True)))
    if status in {"active", "inactive"}:
        query = query.where(Offer.is_active.is_(status == "active"))
    pagination = paginate_admin(query.order_by(Offer.supplier_name, Product.name, Offer.id), q=q, status=status)
    return render_template("admin/supplier_products.html", offers=pagination.items, pagination=pagination, q=q, status=status)


def _selected_id(value, model):
    value = str(value)
    if value.isascii() and value.isdigit() and len(value) <= 19 and 0 < int(value) <= 9223372036854775807:
        return db.session.get(model, int(value))
    return None


@admin_bp.route("/supplier-products/new", methods=["GET", "POST"])
@admin_bp.route("/supplier-products/<int:offer_id>/edit", methods=["GET", "POST"])
@admin_required
def offer_form(offer_id=None):
    offer = None
    if offer_id is not None:
        query = db.select(Offer).where(Offer.id == offer_id)
        if request.method == "POST":
            query = query.with_for_update().execution_options(populate_existing=True)
        offer = db.first_or_404(query)
    fields = ("supplier_id", "product_id", "supplier_sku", "unit_price", "vat_included", "vat_rate", "currency", "stock_qty", "min_order_qty", "delivery_days")
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
                        stock_qty="0", min_order_qty="1", delivery_days="0", currency="EUR")
    supplier = _selected_id(data["supplier_id"], Supplier)
    product = _selected_id(data["product_id"], Product)
    if request.method == "POST":
        if supplier is None:
            errors["supplier_id"] = "Izvēlieties esošu piegādātāju."
        if product is None:
            errors["product_id"] = "Izvēlieties esošu preci."
        if len(data["supplier_sku"]) > 100:
            errors["supplier_sku"] = "Kods nedrīkst pārsniegt 100 rakstzīmes."
        elif supplier and data["supplier_sku"]:
            duplicate_query = db.select(Offer.id).where(
                Offer.supplier_id == supplier.id, Offer.supplier_sku == data["supplier_sku"])
            if offer:
                duplicate_query = duplicate_query.where(Offer.id != offer.id)
            if db.session.scalar(duplicate_query) is not None:
                errors["supplier_sku"] = "Šim piegādātājam piedāvājums ar šādu preces kodu jau pastāv."
        price_text = data["unit_price"].replace(",", ".")
        if not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,2})?", price_text):
            errors["unit_price"] = "Norādiet cenu no 0 līdz 99 999 999,99 €, ar ne vairāk kā divām zīmēm aiz komata."
        if supplier and product and data["is_active"]:
            # Different supplier codes must not produce two active prices for the
            # same supplier and catalog product.
            duplicate_product = db.select(Offer.id).where(
                Offer.product_id == product.id, Offer.is_active.is_(True),
                db.or_(Offer.supplier_id == supplier.id,
                       db.and_(Offer.supplier_id.is_(None),
                               Offer.supplier_name == supplier.name)))
            if offer is not None:
                duplicate_product = duplicate_product.where(Offer.id != offer.id)
            if db.session.scalar(duplicate_product.limit(1)) is not None:
                errors["product_id"] = (
                    "Šim piegādātājam šai precei jau ir aktīvs piedāvājums. "
                    "Rediģējiet esošo piedāvājumu vai deaktivizējiet to."
                )
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
        rate = data["vat_rate"].replace(",", ".")
        if not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,2})?", rate) or Decimal(rate) > 100:
            errors["vat_rate"] = "Norādiet PVN likmi no 0 līdz 100 %, ar ne vairāk kā divām zīmēm aiz komata."
        if data["currency"] != "EUR":
            errors["currency"] = "Izvēlieties EUR — kataloga un groza valūtu."
        if (offer and "stock_qty" not in errors
                and int(data["stock_qty"]) + offer.allocated_qty > 2147483647):
            errors["stock_qty"] = "Atlikums kopā ar rezervēto daudzumu pārsniedz atļauto robežu."
        if not errors:
            item = offer or Offer(created_by_admin_id=current_user.id, data_source="manual")
            item.supplier = supplier
            item.supplier_name = supplier.name
            item.product = product
            item.supplier_sku = data["supplier_sku"] or None
            item.unit_price = Decimal(price_text)
            item.vat_included = data["vat_included"] == "1"
            item.vat_rate = Decimal(rate)
            item.currency = data["currency"]
            item.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            item.is_active = data["is_active"]
            item.delivery_price = supplier.delivery_price
            for field in ("stock_qty", "min_order_qty", "delivery_days"):
                setattr(item, field, int(data[field]))
            # Manual editing explicitly sets the free balance, unlike supplier feeds.
            item.imported_stock_qty = None
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
    data["vat_rate"] = data["vat_rate"].replace(",", ".")
    return render_template("admin/offer_form.html", offer=offer, form_data=data, errors=errors,
                           suppliers=suppliers, products=products, supplier=supplier,
                           csrf_token=_product_csrf_token()), (422 if errors else 200)


@admin_bp.route("/supplier-products/<int:offer_id>/delete", methods=["GET", "POST"])
@admin_required
def delete_offer(offer_id):
    if request.method == "POST":
        _check_product_csrf()
        if request.form.get("confirmed") != "1":
            abort(400, description="Darbība jāapstiprina.")
        offer = db.first_or_404(db.select(Offer).where(Offer.id == offer_id).with_for_update()
                               .execution_options(populate_existing=True))
    else:
        offer = db.get_or_404(Offer, offer_id)
    in_history = db.session.scalar(db.select(OrderItem.id).where(OrderItem.offer_id == offer.id).limit(1)) is not None
    in_cart = db.session.scalar(db.select(CartItem.id).where(CartItem.offer_id == offer.id).limit(1)) is not None
    preserve = in_history or in_cart
    if request.method == "POST":
        if preserve:
            offer.is_active = False
            offer.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            db.session.delete(offer)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Piedāvājumu neizdevās mainīt. Atveriet apstiprinājumu vēlreiz.", "error")
            return redirect(url_for("admin.delete_offer", offer_id=offer_id))
        flash("Piedāvājums deaktivizēts. Saistītie grozi un pasūtījumi saglabāti."
              if preserve else "Piedāvājums dzēsts.", "success")
        return redirect(url_for("admin.supplier_products"))
    return render_template("admin/offer_delete.html", offer=offer, preserve=preserve,
                           in_history=in_history, csrf_token=_product_csrf_token())
