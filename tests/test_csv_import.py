import csv
from decimal import Decimal
from io import BytesIO, StringIO

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.extensions import db
from backend.app.services.csv_import import CSVImportError, MAX_FILE_BYTES, MAX_RECORDS, SAMPLE_FILE, import_csv_offers, read_csv_offers
from backend.app.services.json_import import SAMPLE_FILE as JSON_SAMPLE_FILE, read_json_offers, import_json_offers
from backend.app.services.offer_import import OfferImportError
from test_offer_import import inventory, record, offers
from test_json_import import upload_client


def file_for(rows, *, delimiter=",", header=None):
    header = header if header is not None else list(rows[0])
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter=delimiter)
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(field, "") for field in header])
    return BytesIO(output.getvalue().encode("utf-8"))


@pytest.mark.parametrize("delimiter", [",", ";"])
def test_csv_converts_types_comma_prices_and_quoted_supplier(inventory, delimiter):
    data = record(inventory, unit_price="10,25", supplier_name="Piegādātājs, SIA", vat_included="false")
    del data["supplier_id"]
    parsed = read_csv_offers(file_for([data], delimiter=delimiter))
    assert parsed[0]["unit_price"] == Decimal("10.25")
    assert parsed[0]["vat_included"] is False and parsed[0]["stock_qty"] == 15
    assert parsed[0]["supplier_name"] == "Piegādātājs, SIA" and parsed.lines == [2]


def test_sample_and_json_have_identical_common_records():
    assert read_csv_offers(BytesIO(SAMPLE_FILE.read_bytes())) == read_json_offers(BytesIO(JSON_SAMPLE_FILE.read_bytes()))


def test_bom_crlf_and_reordered_columns(inventory):
    data = record(inventory)
    raw = file_for([data], header=list(reversed(data))).getvalue()
    parsed = read_csv_offers(BytesIO(b"\xef\xbb\xbf" + raw))
    assert parsed[0]["supplier_sku"] == "SUP-001" and parsed.lines == [2]


@pytest.mark.parametrize("field", ["product_sku", "supplier_sku", "currency", "unit_price",
                                  "vat_included", "min_order_qty", "stock_qty", "delivery_days"])
def test_missing_header_column_reports_header_line(inventory, field):
    data = record(inventory)
    with pytest.raises(CSVImportError) as failure:
        read_csv_offers(file_for([data], header=[key for key in data if key != field]))
    assert failure.value.row == 1 and failure.value.field == field


@pytest.mark.parametrize("kind", ["duplicate", "empty", "unknown", "supplier"])
def test_invalid_header_is_rejected(inventory, kind):
    data = record(inventory)
    header = list(data)
    if kind == "duplicate":
        header.append(header[0])
    elif kind == "empty":
        header.append("")
    elif kind == "unknown":
        header.append("data_source")
    else:
        header.remove("supplier_id")
    with pytest.raises(CSVImportError) as failure:
        read_csv_offers(file_for([data], header=header))
    assert failure.value.row == 1


@pytest.mark.parametrize("field,value", [
    ("unit_price", "NaN"), ("unit_price", "-1"), ("unit_price", "1e2"),
    ("unit_price", "1.001"), ("unit_price", ""), ("stock_qty", "2.5"),
    ("stock_qty", "2147483648"), ("min_order_qty", "0"), ("delivery_days", "-1"),
    ("vat_included", "yes"), ("vat_rate", "100.01"), ("vat_rate", ""),
    ("currency", "USD"), ("supplier_sku", ""), ("supplier_id", ""),
])
def test_invalid_later_row_reports_physical_line_and_field(inventory, field, value):
    rows = [record(inventory), record(inventory, **{"supplier_sku": "SUP-002", field: value})]
    with pytest.raises(CSVImportError) as failure:
        import_csv_offers(file_for(rows), admin_id=inventory[0].id)
    assert failure.value.row == 3 and failure.value.field == field
    assert offers() == []


