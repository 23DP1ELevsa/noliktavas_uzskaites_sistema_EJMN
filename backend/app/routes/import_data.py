from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from .admin import admin_required, _check_product_csrf, _product_csrf_token
from ..services.json_import import MAX_FILE_BYTES, SAMPLE_FILE, import_json_offers
from ..services.csv_import import SAMPLE_FILE as CSV_SAMPLE_FILE, import_csv_offers
from ..services.offer_import import OfferImportError
from ..services.api_import import DEFAULT_TIMEOUT, import_api_offers

import_bp = Blueprint("import_data", __name__, url_prefix="/admin/import")


@import_bp.route("/json", methods=["GET", "POST"])
@admin_required
def json_page():
    return _upload_page("JSON", import_json_offers)


@import_bp.route("/csv", methods=["GET", "POST"])
@admin_required
def csv_page():
    return _upload_page("CSV", import_csv_offers)


def _upload_page(kind, importer):
    error, status = None, 200
    context = {"import_format": kind, "sample_endpoint": f"import_data.{kind.lower()}_sample"}
    if request.method == "POST":
        if request.content_length and request.content_length > MAX_FILE_BYTES + 65536:
            return render_template("admin/import_json.html", csrf_token=_product_csrf_token(),
                                   error=f"{kind} fails pārsniedz atļauto izmēru: 2 MiB.", **context), 413
        _check_product_csrf()
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            error, status = f"Izvēlieties {kind} failu.", 422
        elif not upload.filename.lower().endswith("." + kind.lower()):
            error, status = f"Izvēlieties failu ar .{kind.lower()} paplašinājumu.", 422
        else:
            try:
                result = importer(upload.stream, admin_id=current_user.id)
            except OfferImportError as failure:
                error, status = str(failure), 422
                if failure.field:
                    error += f" Lauks: {failure.field}."
            else:
                flash(f"{kind} imports pabeigts. Pievienoti: {result['added']}; atjaunināti: {result['updated']}.", "success")
                return redirect(url_for(f"import_data.{kind.lower()}_page"))
    return render_template("admin/import_json.html", csrf_token=_product_csrf_token(), error=error, **context), status


@import_bp.get("/json/sample")
@admin_required
def json_sample():
    return send_file(SAMPLE_FILE, mimetype="application/json", as_attachment=True,
                     download_name="offers_import.json")


@import_bp.get("/csv/sample")
@admin_required
def csv_sample():
    return send_file(CSV_SAMPLE_FILE, mimetype="text/csv", as_attachment=True,
                     download_name="offers_import.csv")


@import_bp.route("/api", methods=["GET", "POST"])
@admin_required
def api_page():
    error = None
    if request.method == "POST":
        _check_product_csrf()
        try:
            result = import_api_offers(current_app.config["TEST_API_URL"], admin_id=current_user.id)
        except OfferImportError as failure:
            error = str(failure)
            if failure.field:
                error += f" Lauks: {failure.field}."
        else:
            flash(f"API imports pabeigts. Pievienoti: {result['added']}; atjaunināti: {result['updated']}.", "success")
            return redirect(url_for("import_data.api_page"))
    return render_template("admin/import_api.html", import_format="API", error=error,
                           api_url=current_app.config["TEST_API_URL"], timeout=DEFAULT_TIMEOUT,
                           csrf_token=_product_csrf_token()), (422 if error else 200)
