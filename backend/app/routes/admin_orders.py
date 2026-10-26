from datetime import datetime, timezone
from collections import Counter
import re

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Offer, Order
from ..services.stock import allocate, release_order_stock
from ..services.orders import customer_details, mark_order_notifications_read, notify_decision
from ..services.order_review import approval_issues
from .admin import admin_bp, admin_required, _check_product_csrf, _product_csrf_token


@admin_bp.get("/orders")
@admin_required
def applications():
    status = request.args.get("status", "iesniegts")
    sort = request.args.get("sort", "date-desc")
    if status not in {"all", "iesniegts", "apstiprināts", "noraidīts"} or sort not in {"date-desc", "date-asc"}:
        abort(400, description="Nederīga pieteikumu atlase.")
    page = request.args.get("page", "1")
    if not re.fullmatch(r"[0-9]{1,7}", page) or not 1 <= int(page) <= 1000000:
        abort(400, description="Nederīgs lapas numurs.")
    conditions = [Order.status == status] if status != "all" else []
    total = db.session.scalar(db.select(db.func.count(Order.id)).where(*conditions))
    pages = max(1, (total + 11) // 12)
    page = min(int(page), pages)
    ordering = (Order.created_at.desc(), Order.id.desc()) if sort == "date-desc" else (Order.created_at.asc(), Order.id.asc())
    query = db.select(Order).where(*conditions).options(joinedload(Order.user), joinedload(Order.company_profile))
    orders = db.session.scalars(query.order_by(*ordering).limit(12).offset((page - 1) * 12)).all()
    pending = db.session.scalar(db.select(db.func.count(Order.id)).where(Order.status == "iesniegts"))
    return render_template("admin/orders.html", orders=orders, status=status, sort=sort, pending=pending,
                           total=total, page=page, pages=pages, customer_details=customer_details)


@admin_bp.route("/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def application_detail(order_id):
    if request.method == "POST":
        _check_product_csrf()
    query = db.select(Order).where(Order.id == order_id)
    if request.method == "POST":
        query = query.with_for_update().execution_options(populate_existing=True)
    order = db.first_or_404(query)
    if request.method == "GET":
        mark_order_notifications_read(current_user.id, order.id)
    note = request.form.get("admin_note", "").strip() if request.method == "POST" else ""
    error = None
    issues = None
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
            try:
                issues = approval_issues(order, lock=True) if decision == "approve" else []
                if issues:
                    error, status_code = "Pieteikumu nevar apstiprināt: piedāvājumu dati ir mainījušies vai daudzums nav pieejams.", 409
                    db.session.rollback()
                else:
                    if decision == "decline":
                        release_order_stock(order)
                    elif not order.stock_deducted:
                        # Orders submitted before migration 0008 were not allocated.
                        quantities = Counter()
                        for item in order.items:
                            quantities[item.offer_id] += item.quantity
                        for offer in db.session.scalars(db.select(Offer).where(Offer.id.in_(quantities))):
                            allocate(offer, quantities[offer.id])
                        order.stock_deducted = True
                    order.status = "apstiprināts" if decision == "approve" else "noraidīts"
                    order.admin_note = note or None
                    order.processed_by_admin_id = current_user.id
                    order.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    notify_decision(order)
                    db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                error, status_code = "Lēmumu neizdevās saglabāt. Mēģiniet vēlreiz.", 503
            else:
                if not error:
                    flash("Lēmums saglabāts. Paziņojumi nosūtīti profilos.", "success")
                    return redirect(url_for("admin.application_detail", order_id=order.id))
    if issues is None:
        issues = approval_issues(order) if order.status == "iesniegts" else []
    if error:
        flash(error, "error")
    return render_template("admin/order_detail.html", order=order, customer=customer_details(order),
                           error=error, note=note, approval_issues=issues, csrf_token=_product_csrf_token()), status_code
