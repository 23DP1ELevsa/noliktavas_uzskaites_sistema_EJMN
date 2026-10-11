import re
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import CompanyProfile, User


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REGISTRATION_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[ ./-][A-Za-z0-9]+)*")
VAT_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*")
PHONE_PATTERN = re.compile(r"\+?(?:[0-9]|\([0-9 ]+\)|[ .-])+")
COMPANY_FIELDS = ("company_name", "registration_no", "vat_no", "phone", "address", "delivery_address")


def _company_form_data():
    return {field: request.form.get(field, "").strip() for field in COMPANY_FIELDS}


def _validate_profile_data(data):
    errors = {}
    for field, label, limit, required in (
        ("full_name", "Vārds un uzvārds", 150, True),
        ("company_name", "Uzņēmuma nosaukums", 255, True),
        ("registration_no", "Reģistrācijas numurs", 50, True),
        ("vat_no", "PVN numurs", 50, False),
        ("phone", "Tālrunis", 50, False),
        ("address", "Uzņēmuma adrese", 255, True),
        ("delivery_address", "Piegādes adrese", 255, False),
    ):
        value = data[field]
        if required and not value:
            errors[field] = f"{label} ir obligāts lauks."
        elif len(value) > limit:
            errors[field] = f"{label} nedrīkst pārsniegt {limit} rakstzīmes."
        elif any(ord(char) < 32 or ord(char) == 127 for char in value):
            errors[field] = f"{label} nedrīkst saturēt vadības rakstzīmes."

    for field, pattern, message in (
        ("registration_no", REGISTRATION_PATTERN,
         "Reģistrācijas numurā izmantojiet burtus, ciparus un atdalītājus (atstarpi, punktu, / vai -)."),
        ("vat_no", VAT_PATTERN,
         "PVN numurā izmantojiet burtus, ciparus, atstarpes vai defises."),
    ):
        if data[field] and field not in errors and not pattern.fullmatch(data[field]):
            errors[field] = message

    phone = data["phone"]
    if phone and "phone" not in errors:
        digits = re.sub(r"[^0-9]", "", phone)
        if not PHONE_PATTERN.fullmatch(phone) or not 7 <= len(digits) <= 15:
            errors["phone"] = "Ievadiet tālruni ar 7–15 cipariem, piemēram, +371 20000000."
    return errors


def _company_values(data):
    return {field: data[field] or None for field in COMPANY_FIELDS}


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

    form_data = _company_form_data()
    form_data["full_name"] = request.form.get("full_name", "").strip()
    field_errors = {}
    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        password_confirmation = request.form.get("password_confirmation", "")
        field_errors = _validate_profile_data(form_data)
        errors = list(field_errors.values())
        if len(email) > 255 or not EMAIL_PATTERN.fullmatch(email):
            errors.append("Ievadiet derīgu e-pasta adresi.")
        if len(password) < 8:
            errors.append("Parolei jābūt vismaz 8 rakstzīmes garai.")
        if password != password_confirmation:
            errors.append("Paroles nesakrīt.")

        if not errors and db.session.scalar(db.select(User).where(User.email == email)):
            errors.append("Konts ar šo e-pasta adresi jau pastāv.")

        if errors:
            for error in errors:
                flash(error, "error")
        else:
            user = User(email=email, full_name=form_data["full_name"])
            user.set_password(password)
            user.company_profile = CompanyProfile(**_company_values(form_data))
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

    return render_template("auth/register.html", form_data=form_data, errors=field_errors)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile = current_user.company_profile
    errors = {}
    if request.method == "POST":
        form_data = _company_form_data()
        form_data["full_name"] = request.form.get("full_name", "").strip()
        errors = _validate_profile_data(form_data)

        if errors:
            flash("Profils nav saglabāts. Pārbaudiet atzīmētos laukus.", "error")
        else:
            current_user.full_name = form_data["full_name"]
            if profile is None:
                profile = CompanyProfile(user=current_user, **_company_values(form_data))
                db.session.add(profile)
            else:
                for field, value in _company_values(form_data).items():
                    setattr(profile, field, value)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Profilu neizdevās saglabāt. Mēģiniet vēlreiz.", "error")
            else:
                flash("Profils veiksmīgi saglabāts.", "success")
                return redirect(url_for("auth.profile"))
    else:
        form_data = {field: (getattr(profile, field) or "") if profile else ""
                     for field in COMPANY_FIELDS}
        form_data["full_name"] = current_user.full_name

    return render_template("auth/profile.html", profile=profile, form_data=form_data, errors=errors)


@auth_bp.get("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("Jūs izgājāt no konta.", "success")
    return redirect(url_for("index"))
