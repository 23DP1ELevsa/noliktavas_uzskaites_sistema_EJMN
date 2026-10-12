from decimal import Decimal
from io import BytesIO
import json

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.extensions import db
from backend.app.models import Offer
from backend.app.services.demo_data import ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, USER_EMAIL, DEFAULT_USER_PASSWORD
from backend.app.services.json_import import JSONImportError, MAX_FILE_BYTES, MAX_RECORDS, SAMPLE_FILE, import_json_offers, read_json_offers
from backend.app.services.offer_import import OfferImportError
from test_offer_import import inventory, record, offers


def stream(records):
    return BytesIO(json.dumps(records, ensure_ascii=False).encode("utf-8"))


def json_record(inventory, **changes):
    data = record(inventory)
    for field in ("min_order_qty", "stock_qty", "delivery_days"):
        data[field] = int(data[field])
    return {**data, **changes}


def test_json_numeric_values_preserve_decimal_precision(inventory):
    raw = json.dumps([json_record(inventory)]).replace('"10.25"', '0.10')
    parsed = read_json_offers(BytesIO(raw.encode()))
    assert parsed[0]["unit_price"] == Decimal("0.10")
    assert type(parsed[0]["unit_price"]) is Decimal
    assert parsed[0]["stock_qty"] == 15 and parsed[0]["vat_included"] is False


def test_utf8_bom_latvian_supplier_and_empty_array(inventory):
    data = json_record(inventory, supplier_name=inventory[3][0].name)
    del data["supplier_id"]
    raw = stream([data]).getvalue()
    assert read_json_offers(BytesIO(b"\xef\xbb\xbf" + raw))[0]["supplier_name"] == inventory[3][0].name
    assert read_json_offers(BytesIO(b"[]")) == []


@pytest.mark.parametrize("raw", [b"", b"   ", b"{}", b"null", b"123", b'"text"',
                                  b'{"offers": []}', b"[null]", b"[[]]", b"[true]",
                                  b"[1]", b"[{}]", b"\xff\xfe"])
def test_invalid_structure_or_encoding_reports_safe_error(raw):
    with pytest.raises(JSONImportError):
        read_json_offers(BytesIO(raw))


def test_syntax_error_has_file_line_and_column():
    with pytest.raises(JSONImportError) as failure:
        read_json_offers(BytesIO(b'[\n {"price": 1,}\n]'))
    assert failure.value.line == 2 and failure.value.column is not None
    assert "sintakses kļūda" in str(failure.value)


@pytest.mark.parametrize("field,value", [
    ("product_sku", 123), ("supplier_sku", None), ("supplier_id", True),
    ("supplier_id", "1"), ("supplier_name", []), ("currency", 123),
    ("unit_price", True), ("unit_price", []), ("unit_price", {}), ("unit_price", None),
    ("vat_rate", False), ("vat_rate", []), ("vat_included", "false"), ("vat_included", 0),
    ("stock_qty", "15"), ("stock_qty", 1.5), ("stock_qty", True),
    ("min_order_qty", None), ("delivery_days", 2.0), ("delivery_price", None),
    ("is_active", "true"),
])
def test_invalid_type_identifies_record_and_field_without_writes(inventory, field, value):
    rows = [json_record(inventory), json_record(inventory, **{"supplier_sku": "SUP-002", field: value})]
    with pytest.raises(JSONImportError) as failure:
        import_json_offers(stream(rows), admin_id=inventory[0].id)
    assert failure.value.row == 2 and failure.value.field == field
    assert offers() == []


@pytest.mark.parametrize("field", ["product_sku", "supplier_sku", "currency", "unit_price",
                                  "vat_included", "stock_qty", "min_order_qty", "delivery_days"])
def test_missing_field_identifies_record(inventory, field):
    data = json_record(inventory)
    del data[field]
    with pytest.raises(JSONImportError) as failure:
        read_json_offers(stream([json_record(inventory), data]))
    assert failure.value.row == 2 and failure.value.field == field
    assert "Trūkst obligātā" in str(failure.value)


