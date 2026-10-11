from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Cart, CartItem, Offer, Product, User
from ..services.comparison import cart_csrf_token, comparison_rows, parse_quantity, require_cart_csrf
from ..services.cart import load_cart_summary
from ..services.shopping_errors import shopping_database_error

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")
cart_bp.register_error_handler(SQLAlchemyError, shopping_database_error)


def _lock_user():
    # Serialize cart writes for this user, including creation of the first cart.
    db.session.scalar(db.select(User).where(User.id == current_user.id).with_for_update())


@cart_bp.get("")
@login_required
def cart_page():
    return render_template("cart.html", **load_cart_summary(current_user.id),
                           csrf_token=cart_csrf_token())


@cart_bp.post("/items")
@login_required
def add_item():
    require_cart_csrf()
    _lock_user()
    try:
        offer_id = parse_quantity(request.form.get("offer_id"))
        quantity = parse_quantity(request.form.get("quantity"))
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("cart.cart_page"))
    offer = db.first_or_404(db.select(Offer).join(Product).where(
        Offer.id == offer_id, Offer.is_active.is_(True), Product.is_active.is_(True),
        db.or_(Offer.supplier_id.is_(None), Offer.supplier.has(is_active=True))
    ).with_for_update())
    destination = url_for("catalog.product_page", product_id=offer.product_id,
                          quantity=quantity, sort=request.form.get("sort", "total-asc"))
    cart = db.session.scalar(db.select(Cart).where(Cart.user_id == current_user.id))
    item = db.session.scalar(db.select(CartItem).where(
        CartItem.cart_id == cart.id, CartItem.offer_id == offer.id)) if cart else None
    combined = quantity + (item.quantity if item else 0)
    if quantity < offer.min_order_qty or combined > offer.stock_qty or combined > 2147483647:
        flash(f"Preci nevar pievienot. Minimālais daudzums: {offer.min_order_qty}; "
              f"noliktavā: {offer.stock_qty}; grozā jau ir: {item.quantity if item else 0}.", "error")
        return redirect(destination)
    if cart is None:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
    if item:
        item.quantity = combined
    else:
        db.session.add(CartItem(cart=cart, offer=offer, quantity=quantity))
    cart.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    flash(f"{offer.product.name}: {quantity} {offer.product.unit} pievienoti grozam.", "success")
    return redirect(destination)


@cart_bp.post("/items/<int:item_id>/update")
@login_required
def update_item(item_id):
    require_cart_csrf()
    _lock_user()
    item = db.first_or_404(db.select(CartItem).join(Cart).where(
        CartItem.id == item_id, Cart.user_id == current_user.id))
    offer = db.session.scalar(db.select(Offer).where(Offer.id == item.offer_id).with_for_update())
    try:
        quantity = parse_quantity(request.form.get("quantity"))
        if not offer.is_active or not offer.product.is_active or not offer.supplier_active:
            raise ValueError("Piedāvājums vairs nav aktīvs.")
        error = comparison_rows([offer], quantity, "total-asc")[0]["error"]
        if error:
            raise ValueError(error)
    except ValueError as error:
        flash(str(error), "error")
    else:
        item.quantity = quantity
        item.cart.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        flash("Daudzums grozā atjaunināts.", "success")
    return redirect(url_for("cart.cart_page"))


@cart_bp.post("/items/<int:item_id>/remove")
@login_required
def remove_item(item_id):
    require_cart_csrf()
    _lock_user()
    item = db.first_or_404(db.select(CartItem).join(Cart).where(
        CartItem.id == item_id, Cart.user_id == current_user.id))
    item.cart.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.delete(item)
    db.session.commit()
    flash("Prece izņemta no groza.", "success")
    return redirect(url_for("cart.cart_page"))