@pytest.mark.parametrize("change", ["extra", "missing", "quote"])
def test_row_structure_must_match_header(inventory, change):
    raw = file_for([record(inventory)]).getvalue().decode()
    header, row = raw.splitlines()
    broken = row + ",extra" if change == "extra" else row.rsplit(",", 1)[0] if change == "missing" else '"unfinished'
    with pytest.raises(CSVImportError) as failure:
        read_csv_offers(BytesIO((header + "\n" + broken).encode()))
    assert failure.value.row == 2


def test_blank_lines_keep_physical_error_number_and_header_only_is_valid(inventory):
    raw = file_for([record(inventory), record(inventory, supplier_sku="SECOND", stock_qty="-1")]).getvalue().decode()
    header, first, second = raw.splitlines()
    with pytest.raises(CSVImportError) as failure:
        read_csv_offers(BytesIO((header + "\n\n" + first + "\n\n" + second).encode()))
    assert failure.value.row == 5
    assert read_csv_offers(BytesIO((header + "\n").encode())) == []


def test_multiline_quoted_cell_preserves_following_line_numbers(inventory):
    # A whitespace-only quoted optional field spans lines and is omitted.
    rows = [record(inventory, supplier_name="\n"), record(inventory, supplier_sku="SECOND", stock_qty="-1")]
    with pytest.raises(CSVImportError) as failure:
        read_csv_offers(file_for(rows))
    assert failure.value.row == 4 and failure.value.field == "stock_qty"


def test_blank_optional_cells_use_shared_defaults(inventory):
    data = record(inventory, supplier_name="", delivery_price="", is_active="")
    parsed = read_csv_offers(file_for([data]))[0]
    assert "supplier_name" not in parsed and "delivery_price" not in parsed and "is_active" not in parsed
    assert import_csv_offers(file_for([data]), admin_id=inventory[0].id) == {"added": 1, "updated": 0}
    assert offers()[0].delivery_price == Decimal("3.50") and offers()[0].is_active


@pytest.mark.parametrize("raw", [b"", b" \n", b"\xff\xfe", b"[{}]"])
def test_empty_wrong_encoding_and_non_csv_fail(raw):
    with pytest.raises(CSVImportError):
        read_csv_offers(BytesIO(raw))


def test_size_row_limit_and_io_failure(inventory):
    with pytest.raises(CSVImportError, match="izmēru"):
        read_csv_offers(BytesIO(b" " * (MAX_FILE_BYTES + 1)))
    data = record(inventory)
    with pytest.raises(CSVImportError, match="ne vairāk"):
        read_csv_offers(file_for([data] * (MAX_RECORDS + 1)))
    class Broken:
        def read(self, size):
            raise OSError("read error")
    with pytest.raises(CSVImportError, match="nolasīt"):
        read_csv_offers(Broken())
    with pytest.raises(CSVImportError, match="binārajā"):
        read_csv_offers(StringIO("header"))


def test_repeat_and_cross_format_import_do_not_duplicate(inventory):
    data = record(inventory)
    assert import_csv_offers(file_for([data]), admin_id=inventory[0].id) == {"added": 1, "updated": 0}
    identifier = offers()[0].id
    assert import_csv_offers(file_for([dict(data, unit_price="15.00")]), admin_id=inventory[0].id) == {"added": 0, "updated": 1}
    from test_json_import import stream, json_record
    assert import_json_offers(stream([json_record(inventory)]), admin_id=inventory[0].id) == {"added": 0, "updated": 1}
    assert len(offers()) == 1 and offers()[0].id == identifier


def test_common_error_is_remapped_to_file_line_and_entire_batch_is_rolled_back(inventory):
    import_csv_offers(file_for([record(inventory)]), admin_id=inventory[0].id)
    raw = file_for([record(inventory, unit_price="99"), record(inventory, supplier_sku="OTHER", product_sku="MISSING")]).getvalue()
    raw = raw.replace(b"\r\n", b"\r\n\r\n", 1)
    with pytest.raises(CSVImportError) as failure:
        import_csv_offers(BytesIO(raw), admin_id=inventory[0].id)
    assert failure.value.row == 4 and failure.value.field == "product_sku"
    assert len(offers()) == 1 and offers()[0].unit_price == Decimal("10.25")


