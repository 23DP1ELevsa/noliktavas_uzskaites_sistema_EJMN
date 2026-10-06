import re
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import CompanyProfile, User


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _safe_next_url(value):
    if not value:
        return None
    target = urljoin(request.host_url, value)
    parsed_target = urlparse(target)
    if parsed_target.scheme in {"http", "https"} and parsed_target.netloc == request.host:
        return target
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        user = db.session.scalar(db.select(User).where(User.email == email))

        if user is None or not user.check_password(password):
            flash("Nepareizs e-pasts vai parole.", "error")
        elif not user.is_active:
            flash("Šis konts ir deaktivizēts.", "error")
        else:
            login_user(user)
            flash("Veiksmīgi pieslēdzāties.", "success")
            next_url = request.args.get("next") or request.form.get("next")
            return redirect(_safe_next_url(next_url) or url_for("index"))

    return render_template("auth/login.html", next_url=request.args.get("next", ""))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        password_confirmation = request.form.get("password_confirmation", "")
        company_name = request.form.get("company_name", "").strip()
        registration_no = request.form.get("registration_no", "").strip()
        address = request.form.get("address", "").strip()
        vat_no = request.form.get("vat_no", "").strip() or None
        phone = request.form.get("phone", "").strip() or None

        errors = []
        if not full_name:
            errors.append("Ievadiet vārdu un uzvārdu.")
        if not EMAIL_PATTERN.fullmatch(email):
            errors.append("Ievadiet derīgu e-pasta adresi.")
        if len(password) < 8:
            errors.append("Parolei jābūt vismaz 8 rakstzīmes garai.")
        if password != password_confirmation:
            errors.append("Paroles nesakrīt.")
        if not company_name or not registration_no or not address:
            errors.append("Aizpildiet visus obligātos uzņēmuma laukus.")

        if not errors and db.session.scalar(db.select(User).where(User.email == email)):
            errors.append("Konts ar šo e-pasta adresi jau pastāv.")

        if errors:
            for error in errors:
                flash(error, "error")
        else:
            user = User(email=email, full_name=full_name)
            user.set_password(password)
            user.company_profile = CompanyProfile(
                company_name=company_name,
                registration_no=registration_no,
                vat_no=vat_no,
                phone=phone,
                address=address,
            )
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Konts ar šo e-pasta adresi jau pastāv.", "error")
            else:
                login_user(user)
                flash("Konts izveidots. Laipni lūdzam StockFlow!", "success")
                return redirect(url_for("index"))

    return render_template("auth/register.html")


@auth_bp.get("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("Jūs izgājāt no konta.", "success")
    return redirect(url_for("index"))
