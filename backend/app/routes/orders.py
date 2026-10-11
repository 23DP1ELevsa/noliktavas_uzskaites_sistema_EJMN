from datetime import datetime, timezone
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import CompanyProfile, Order, OrderItem, User
from ..services.cart import checkout_fingerprint, load_cart_summary
from ..services.comparison import cart_csrf_token, require_cart_csrf
from ..services.shopping_errors import shopping_database_error
from ..services.orders import customer_details, notify_submission
import re

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")
orders_bp.register_error_handler(SQLAlchemyError, shopping_database_error)


@orders_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    if request.method == "POST":
        require_cart_csrf()
        db.session.scalar(db.select(User).where(User.id == current_user.id).with_for_update())
    summary = load_cart_summary(current_user.id, lock=request.method == "POST")
    if not summary["rows"]:
        flash("Pievienojiet preces grozam, lai noformētu pieteikumu.", "error")
        return redirect(url_for("cart.cart_page"))
    if not summary["can_checkout"]:
        flash(summary["checkout_error"] or "Pārbaudiet grozu: daļa preču nav pieejama izvēlētajā daudzumā.", "error")
        return redirect(url_for("cart.cart_page"))
    profile_query = db.select(CompanyProfile).where(CompanyProfile.user_id == current_user.id)
    if request.method == "POST":
        profile_query = profile_query.with_for_update().execution_options(populate_existing=True)
    profile = db.session.scalar(profile_query)
    profile_complete = bool(profile and profile.company_name.strip() and profile.registration_no.strip()
                            and profile.address.strip() and profile.effective_delivery_address.strip())
    form_data = {
        "delivery_address": request.form.get("delivery_address", profile.effective_delivery_address if profile else "").strip(),
        "phone": request.form.get("phone", profile.phone or "" if profile else "").strip(),
        "note": request.form.get("note", "").strip(),
    }
    errors = {}
    fingerprint = checkout_fingerprint(summary, profile)
    if request.method == "POST":
        review = session.get("checkout_review", {})
        if not profile_complete:
            flash("Pirms iesniegšanas papildiniet uzņēmuma profilu.", "error")
            return redirect(url_for("orders.checkout"))
        if (review.get("fingerprint") != fingerprint or not review.get("token")
                or not secrets.compare_digest(review["token"].encode(), request.form.get("review_token", "").encode())):
            flash("Groza vai uzņēmuma dati ir mainījušies. Pārskatiet pieteikumu un iesniedziet atkārtoti.", "error")
            return redirect(url_for("orders.checkout"))
        if not form_data["delivery_address"] or len(form_data["delivery_address"]) > 255 or any(ord(c) < 32 for c in form_data["delivery_address"]):
            errors["delivery_address"] = "Norādiet piegādes adresi līdz 255 rakstzīmēm."
        phone = form_data["phone"]
        if phone and (len(phone) > 50 or not re.fullmatch(r"\+?[0-9() .-]+", phone) or not 7 <= len(re.sub(r"\D", "", phone)) <= 15):
            errors["phone"] = "Norādiet tālruni ar 7–15 cipariem."
        if len(form_data["note"]) > 1000 or any(ord(c) < 32 and c not in "\n\r\t" for c in form_data["note"]):
            errors["note"] = "Piezīme nedrīkst pārsniegt 1000 rakstzīmes vai saturēt vadības rakstzīmes."
        if not errors:
            snapshot = dict(company_name=profile.company_name, registration_no=profile.registration_no,
                            vat_no=profile.vat_no or "", address=profile.address,
                            full_name=current_user.full_name, email=current_user.email, **form_data)
            order = Order(user_id=current_user.id, company_profile_id=profile.id,
                          total_amount=summary["total"], customer_snapshot=snapshot)
            db.session.add(order)
            for row in summary["rows"]:
                offer, item = row["offer"], row["item"]
                db.session.add(OrderItem(order=order, offer=offer, supplier_id=offer.supplier_id, product_name=offer.product.name,
                                        supplier_name=offer.supplier_name, unit_price=offer.unit_price,
                                        quantity=item.quantity, delivery_price=offer.delivery_price,
                                        line_total=row["total"], vat_included=offer.vat_included,
                                        vat_rate=offer.vat_rate, currency=offer.currency))
                db.session.delete(item)
            summary["cart"].updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            notify_submission(order)
            db.session.commit()
            session.pop("checkout_review", None)
            return redirect(url_for("orders.order_detail", order_id=order.id))
    review = {"fingerprint": fingerprint, "token": secrets.token_hex(32)}
    session["checkout_review"] = review
    return render_template("checkout.html", **summary, profile=profile, profile_complete=profile_complete,
                           csrf_token=cart_csrf_token(), review_token=review["token"],
                           form_data=form_data, errors=errors), (422 if errors else 200)


@orders_bp.get("/<int:order_id>")
@login_required
def order_detail(order_id):
    order = db.first_or_404(db.select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    return render_template("order.html", order=order, customer=customer_details(order))


@orders_bp.get("")
@login_required
def order_list():
    orders = db.session.scalars(db.select(Order).where(Order.user_id == current_user.id)
                                .order_by(Order.created_at.desc(), Order.id.desc())).all()
    return render_template("orders.html", orders=orders)