@pytest.mark.parametrize("field,value", [("unit_price", "-1"), ("currency", "USD"),
                                        ("vat_rate", "100.01"), ("stock_qty", -1),
                                        ("unit_price", "0.001"), ("unit_price", "1e2")])
def test_json_uses_common_value_validation(inventory, field, value):
    with pytest.raises(JSONImportError) as failure:
        read_json_offers(stream([json_record(inventory, **{field: value})]))
    assert failure.value.row == 1 and failure.value.field == field


def test_duplicate_json_keys_are_not_silently_overwritten(inventory):
    row = json.dumps(json_record(inventory)).replace('"unit_price": "10.25"', '"unit_price": "10.25", "unit_price": "99"')
    raw = '[' + json.dumps(json_record(inventory)) + ',' + row + ']'
    with pytest.raises(JSONImportError) as failure:
        read_json_offers(BytesIO(raw.encode()))
    assert failure.value.row == 2 and failure.value.field == "unit_price"


def test_unknown_fields_and_supplier_reference_are_checked(inventory):
    with pytest.raises(JSONImportError) as failure:
        read_json_offers(stream([json_record(inventory, data_source="API")]))
    assert failure.value.field == "data_source"
    data = json_record(inventory)
    del data["supplier_id"]
    with pytest.raises(JSONImportError) as failure:
        read_json_offers(stream([data]))
    assert failure.value.field == "supplier_id"


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_nonstandard_nonfinite_constants_are_rejected(constant):
    with pytest.raises(JSONImportError, match="NaN vai Infinity"):
        read_json_offers(BytesIO(b'[{"unit_price": ' + constant + b'}]'))


def test_size_record_count_and_deep_nesting_are_bounded():
    with pytest.raises(JSONImportError, match="izmēru"):
        read_json_offers(BytesIO(b" " * (MAX_FILE_BYTES + 1)))
    with pytest.raises(JSONImportError, match="ne vairāk"):
        read_json_offers(stream([None] * (MAX_RECORDS + 1)))
    with pytest.raises(JSONImportError):
        read_json_offers(BytesIO(b"[" * 2000 + b"]" * 2000))


def test_file_read_failure_and_text_mode_are_reported():
    class Broken:
        def read(self, size):
            raise OSError("read failure")
    with pytest.raises(JSONImportError, match="neizdevās nolasīt"):
        read_json_offers(Broken())
    from io import StringIO
    with pytest.raises(JSONImportError, match="binārajā"):
        read_json_offers(StringIO("[]"))


def test_json_repeated_import_updates_without_duplicates(inventory):
    rows = [json_record(inventory), json_record(inventory, supplier_sku="SUP-002")]
    assert import_json_offers(stream(rows), admin_id=inventory[0].id) == {"added": 2, "updated": 0}
    identifiers = [offer.id for offer in offers()]
    rows[0]["unit_price"] = "15.00"
    assert import_json_offers(stream(rows), admin_id=inventory[0].id) == {"added": 0, "updated": 2}
    assert [offer.id for offer in offers()] == identifiers
    assert offers()[0].unit_price == Decimal("15.00")
    assert all(offer.data_source == "JSON" for offer in offers())


def test_later_unknown_product_keeps_old_price_and_no_partial_insert(inventory):
    import_json_offers(stream([json_record(inventory)]), admin_id=inventory[0].id)
    with pytest.raises(OfferImportError) as failure:
        import_json_offers(stream([json_record(inventory, unit_price="99.00"),
                                  json_record(inventory, supplier_sku="NEW", product_sku="MISSING")]),
                           admin_id=inventory[0].id)
    assert failure.value.row == 2 and failure.value.field == "product_sku"
    assert len(offers()) == 1 and offers()[0].unit_price == Decimal("10.25")


