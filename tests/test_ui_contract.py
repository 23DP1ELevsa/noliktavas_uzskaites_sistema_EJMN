"""Browser error copy is localized without changing authorization or API errors."""

from urllib.parse import parse_qs, urlsplit

import pytest

from backend.app.extensions import db
from backend.app.models import User


def test_login_required_notice_is_latvian_and_preserves_destination(database_app):
    client = database_app.test_client()
    destination = "/orders?status=iesniegts"

    response = client.get(destination)

    assert response.status_code == 302
    location = urlsplit(response.location)
    assert location.path == "/auth/login"
    assert parse_qs(location.query)["next"] == [destination]
    html = client.get(response.location).get_data(as_text=True)
    assert "Lai turpinātu, lūdzu, pieslēdzieties savam kontam." in html
    assert "Please log in" not in html
    assert 'name="next" value="/orders?status=iesniegts"' in html


@pytest.mark.parametrize("method,path,status,title", [
    ("GET", "/orders?status=nepareizs", 400, "Pieprasījumu neizdevās apstrādāt"),
    ("GET", "/admin", 403, "Piekļuve nav atļauta"),
    ("GET", "/neeksistejosa-lapa", 404, "Lapa nav atrasta"),
    ("POST", "/", 405, "Darbība nav atļauta"),
])
def test_browser_errors_are_latvian_and_keep_http_status(database_app, method, path, status, title):
    user = User(email="ui-contract@example.test", full_name="Pārbaudes pircējs", password_hash="unused", role="user")
    db.session.add(user)
    db.session.commit()
    client = database_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True

    response = client.open(path, method=method)

    assert response.status_code == status
    html = response.get_data(as_text=True)
    assert '<html lang="lv">' in html
    assert f"<h1>{title}</h1>" in html
    assert f"Kļūda {status}" in html
    assert "Atvērt katalogu" in html
    assert "The requested URL" not in html
    assert "You don't have the permission" not in html
    if status == 405:
        assert "GET" in {method.strip() for method in response.headers["Allow"].split(",")}


def test_catalog_and_api_errors_keep_existing_response_contracts(database_app):
    client = database_app.test_client()

    invalid_filter = client.get("/catalog?min_price=NaN")

    assert invalid_filter.status_code == 400
    assert invalid_filter.is_json
    assert invalid_filter.json == {
        "error": "invalid_filters",
        "field": "min_price",
        "message": "Cena jānorāda no 0 līdz 99999999.99, ar ne vairāk kā divām zīmēm aiz punkta.",
    }
    for path in ("/catalog", "/api/test/offers"):
        method_error = client.post(path)
        assert method_error.status_code == 405
        assert method_error.mimetype == "text/html"
        assert "405 Method Not Allowed" in method_error.get_data(as_text=True)
        assert "StockFlow" not in method_error.get_data(as_text=True)
