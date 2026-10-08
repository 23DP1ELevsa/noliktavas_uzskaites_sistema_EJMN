from decimal import Decimal

import pytest
from sqlalchemy import event

from backend.app.extensions import db
from backend.app.models import Category, Offer, Product, User


@pytest.fixture
def catalog(database_app):
    admin = User(email="catalog-admin@example.test", full_name="Admin", role="admin",
                 password_hash="unused-test-hash")
    electronics = Category(name="Elektronika")
    office = Category(name="Biroja preces")
    definitions = [
        ("cable", "USB-C kabelis", electronics, True),
        ("mouse", "Bezvadu pele", electronics, True),
        ("paper", "Arhīva kaste", office, True),
        ("empty", "Prece bez piedāvājumiem", electronics, True),
        ("archived", "Prece ar neaktīvu piedāvājumu", electronics, True),
        ("special", "100%_Ātrā/pele", electronics, True),
        ("limited", "Ierobežots atlikums", electronics, True),
        ("hidden", "Slēpts USB-C kabelis", electronics, False),
    ]
    products = {
        sku: Product(sku=sku, name=name, category=category, is_active=active)
        for sku, name, category, active in definitions
    }
    products["cable"].brand = "Test Brand"
    products["cable"].model = "C1"
    products["cable"].description = "Testa apraksts"
    offers = [
        ("cable", "North", "8.99", 10, 2, True),
        ("cable", "North", "12.00", 10, 1, True),
        ("cable", "South", "19.90", 0, 1, True),
        ("cable", "South", "7.00", 1, 3, True),
        ("cable", "North", "0.50", 100, 1, False),
        ("mouse", "North", "25.00", 0, 1, True),
        ("paper", "South", "3.00", 10, 1, True),
        ("archived", "North", "1.00", 100, 1, False),
        ("special", "Ātra SIA %_", "3.50", 5, 1, True),
        ("limited", "North", "4.00", 1, 2, True),
        ("hidden", "North", "0.10", 100, 1, True),
    ]
    db.session.add_all(products.values())
    for sku, supplier, price, stock, minimum, active in offers:
        db.session.add(Offer(
            product=products[sku], created_by_admin=admin, supplier_name=supplier,
            unit_price=Decimal(price), stock_qty=stock, min_order_qty=minimum,
            vat_included=True, is_active=active,
        ))
    db.session.commit()
    return database_app.test_client(), products, electronics.id, office.id


def get_items(catalog, **filters):
    response = catalog[0].get("/catalog", query_string=filters)
    assert response.status_code == 200
    assert response.json["count"] == len(response.json["items"])
    return response.json["items"]


def test_catalog_reads_active_products_and_public_information(catalog):
    items = get_items(catalog)
    assert len(items) == 7
    assert "hidden" not in {item["sku"] for item in items}
    assert all(item["active"] for item in items)
    cable = next(item for item in items if item["sku"] == "cable")
    assert cable["category"] == "Elektronika"
    assert cable["category_id"] == catalog[2]
    assert (cable["brand"], cable["model"], cable["description"], cable["unit"]) == (
        "Test Brand", "C1", "Testa apraksts", "gab.",
    )
    assert cable["price"] == 7.00 and cable["currency"] == "EUR"
    assert cable["available"] is True and cable["offer_count"] == 4
    assert len({item["id"] for item in items}) == 7
    assert [offer["unit_price"] for offer in cable["offers"]] == [7, 8.99, 12, 19.90]
    assert all("created_by_admin_id" not in offer for offer in cable["offers"])
    assert cable["offers"][0]["updated_at"].endswith("Z")


@pytest.mark.parametrize("query,expected", [
    ("  KABELIS  ", {"cable"}), ("PELE", {"mouse", "special"}),
    ("ātrā", {"special"}), ("ĀTRĀ", {"special"}),
    ("%", {"special"}), ("_", {"special"}), ("/", {"special"}),
    ("%_", {"special"}), ("' OR 1=1 --", set()), ("neeksiste", set()),
])
def test_name_search_is_case_insensitive_and_literal(catalog, query, expected):
    assert {item["sku"] for item in get_items(catalog, q=query)} == expected


def test_category_filter(catalog):
    assert [item["sku"] for item in get_items(catalog, category_id=catalog[3])] == ["paper"]
    assert "paper" not in {item["sku"] for item in get_items(catalog, category_id=catalog[2])}
    assert get_items(catalog, category_id=18446744073709551615) == []


