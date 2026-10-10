from functools import wraps
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import Category, Offer, Product

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _category_form_data():
    return {
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip() or None,
    }


def _validate_category(data):
    if not data["name"]:
        return "Kategorijas nosaukums ir obligāts."
    if len(data["name"]) > 150:
        return "Kategorijas nosaukums nedrīkst pārsniegt 150 rakstzīmes."
    return None


@admin_bp.get("/categories")
@admin_required
def categories():
    items = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    return render_template("admin/categories.html", categories=items)


@admin_bp.route("/categories/new", methods=["GET", "POST"])
@admin_required
def create_category():
    data = _category_form_data()
    if request.method == "POST":
        error = _validate_category(data)
        if error:
            flash(error, "error")
        else:
            category = Category(**data)
            db.session.add(category)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Kategorija ar šādu nosaukumu jau pastāv.", "error")
            else:
                flash("Kategorija veiksmīgi izveidota.", "success")
                return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=None, form_data=data)


@admin_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_category(category_id):
    category = db.get_or_404(Category, category_id)
    data = _category_form_data() if request.method == "POST" else {
        "name": category.name,
        "description": category.description or "",
    }
    if request.method == "POST":
        error = _validate_category(data)
        if error:
            flash(error, "error")
        else:
            category.name = data["name"]
            category.description = data["description"]
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Kategorija ar šādu nosaukumu jau pastāv.", "error")
            else:
                flash("Kategorija veiksmīgi atjaunināta.", "success")
                return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=category, form_data=data)


@admin_bp.post("/categories/<int:category_id>/delete")
@admin_required
def delete_category(category_id):
    category = db.get_or_404(Category, category_id)
    if category.products:
        flash("Kategoriju nevar dzēst, kamēr tai ir piesaistītas preces.", "error")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Kategorija veiksmīgi dzēsta.", "success")
    return redirect(url_for("admin.categories"))


def _product_csrf_token():
    if "product_csrf_token" not in session:
        session["product_csrf_token"] = secrets.token_hex(32)
    return session["product_csrf_token"]


def _check_product_csrf():
    expected = session.get("product_csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not supplied.isascii() or not secrets.compare_digest(expected, supplied):
        abort(400, description="Nederīgs formas drošības kods. Atveriet formu vēlreiz.")


def _product_form_data(product=None):
    fields = ("name", "sku", "category_id", "description", "image_url", "brand", "model", "unit")
    if request.method == "POST":
        data = {field: request.form.get(field, "").strip() for field in fields}
        data["sku"] = data["sku"].upper()
        data["is_active"] = request.form.get("is_active") == "1"
    else:
        data = {field: (getattr(product, field) or "") if product else "" for field in fields}
        data["unit"] = product.unit if product else "gab."
        data["is_active"] = product.is_active if product else True
    return data


def _validate_product(data, product=None):
    errors = {}
    for field, label, limit in (("name", "Nosaukums", 255), ("sku", "SKU", 100),
                                 ("unit", "Mērvienība", 30), ("brand", "Zīmols", 100),
                                 ("model", "Modelis", 100), ("image_url", "Attēla saite", 2048)):
        if field in {"name", "sku", "unit"} and not data[field]:
            errors[field] = f"{label} ir obligāts lauks."
        elif len(data[field]) > limit:
            errors[field] = f"{label} nedrīkst pārsniegt {limit} rakstzīmes."
    category_id = str(data["category_id"])
    if (not category_id.isascii() or not category_id.isdigit()
            or len(category_id) > 19 or not 0 < int(category_id) <= 9223372036854775807
            or db.session.get(Category, int(category_id)) is None):
        errors["category_id"] = "Izvēlieties esošu kategoriju."
    if data["sku"]:
        query = db.select(Product.id).where(db.func.lower(Product.sku) == data["sku"].lower())
        if product:
            query = query.where(Product.id != product.id)
        if db.session.scalar(query) is not None:
            errors["sku"] = "Prece ar šādu SKU jau pastāv. Izvēlieties unikālu SKU."
    if data["image_url"]:
        try:
            parsed = urlsplit(data["image_url"])
            valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                     and not parsed.username and not parsed.password
                     and not any(char.isspace() or ord(char) < 32 for char in data["image_url"]))
            parsed.port  # Reject invalid port numbers as well.
        except ValueError:
            valid = False
        if not valid:
            errors["image_url"] = "Norādiet pilnu attēla saiti, kas sākas ar https:// vai http://."
    return errors


@admin_bp.get("/products")
@admin_required
def products():
    q = request.args.get("q", "").strip()[:255]
    status = request.args.get("status", "all")
    query = db.select(Product).options(joinedload(Product.category), selectinload(Product.offers))
    if q:
        query = query.where(db.or_(Product.name.icontains(q, autoescape=True),
                                  Product.sku.icontains(q, autoescape=True)))
    if status in {"active", "inactive"}:
        query = query.where(Product.is_active.is_(status == "active"))
    items = db.session.scalars(query.order_by(Product.name, Product.id)).all()
    total = db.session.scalar(db.select(db.func.count(Product.id)))
    active = db.session.scalar(db.select(db.func.count(Product.id)).where(Product.is_active.is_(True)))
    return render_template("admin/products.html", products=items, q=q, status=status,
                           total=total, active=active)


@admin_bp.get("/products/<int:product_id>")
@admin_required
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    return render_template("admin/product_detail.html", product=product)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_form(product_id=None):
    product = db.get_or_404(Product, product_id) if product_id is not None else None
    data = _product_form_data(product)
    errors = {}
    if request.method == "POST":
        _check_product_csrf()
        errors = _validate_product(data, product)
        if not errors:
            item = product or Product()
            for field, value in data.items():
                if field == "category_id":
                    value = int(value)
                elif field != "is_active":
                    value = value or None
                setattr(item, field, value)
            db.session.add(item)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors["sku"] = "Preci neizdevās saglabāt. Pārbaudiet SKU un kategoriju."
            else:
                flash("Prece veiksmīgi atjaunināta." if product else "Prece veiksmīgi izveidota.", "success")
                return redirect(url_for("admin.product_detail", product_id=item.id))
    categories = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    return render_template("admin/product_form.html", product=product, form_data=data,
                           errors=errors, categories=categories, csrf_token=_product_csrf_token()), (422 if errors else 200)


@admin_bp.route("/products/<int:product_id>/delete", methods=["GET", "POST"])
@admin_required
def delete_product(product_id):
    product = db.get_or_404(Product, product_id)
    has_relations = db.session.scalar(db.select(Offer.id).where(Offer.product_id == product.id).limit(1)) is not None
    if request.method == "POST":
        _check_product_csrf()
        if request.form.get("confirmed") != "1":
            abort(400, description="Darbība jāapstiprina.")
        if has_relations:
            product.is_active = False
        else:
            db.session.delete(product)
        try:
            db.session.commit()
        except IntegrityError:
            # Another request may have attached an offer after our check.
            db.session.rollback()
            product.is_active = False
            db.session.commit()
            has_relations = True
        flash("Prece deaktivizēta. Saistītie piedāvājumi un pasūtījumi ir saglabāti."
              if has_relations else "Prece veiksmīgi dzēsta.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_delete.html", product=product,
                           has_relations=has_relations, csrf_token=_product_csrf_token())