def test_duplicate_identity_error_is_remapped(inventory):
    with pytest.raises(CSVImportError) as failure:
        import_csv_offers(file_for([record(inventory)] * 2), admin_id=inventory[0].id)
    assert failure.value.row == 3 and failure.value.field == "supplier_sku"


def test_upload_download_repetition_and_format_tabs(upload_client):
    client, token = upload_client
    html = client.get("/admin/import/csv").get_data(as_text=True)
    assert 'aria-current="page">CSV' in html and "Importēt CSV" in html
    assert 'class="form-panel"' in html and html.count("<footer") == 1
    download = client.get("/admin/import/csv/sample")
    assert download.status_code == 200 and "attachment" in download.headers["Content-Disposition"]
    assert download.data == SAMPLE_FILE.read_bytes()
    count = len(offers())
    for _ in range(2):
        response = client.post("/admin/import/csv", data={"csrf_token": token,
            "file": (BytesIO(download.data), "offers.CSV")}, follow_redirects=True)
        assert response.status_code == 200 and "Pievienoti: 0; atjaunināti: 2." in response.get_data(as_text=True)
    assert len(offers()) == count


def test_upload_bad_later_row_and_commit_failure_leave_data_unchanged(upload_client, monkeypatch):
    client, token = upload_client
    before = [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()]
    raw = SAMPLE_FILE.read_bytes().replace(b",6,7.50,5", b",-6,7.50,5")
    response = client.post("/admin/import/csv", data={"csrf_token": token,
        "file": (BytesIO(raw), "bad.csv")})
    assert response.status_code == 422 and "Rinda 3:" in response.get_data(as_text=True)
    assert "stock_qty" in response.get_data(as_text=True)
    def fail_commit():
        db.session.flush()
        raise IntegrityError("commit", {}, Exception("simulated failure"))
    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        response = client.post("/admin/import/csv", data={"csrf_token": token,
            "file": (BytesIO(SAMPLE_FILE.read_bytes()), "file.csv")})
    assert response.status_code == 422 and "visas importa izmaiņas atceltas" in response.get_data(as_text=True)
    assert [(offer.id, offer.unit_price, offer.updated_at) for offer in offers()] == before


def test_upload_rejects_missing_file_extension_size_and_csrf(upload_client):
    client, token = upload_client
    assert client.post("/admin/import/csv", data={"csrf_token": token}).status_code == 422
    assert client.post("/admin/import/csv", data={"csrf_token": token,
        "file": (BytesIO(b"[]"), "file.json")}).status_code == 422
    assert client.post("/admin/import/csv", data={"csrf_token": token,
        "file": (BytesIO(b" " * (MAX_FILE_BYTES + 65537)), "big.csv")}).status_code == 413
    assert client.post("/admin/import/csv", data={"file": (BytesIO(b""), "file.csv")}).status_code == 400


def test_csv_pages_require_admin(database_app):
    client = database_app.test_client()
    assert client.get("/admin/import/csv").status_code == 302
    assert client.get("/admin/import/csv/sample").status_code == 302
    assert client.post("/admin/import/csv").status_code == 302
    from backend.app.services.demo_data import USER_EMAIL, DEFAULT_USER_PASSWORD
    database_app.test_cli_runner().invoke(args=["seed-demo"])
    client.post("/auth/login", data={"email": USER_EMAIL, "password": DEFAULT_USER_PASSWORD})
    assert client.get("/admin/import/csv").status_code == 403
    assert client.get("/admin/import/csv/sample").status_code == 403
    assert client.post("/admin/import/csv").status_code == 403
