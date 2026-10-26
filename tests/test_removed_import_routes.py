"""Retired external offer imports stay unavailable; file imports remain supported."""

import pytest

from backend.app.config import environment_config
from backend.app.models import Offer
from backend.app.extensions import db
from backend.app.services.demo_data import ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
from backend.app.services.offer_import import OfferImportError, save_imported_offers
from test_offer_import import inventory, record


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_retired_offer_import_and_demo_routes_return_not_found(database_app, authenticated, method):
    client = database_app.test_client()
    if authenticated:
        result = database_app.test_cli_runner().invoke(args=["seed-demo"])
        assert result.exit_code == 0, result.output
        client.post("/auth/login", data={"email": ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD})

    for path in ("/admin/import/api", "/api/test/offers"):
        assert client.open(path, method=method).status_code == 404
    assert not any(rule.endpoint.startswith("test_api.") or rule.endpoint == "import_data.api_page"
                   for rule in database_app.url_map.iter_rules())


def test_retired_import_configuration_is_not_exposed(monkeypatch):
    monkeypatch.setenv("TEST_API_URL", "https://retired-source.example.test/offers")

    assert "TEST_API_URL" not in environment_config()


def test_external_import_source_is_rejected_without_saving_records(inventory):
    with pytest.raises(OfferImportError) as failure:
        save_imported_offers([record(inventory)], source="API", admin_id=inventory[0].id)

    assert failure.value.field == "source"
    assert db.session.scalar(db.select(db.func.count(Offer.id))) == 0


def test_file_import_navigation_only_lists_supported_formats(database_app):
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    client = database_app.test_client()
    client.post("/auth/login", data={"email": ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD})

    for kind in ("json", "csv"):
        response = client.get(f"/admin/import/{kind}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert '/admin/import/json' in html and '/admin/import/csv' in html
        assert '/admin/import/api' not in html
