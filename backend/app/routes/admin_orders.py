from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Order
from ..services.orders import customer_details, notify_decision
from .admin import admin_bp, admin_required, _check_product_csrf, _product_csrf_token


@admin_bp.get("/orders")
@admin_required
def applications():
    status = request.args.get("status", "iesniegts")
    query = db.select(Order).options(joinedload(Order.user), joinedload(Order.company_profile))
    if status in {"iesniegts", "apstiprināts", "noraidīts"}:
        query = query.where(Order.status == status)
    orders = db.session.scalars(query.order_by(Order.created_at.desc(), Order.id.desc())).all()
    pending = db.session.scalar(db.select(db.func.count(Order.id)).where(Order.status == "iesniegts"))
    return render_template("admin/orders.html", orders=orders, status=status, pending=pending, customer_details=customer_details)


@admin_bp.route("/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def application_detail(order_id):
    if request.method == "POST":
        _check_product_csrf()
    query = db.select(Order).where(Order.id == order_id)
    if request.method == "POST":
        query = query.with_for_update().execution_options(populate_existing=True)
    order = db.first_or_404(query)
    note = request.form.get("admin_note", "").strip() if request.method == "POST" else ""
    error = None
    status_code = 200
    if request.method == "POST":
        decision = request.form.get("decision")
        if decision not in {"approve", "decline"}:
            abort(400)
        if order.status != "iesniegts":
            error, status_code = "Šis pieteikums jau ir izskatīts. Lēmums nav mainīts.", 409
        elif len(note) > 1000 or any(ord(c) < 32 and c not in "\n\r\t" for c in note):
            error, status_code = "Komentārs nedrīkst pārsniegt 1000 rakstzīmes vai saturēt vadības rakstzīmes.", 422
        elif decision == "decline" and not note:
            error, status_code = "Lai noraidītu pieteikumu, norādiet noraidīšanas iemeslu.", 422
        else:
            order.status = "apstiprināts" if decision == "approve" else "noraidīts"
            order.admin_note = note or None
            order.processed_by_admin_id = current_user.id
            order.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            try:
                notify_decision(order)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                error, status_code = "Lēmumu neizdevās saglabāt. Mēģiniet vēlreiz.", 503
            else:
                flash("Lēmums saglabāts. Paziņojumi nosūtīti profilos.", "success")
                return redirect(url_for("admin.application_detail", order_id=order.id))
    return render_template("admin/order_detail.html", order=order, customer=customer_details(order),
                           error=error, note=note, csrf_token=_product_csrf_token()), status_code
