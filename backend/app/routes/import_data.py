from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from .admin import admin_required, _check_product_csrf, _product_csrf_token
from ..services.json_import import MAX_FILE_BYTES, SAMPLE_FILE, import_json_offers
from ..services.offer_import import OfferImportError

import_bp = Blueprint("import_data", __name__, url_prefix="/admin/import")


@import_bp.route("/json", methods=["GET", "POST"])
@admin_required
def json_page():
    error, status = None, 200
    if request.method == "POST":
        if request.content_length and request.content_length > MAX_FILE_BYTES + 65536:
            return render_template("admin/import_json.html", csrf_token=_product_csrf_token(),
                                   error="JSON fails pārsniedz atļauto izmēru: 2 MiB."), 413
        _check_product_csrf()
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            error, status = "Izvēlieties JSON failu.", 422
        elif not upload.filename.lower().endswith(".json"):
            error, status = "Izvēlieties failu ar .json paplašinājumu.", 422
        else:
            try:
                result = import_json_offers(upload.stream, admin_id=current_user.id)
            except OfferImportError as failure:
                error, status = str(failure), 422
                if failure.field:
                    error += f" Lauks: {failure.field}."
            else:
                flash(f"JSON imports pabeigts. Pievienoti: {result['added']}; atjaunināti: {result['updated']}.", "success")
                return redirect(url_for("import_data.json_page"))
    return render_template("admin/import_json.html", csrf_token=_product_csrf_token(), error=error), status


@import_bp.get("/json/sample")
@admin_required
def json_sample():
    return send_file(SAMPLE_FILE, mimetype="application/json", as_attachment=True,
                     download_name="offers_import.json")
