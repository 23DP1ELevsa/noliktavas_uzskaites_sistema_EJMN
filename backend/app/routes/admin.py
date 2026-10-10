from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Category

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