@pytest.mark.parametrize("filters,expected", [
    ({"min_price": "8.99", "max_price": "8.99"}, {"cable"}),
    ({"min_price": "20"}, {"mouse"}),
    ({"max_price": "3"}, {"paper"}),
    ({"min_price": "5", "max_price": "6"}, set()),
    ({"max_price": "1"}, set()),
    ({"supplier": " north "}, {"cable", "mouse", "limited"}),
    ({"supplier": "North%"}, set()),
    ({"supplier": "ātra sia %_"}, {"special"}),
    ({"in_stock": "true"}, {"cable", "paper", "special"}),
    ({"in_stock": "1"}, {"cable", "paper", "special"}),
    ({"in_stock": "false"}, {"mouse", "empty", "archived", "limited"}),
    ({"in_stock": "0"}, {"mouse", "empty", "archived", "limited"}),
    ({"supplier": "South", "in_stock": "false"}, {"cable"}),
    ({"supplier": "North", "min_price": "18", "max_price": "20"}, set()),
    ({"supplier": "South", "in_stock": "true", "min_price": "5"}, set()),
    ({"min_price": "18", "max_price": "20", "in_stock": "true"}, set()),
])
def test_price_supplier_and_availability_filters(catalog, filters, expected):
    assert {item["sku"] for item in get_items(catalog, **filters)} == expected


def test_all_filters_match_the_same_offer_and_determine_displayed_price(catalog):
    items = get_items(catalog, q="KABELIS", category_id=catalog[2], min_price="8",
                      max_price="10", supplier="North", in_stock="true")
    assert len(items) == 1
    assert items[0]["price"] == 8.99
    assert items[0]["offer_count"] == 1
    assert items[0]["offers"][0]["supplier_name"] == "North"
    assert items[0]["available"] is True
    assert all(offer["available"] for offer in items[0]["offers"])


def test_filtered_offers_do_not_leak_between_requests(catalog):
    north = get_items(catalog, q="kabelis", supplier="North")[0]
    south = get_items(catalog, q="kabelis", supplier="South")[0]
    available = get_items(catalog, q="kabelis", in_stock="true")[0]
    assert {offer["supplier_name"] for offer in north["offers"]} == {"North"}
    assert {offer["supplier_name"] for offer in south["offers"]} == {"South"}
    assert north["price"] == available["price"] == 8.99
    assert south["price"] == 7 and south["available"] is False
    assert get_items(catalog, q="kabelis")[0]["offer_count"] == 4


def test_products_without_active_offers_have_no_price(catalog):
    for sku in ("empty", "archived"):
        item = next(item for item in get_items(catalog) if item["sku"] == sku)
        assert item["price"] is None and item["available"] is False
        assert item["offers"] == [] and item["offer_count"] == 0


def test_zero_price_and_exact_minimum_stock_are_valid(catalog):
    offer = db.session.scalar(db.select(Offer).where(Offer.product_id == catalog[1]["limited"].id))
    offer.unit_price = Decimal("0.00")
    offer.stock_qty = offer.min_order_qty
    db.session.commit()
    items = get_items(catalog, min_price="0", max_price="0", in_stock="true")
    assert [item["sku"] for item in items] == ["limited"]
    assert items[0]["price"] == 0 and items[0]["available"] is True


@pytest.mark.parametrize("filters", [
    {"q": "neeksiste"}, {"category_id": "999999"}, {"supplier": "Unknown"},
    {"min_price": "99999", "max_price": "999999"},
])
def test_no_results_have_a_consistent_response(catalog, filters):
    response = catalog[0].get("/catalog", query_string=filters)
    assert response.status_code == 200
    assert response.json == {"items": [], "count": 0, "message": "Preces netika atrastas."}


def test_empty_database_returns_empty_catalog(database_app):
    response = database_app.test_client().get("/catalog")
    assert response.status_code == 200
    assert response.json == {"items": [], "count": 0, "message": "Preces netika atrastas."}


def test_blank_filters_are_ignored(catalog):
    expected = get_items(catalog)
    assert get_items(catalog, q=" ", category_id="", min_price="", max_price=" ",
                     supplier=" ", in_stock="") == expected


@pytest.mark.parametrize("field,value", [
    ("category_id", "0"), ("category_id", "-1"), ("category_id", "abc"),
    ("category_id", "1.5"), ("category_id", "18446744073709551616"),
    ("min_price", "-1"), ("min_price", "NaN"), ("max_price", "Infinity"),
    ("max_price", "abc"), ("max_price", "8,99"), ("min_price", "1.001"),
    ("max_price", "100000000"), ("min_price", "1e2"), ("in_stock", "maybe"),
    ("q", "x" * 256), ("supplier", "x" * 256),
])
def test_invalid_filters_return_400_before_database_queries(database_app, field, value):
    response = database_app.test_client().get("/catalog", query_string={field: value})
    assert response.status_code == 400
    assert response.json["error"] == "invalid_filters"
    assert response.json["field"] == field
    assert response.json["message"]


def test_reversed_price_range_and_duplicate_parameters_are_rejected(database_app):
    client = database_app.test_client()
    response = client.get("/catalog?min_price=10&max_price=5")
    assert response.status_code == 400 and response.json["field"] == "max_price"
    response = client.get("/catalog?in_stock=true&in_stock=false")
    assert response.status_code == 400 and response.json["field"] == "in_stock"


def test_catalog_avoids_queries_per_product(catalog):
    db.session.remove()
    queries = []

    def record_query(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", record_query)
    try:
        assert len(get_items(catalog)) == 7
    finally:
        event.remove(db.engine, "before_cursor_execute", record_query)
    assert len(queries) == 2
