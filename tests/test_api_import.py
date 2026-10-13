from email.message import Message
from decimal import Decimal
from http.client import IncompleteRead
from io import BytesIO
import json
from threading import Thread
import time
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

from flask import Response, redirect
import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.serving import make_server

from backend.app.extensions import db
from backend.app.services.api_import import APIImportError, DEFAULT_TIMEOUT, fetch_api_offers, import_api_offers
from backend.app.services.json_import import SAMPLE_FILE
from backend.app.services.offer_import import MAX_FILE_BYTES, OfferImportError
from backend.test_api import create_test_api
from test_offer_import import inventory, record, offers
from test_json_import import upload_client, json_record


URL = "http://127.0.0.1:5001/api/test/offers"


class FakeResponse:
    def __init__(self, body=b"[]", status=200, content_type="application/json", encoding=None, failure=None):
        self.body, self.status, self.failure = body, status, failure
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if encoding:
            self.headers["Content-Encoding"] = encoding
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, size):
        assert size == MAX_FILE_BYTES + 1
        if self.failure:
            raise self.failure
        return self.body[:size]


def mock_response(monkeypatch, response):
    calls = []
    def open_request(request, timeout):
        calls.append((request, timeout))
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr("backend.app.services.api_import.build_opener",
                        lambda *args: SimpleNamespace(open=open_request))
    return calls


def test_demo_endpoint_is_public_static_and_has_no_database_dependency(database_app):
    independent = create_test_api().test_client()
    standalone = independent.get("/api/test/offers")
    embedded = database_app.test_client().get("/api/test/offers")
    assert standalone.status_code == embedded.status_code == 200
    assert standalone.content_type.startswith("application/json")
    assert standalone.data == embedded.data == SAMPLE_FILE.read_bytes()
    assert len(standalone.get_json()) == 2
    assert independent.get("/health").get_json() == {"status": "ok"}


def test_request_method_headers_timeout_and_empty_array(monkeypatch):
    response = FakeResponse()
    calls = mock_response(monkeypatch, response)
    assert fetch_api_offers(URL) == []
    request, timeout = calls[0]
    assert request.get_method() == "GET" and request.full_url == URL
    assert request.get_header("Accept") == "application/json"
    assert timeout == DEFAULT_TIMEOUT and response.closed


@pytest.mark.parametrize("url", [None, "", "file:///C:/data", "ftp://host/offers", "http://",
    "http://user:secret@host/data", "http://host/data#fragment", "http://host:99999/data", "http://host/ data"])
def test_invalid_configured_url_is_rejected(url):
    with pytest.raises(APIImportError, match="TEST_API_URL"):
        fetch_api_offers(url)


@pytest.mark.parametrize("timeout", [0, -1, 31, True, "5", float("nan")])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(APIImportError):
        fetch_api_offers(URL, timeout=timeout)


@pytest.mark.parametrize("failure,message", [
    (TimeoutError(), "gaidīšanas laiks"),
    (URLError(TimeoutError()), "gaidīšanas laiks"),
    (URLError(OSError("connection refused")), "savienoties"),
    (OSError("connection reset"), "pilnībā"),
    (IncompleteRead(b"partial", 10), "pilnībā"),
])
def test_connection_timeout_and_truncated_response_errors(monkeypatch, failure, message):
    mock_response(monkeypatch, failure)
    with pytest.raises(APIImportError, match=message):
        fetch_api_offers(URL)


def test_timeout_while_reading_response_closes_it(monkeypatch):
    response = FakeResponse(failure=TimeoutError())
    mock_response(monkeypatch, response)
    with pytest.raises(APIImportError, match="gaidīšanas laiks"):
        fetch_api_offers(URL)
    assert response.closed


@pytest.mark.parametrize("status", [204, 301, 404, 500, 503])
def test_bad_response_status_is_rejected(monkeypatch, status):
    response = FakeResponse(status=status)
    mock_response(monkeypatch, response)
    with pytest.raises(APIImportError, match=str(status)):
        fetch_api_offers(URL)
    assert response.closed


def test_http_error_body_is_closed_without_import(monkeypatch):
    body = BytesIO(b"untrusted error")
    mock_response(monkeypatch, HTTPError(URL, 500, "error", Message(), body))
    with pytest.raises(APIImportError, match="500"):
        fetch_api_offers(URL)
    assert body.closed


@pytest.mark.parametrize("response", [FakeResponse(content_type="text/html"), FakeResponse(encoding="gzip"),
    FakeResponse(body=b"not JSON"), FakeResponse(body=b'{"offers": []}'),
    FakeResponse(body=b" " * (MAX_FILE_BYTES + 1))])
def test_wrong_content_type_structure_encoding_and_size_are_rejected(monkeypatch, response):
    mock_response(monkeypatch, response)
    with pytest.raises(APIImportError):
        fetch_api_offers(URL)


def test_validation_preserves_record_and_field_and_no_partial_changes(inventory, monkeypatch):
    rows = [json_record(inventory), json_record(inventory, supplier_sku="OTHER", stock_qty=-1)]
    mock_response(monkeypatch, FakeResponse(body=json.dumps(rows).encode()))
    with pytest.raises(APIImportError) as failure:
        import_api_offers(URL, admin_id=inventory[0].id)
    assert failure.value.row == 2 and failure.value.field == "stock_qty" and offers() == []


