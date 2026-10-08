from flask import Blueprint, jsonify, request

from ..services.catalog import CatalogFilterError, CatalogFilters, search_catalog


catalog_bp = Blueprint("catalog", __name__, url_prefix="/catalog")


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
