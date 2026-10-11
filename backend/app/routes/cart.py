from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Cart, CartItem, Offer, Product, User
from ..services.comparison import cart_csrf_token, comparison_rows, parse_quantity, require_cart_csrf

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


def _lock_user():
    # Serialize cart writes for this user, including creation of the first cart.
    db.session.scalar(db.select(User).where(User.id == current_user.id).with_for_update())


@cart_bp.get("")
@login_required
def cart_page():
    cart = db.session.scalar(db.select(Cart).where(Cart.user_id == current_user.id))
    items = db.session.scalars(db.select(CartItem).where(CartItem.cart_id == cart.id).options(
        joinedload(CartItem.offer).joinedload(Offer.product)
    ).order_by(CartItem.id)).all() if cart else []
    rows = []
    for item in items:
        row = comparison_rows([item.offer], item.quantity, "total-asc")[0]
        row["item"] = item
        if not item.offer.is_active or not item.offer.product.is_active:
            row["error"] = "Piedāvājums vairs nav aktīvs."
        rows.append(row)
    return render_template("cart.html", rows=rows,
                           total=sum((row["total"] for row in rows), Decimal("0.00")),
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
        Offer.id == offer_id, Offer.is_active.is_(True), Product.is_active.is_(True)
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
        if not offer.is_active or not offer.product.is_active:
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
