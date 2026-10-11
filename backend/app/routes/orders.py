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
        order = Order(user_id=current_user.id, company_profile_id=profile.id, total_amount=summary["total"])
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
        db.session.commit()
        session.pop("checkout_review", None)
        return redirect(url_for("orders.order_detail", order_id=order.id))
    review = {"fingerprint": fingerprint, "token": secrets.token_hex(32)}
    session["checkout_review"] = review
    return render_template("checkout.html", **summary, profile=profile, profile_complete=profile_complete,
                           csrf_token=cart_csrf_token(), review_token=review["token"])


@orders_bp.get("/<int:order_id>")
@login_required
def order_detail(order_id):
    order = db.first_or_404(db.select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    return render_template("order.html", order=order)
