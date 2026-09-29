from backend.app import create_app


def make_client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_catalog_returns_only_active_products():
    response = make_client().get("/catalog")

    assert response.status_code == 200
    assert response.json["count"] == 2
    assert all(product["active"] for product in response.json["items"])


def test_catalog_searches_by_product_name_case_insensitive():
    response = make_client().get("/catalog?q=PELE")

    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["items"][0]["name"] == "Bezvadu pele"


def test_catalog_returns_empty_result_correctly():
    response = make_client().get("/catalog?q=neeksiste")

    assert response.status_code == 200
    assert response.json["items"] == []
    assert response.json["count"] == 0
    assert response.json["message"] == "Preces netika atrastas."