@pytest.fixture
def upload_client(database_app):
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0
    client = database_app.test_client()
    client.post("/auth/login", data={"email": ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD})
    response = client.get("/admin/import/json")
    assert response.status_code == 200
    with client.session_transaction() as session:
        token = session["product_csrf_token"]
    return client, token


def test_sample_upload_download_repetition_and_existing_design(upload_client):
    client, token = upload_client
    page = client.get("/admin/import/json").get_data(as_text=True)
    assert 'aria-current="page">Imports' in page and 'class="form-panel"' in page
    assert page.count("<footer") == 1
    download = client.get("/admin/import/json/sample")
    assert download.status_code == 200 and "attachment" in download.headers["Content-Disposition"]
    assert read_json_offers(BytesIO(download.data)) == read_json_offers(BytesIO(SAMPLE_FILE.read_bytes()))
    count = len(offers())
    for _ in range(2):
        response = client.post("/admin/import/json", data={"csrf_token": token,
                              "file": (BytesIO(download.data), "offers.json")}, follow_redirects=True)
        assert response.status_code == 200
        assert "Pievienoti: 0; atjaunināti: 2." in response.get_data(as_text=True)
    assert len(offers()) == count


@pytest.mark.parametrize("payload", [b"invalid", b'[{}]', b'{"offers": []}'])
def test_upload_errors_show_reason_and_preserve_database(upload_client, payload):
    client, token = upload_client
    before = [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()]
    response = client.post("/admin/import/json", data={"csrf_token": token,
                          "file": (BytesIO(payload), "invalid.json")})
    assert response.status_code == 422
    assert 'role="alert"' in response.get_data(as_text=True)
    assert [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()] == before


def test_upload_failure_contains_record_field_and_escaped_message(upload_client):
    client, token = upload_client
    rows = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    rows[1]["<script>alert(1)</script>"] = 1
    response = client.post("/admin/import/json", data={"csrf_token": token,
                          "file": (stream(rows), "bad.json")})
    html = response.get_data(as_text=True)
    assert response.status_code == 422 and "Rinda 2:" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_missing_wrong_extension_oversized_and_csrf(upload_client):
    client, token = upload_client
    assert client.post("/admin/import/json", data={"csrf_token": token}).status_code == 422
    assert client.post("/admin/import/json", data={"csrf_token": token,
        "file": (BytesIO(b"[]"), "file.csv")}).status_code == 422
    assert client.post("/admin/import/json", data={"csrf_token": token,
        "file": (BytesIO(b" " * (MAX_FILE_BYTES + 65537)), "large.json")}).status_code == 413
    for invalid in (None, "wrong", "ā"):
        assert client.post("/admin/import/json", data={"csrf_token": invalid or "",
            "file": (BytesIO(b"[]"), "file.json")}).status_code == 400


def test_upload_commit_failure_reports_error_and_no_changes(upload_client, monkeypatch):
    client, token = upload_client
    before = [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()]
    def fail_commit():
        db.session.flush()
        raise IntegrityError("commit", {}, Exception("simulated failure"))
    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        response = client.post("/admin/import/json", data={"csrf_token": token,
            "file": (BytesIO(SAMPLE_FILE.read_bytes()), "file.json")})
    assert response.status_code == 422 and "visas importa izmaiņas atceltas" in response.get_data(as_text=True)
    assert [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()] == before


def test_import_and_download_require_admin(database_app):
    client = database_app.test_client()
    for path in ("/admin/import/json", "/admin/import/json/sample"):
        assert client.get(path).status_code == 302
    assert client.post("/admin/import/json").status_code == 302
    database_app.test_cli_runner().invoke(args=["seed-demo"])
    client.post("/auth/login", data={"email": USER_EMAIL, "password": DEFAULT_USER_PASSWORD})
    assert client.get("/admin/import/json").status_code == 403
    assert client.get("/admin/import/json/sample").status_code == 403
    assert client.post("/admin/import/json").status_code == 403
