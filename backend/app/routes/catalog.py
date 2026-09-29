from flask import Blueprint, jsonify, request

catalog_bp = Blueprint("catalog", __name__, url_prefix="/catalog")

# Pagaidu dati kataloga servera loģikas izstrādei.
# Vēlāk šo sarakstu aizstās datubāzes vaicājums.
PRODUCTS = [
    {"id": 1, "name": "USB-C kabelis", "category": "Elektronika", "price": 8.99, "active": True},
    {"id": 2, "name": "Bezvadu pele", "category": "Elektronika", "price": 19.90, "active": True},
    {"id": 3, "name": "Arhīva kaste", "category": "Biroja preces", "price": 3.50, "active": False},
]


@catalog_bp.get("")
def get_catalog():
    """Atgriež aktīvās preces un ļauj tās meklēt pēc nosaukuma."""
    query = request.args.get("q", "").strip().casefold()

    products = [product for product in PRODUCTS if product["active"]]

    if query:
        products = [
            product
            for product in products
            if query in product["name"].casefold()
        ]

    return jsonify(
        {
            "items": products,
            "count": len(products),
            "message": None if products else "Preces netika atrastas.",
        }
    )
