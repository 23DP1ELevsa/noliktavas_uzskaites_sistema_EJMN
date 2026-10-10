from flask import Blueprint, jsonify, render_template, request

from ..extensions import db
from ..models import Category, Product
from ..services.catalog import CatalogFilterError, CatalogFilters, search_catalog


catalog_bp = Blueprint("catalog", __name__, url_prefix="/catalog")


@catalog_bp.get("/products/<int:product_id>")
def product_page(product_id):
    product = db.first_or_404(db.select(Product).where(
        Product.id == product_id, Product.is_active.is_(True)))
    offers = sorted((offer for offer in product.offers if offer.is_active),
                    key=lambda offer: (offer.unit_price, offer.id))
    return render_template("product.html", product=product, offers=offers)


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