def test_api_uses_shared_identity_across_sources(inventory, monkeypatch):
    from backend.app.services.offer_import import save_imported_offers
    save_imported_offers([record(inventory)], source="CSV", admin_id=inventory[0].id)
    identifier = offers()[0].id
    rows = [json_record(inventory, unit_price="12.50"), json_record(inventory, supplier_sku="OTHER")]
    mock_response(monkeypatch, FakeResponse(body=json.dumps(rows).encode()))
    assert import_api_offers(URL, admin_id=inventory[0].id) == {"added": 1, "updated": 1}
    assert offers()[0].id == identifier and offers()[0].unit_price == Decimal("12.50")
    assert all(offer.data_source == "API" for offer in offers())
    assert import_api_offers(URL, admin_id=inventory[0].id) == {"added": 0, "updated": 2}


@pytest.fixture
def live_api():
    app = create_test_api()
    app.add_url_rule("/redirect", endpoint="redirect_demo", view_func=lambda: redirect("/api/test/offers"))
    app.add_url_rule("/bad", endpoint="bad_demo", view_func=lambda: Response(b"not-json", mimetype="application/json"))
    def slow():
        time.sleep(0.15)
        return Response(b"[]", mimetype="application/json")
    app.add_url_rule("/slow", view_func=slow)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_http_fetch_redirect_and_timeout(live_api):
    rows = fetch_api_offers(live_api + "/api/test/offers")
    assert len(rows) == 2 and rows[1]["unit_price"] == Decimal("74.00")
    with pytest.raises(APIImportError, match="302"):
        fetch_api_offers(live_api + "/redirect")
    with pytest.raises(APIImportError, match="gaidīšanas laiks"):
        fetch_api_offers(live_api + "/slow", timeout=0.02)
    with pytest.raises(APIImportError, match="nav derīgi"):
        fetch_api_offers(live_api + "/bad")


def test_api_upload_page_real_http_repetition_and_csrf(upload_client, database_app, live_api):
    client, token = upload_client
    database_app.config["TEST_API_URL"] = live_api + "/api/test/offers"
    page = client.get("/admin/import/api").get_data(as_text=True)
    assert 'aria-current="page">API' in page and 'class="form-panel"' in page
    assert page.count("<footer") == 1
    count = len(offers())
    for _ in range(2):
        response = client.post("/admin/import/api", data={"csrf_token": token, "url": "http://untrusted.invalid/"}, follow_redirects=True)
        assert response.status_code == 200 and "Pievienoti: 0; atjaunināti: 2." in response.get_data(as_text=True)
    assert len(offers()) == count and len([offer for offer in offers() if offer.data_source == "API"]) == 2
    assert client.post("/admin/import/api").status_code == 400


def test_page_failure_and_commit_failure_preserve_database(upload_client, database_app, monkeypatch):
    client, token = upload_client
    database_app.config["TEST_API_URL"] = URL
    before = [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()]
    mock_response(monkeypatch, URLError(TimeoutError()))
    response = client.post("/admin/import/api", data={"csrf_token": token})
    assert response.status_code == 422 and "gaidīšanas laiks" in response.get_data(as_text=True)
    mock_response(monkeypatch, FakeResponse(body=SAMPLE_FILE.read_bytes()))
    def fail_commit():
        db.session.flush()
        raise IntegrityError("commit", {}, Exception("simulated failure"))
    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        response = client.post("/admin/import/api", data={"csrf_token": token})
    assert response.status_code == 422 and "visas importa izmaiņas atceltas" in response.get_data(as_text=True)
    assert [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()] == before


def test_api_import_requires_admin(database_app):
    from backend.app.services.demo_data import USER_EMAIL, DEFAULT_USER_PASSWORD
    client = database_app.test_client()
    assert client.get("/admin/import/api").status_code == 302
    assert client.post("/admin/import/api").status_code == 302
    database_app.test_cli_runner().invoke(args=["seed-demo"])
    client.post("/auth/login", data={"email": USER_EMAIL, "password": DEFAULT_USER_PASSWORD})
    assert client.get("/admin/import/api").status_code == 403
    assert client.post("/admin/import/api").status_code == 403


def test_embedded_api_can_be_fetched_during_import_request(upload_client, database_app):
    client, token = upload_client
    server = make_server("127.0.0.1", 0, database_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    database_app.config["TEST_API_URL"] = f"http://127.0.0.1:{server.server_port}/api/test/offers"
    try:
        response = client.post("/admin/import/api", data={"csrf_token": token}, follow_redirects=True)
        assert response.status_code == 200
        assert "Pievienoti: 0; atjaunināti: 2." in response.get_data(as_text=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_api_url_configuration_is_independent_of_request_host(monkeypatch):
    from backend.app.config import environment_config
    monkeypatch.setattr("backend.app.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("TEST_API_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert environment_config()["TEST_API_URL"] == "http://127.0.0.1:5000/api/test/offers"
    monkeypatch.setenv("PORT", "8123")
    assert environment_config()["TEST_API_URL"] == "http://127.0.0.1:8123/api/test/offers"
    monkeypatch.setenv("TEST_API_URL", "https://api.example.test/offers")
    assert environment_config()["TEST_API_URL"] == "https://api.example.test/offers"
