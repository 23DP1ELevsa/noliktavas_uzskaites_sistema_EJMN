from flask import Blueprint, jsonify, render_template, request

from ..extensions import db
from ..models import Category, Product
from ..services.catalog import CatalogFilterError, CatalogFilters, search_catalog
from ..services.comparison import SORT_OPTIONS, cart_csrf_token, comparison_rows, parse_quantity


catalog_bp = Blueprint("catalog", __name__, url_prefix="/catalog")


@catalog_bp.get("/products/<int:product_id>")
def product_page(product_id):
    product = db.first_or_404(db.select(Product).where(
        Product.id == product_id, Product.is_active.is_(True)))
    offers = [offer for offer in product.offers if offer.is_active]
    error = None
    try:
        quantity = parse_quantity(request.args.get("quantity", "1"))
    except ValueError as exc:
        quantity, error = 1, str(exc)
    sort = request.args.get("sort", "total-asc")
    if sort not in SORT_OPTIONS:
        sort, error = "total-asc", "Izvēlieties derīgu kārtošanas veidu."
    rows = comparison_rows(offers, quantity, sort)
    return render_template("product.html", product=product, offers=offers, rows=rows,
                           quantity=quantity, sort=sort, comparison_error=error,
                           max_quantity=2147483647, csrf_token=cart_csrf_token())


@catalog_bp.get("/page")
def catalog_page():
    categories = db.session.scalars(
        db.select(Category).order_by(Category.name)
    ).all()
    return render_template("catalog.html", categories=categories)


@catalog_bp.get("")
def get_catalog():
    """Atgriež aktīvās preces no datubāzes, izmantojot izvēlētos filtrus."""
    try:
        filters = CatalogFilters.from_args(request.args)
    except CatalogFilterError as error:
        return jsonify({"error": "invalid_filters", "field": error.field,
                        "message": str(error)}), 400

    products = search_catalog(filters)

    return jsonify(
        {
            "items": products,
            "count": len(products),
            "message": None if products else "Preces netika atrastas.",
        }
    )
