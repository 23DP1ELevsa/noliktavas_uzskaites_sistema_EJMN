from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Offer, OrderItem, Supplier
from ..services.admin_pagination import paginate_admin
from ..services.suppliers import supplier_form_data, supplier_values, validate_supplier
from .admin import admin_bp, admin_required, _check_product_csrf, _product_csrf_token


def supplier_has_relations(supplier):
    return (db.session.scalar(db.select(Offer.id).where(Offer.supplier_id == supplier.id).limit(1)) is not None
            or db.session.scalar(db.select(OrderItem.id).where(OrderItem.supplier_id == supplier.id).limit(1)) is not None)


@admin_bp.get("/suppliers")
@admin_required
def suppliers():
    q = request.args.get("q", "").strip()[:255]
    status = request.args.get("status", "all")
    query = db.select(Supplier).options(selectinload(Supplier.offers))
    if q:
        query = query.where(db.or_(Supplier.name.icontains(q, autoescape=True),
                                  Supplier.contact_person.icontains(q, autoescape=True),
                                  Supplier.email.icontains(q, autoescape=True)))
    if status in {"active", "inactive"}:
        query = query.where(Supplier.is_active.is_(status == "active"))
    pagination = paginate_admin(query.order_by(Supplier.name_key, Supplier.id), q=q, status=status)
    return render_template("admin/suppliers.html", suppliers=pagination.items, pagination=pagination, q=q, status=status)


@admin_bp.get("/suppliers/<int:supplier_id>")
@admin_required
def supplier_detail(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    order_count = db.session.scalar(db.select(db.func.count(db.distinct(OrderItem.order_id)))
                                   .where(OrderItem.supplier_id == supplier.id))
    return render_template("admin/supplier_detail.html", supplier=supplier, order_count=order_count,
                           has_relations=supplier_has_relations(supplier), csrf_token=_product_csrf_token())


@admin_bp.route("/suppliers/new", methods=["GET", "POST"])
@admin_bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@admin_required
def supplier_form(supplier_id=None):
    supplier = db.get_or_404(Supplier, supplier_id) if supplier_id is not None else None
    data = supplier_form_data(request.form if request.method == "POST" else None, supplier)
    errors = {}
    if request.method == "POST":
        _check_product_csrf()
        if supplier:
            db.session.refresh(supplier, with_for_update=True)
        errors = validate_supplier(data, supplier)
        if not errors:
            item = supplier or Supplier()
            old_price = item.delivery_price
            values = supplier_values(data)
            for field, value in values.items():
                setattr(item, field, value)
            db.session.add(item)
            if supplier:
                with db.session.no_autoflush:
                    for offer in db.session.scalars(db.select(Offer).where(Offer.supplier_id == supplier.id)
                                                   .order_by(Offer.id).with_for_update()):
                        offer.supplier_name = item.name
                        if old_price != item.delivery_price:
                            offer.delivery_price = item.delivery_price
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors["name"] = "Piegādātāju neizdevās saglabāt. Pārbaudiet nosaukuma unikalitāti."
            else:
                flash("Piegādātājs veiksmīgi atjaunināts." if supplier else "Piegādātājs veiksmīgi izveidots.", "success")
                return redirect(url_for("admin.supplier_detail", supplier_id=item.id))
    return render_template("admin/supplier_form.html", supplier=supplier, form_data=data,
                           errors=errors, csrf_token=_product_csrf_token()), (422 if errors else 200)


@admin_bp.post("/suppliers/<int:supplier_id>/status")
@admin_required
def supplier_status(supplier_id):
    _check_product_csrf()
    supplier = db.get_or_404(Supplier, supplier_id)
    if request.form.get("is_active") not in {"0", "1"}:
        abort(400)
    supplier.is_active = request.form["is_active"] == "1"
    db.session.commit()
    flash("Piegādātājs aktivizēts." if supplier.is_active else "Piegādātājs deaktivizēts. Saistītie dati ir saglabāti.", "success")
    return redirect(url_for("admin.supplier_detail", supplier_id=supplier.id))


@admin_bp.route("/suppliers/<int:supplier_id>/delete", methods=["GET", "POST"])
@admin_required
def delete_supplier(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    has_relations = supplier_has_relations(supplier)
    if request.method == "POST":
        _check_product_csrf()
        if request.form.get("confirmed") != "1":
            abort(400, description="Darbība jāapstiprina.")
        if has_relations:
            flash("Piegādātāju nevar dzēst: tam ir saistīti piedāvājumi vai pasūtījumi. Varat to deaktivizēt.", "error")
        else:
            db.session.delete(supplier)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Piegādātāju nevar dzēst, jo tam ir pievienoti saistīti dati.", "error")
            else:
                flash("Piegādātājs veiksmīgi dzēsts.", "success")
                return redirect(url_for("admin.suppliers"))
        return redirect(url_for("admin.supplier_detail", supplier_id=supplier.id))
    return render_template("admin/supplier_delete.html", supplier=supplier,
                           has_relations=has_relations, csrf_token=_product_csrf_token())
