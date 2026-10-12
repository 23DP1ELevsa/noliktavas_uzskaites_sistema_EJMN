"""Read UTF-8 JSON files and pass validated offers to shared persistence."""

from decimal import Decimal
import json
from pathlib import Path

from .offer_import import FIELDS, OfferImportError, save_imported_offers, validate_import_record


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 10000
SAMPLE_FILE = Path(__file__).resolve().parents[3] / "data_samples" / "offers_import.json"
REQUIRED_FIELDS = ("product_sku", "supplier_sku", "currency", "unit_price", "vat_included",
                   "min_order_qty", "stock_qty", "delivery_days")
TEXT_FIELDS = {"product_sku", "supplier_sku", "supplier_name", "currency"}
INTEGER_FIELDS = {"supplier_id", "min_order_qty", "stock_qty", "delivery_days"}
BOOLEAN_FIELDS = {"vat_included", "is_active"}
DECIMAL_FIELDS = {"unit_price", "vat_rate", "delivery_price"}


class JSONImportError(OfferImportError):
    """JSON format failure, with record/field or source line/column context."""

    def __init__(self, message, *, row=None, field=None, line=None, column=None):
        self.line, self.column = line, column
        super().__init__(message, row=row, field=field)


class _JSONObject(dict):
    def __init__(self, pairs):
        self.duplicates = []
        for key, value in pairs:
            if key in self:
                self.duplicates.append(key)
            self[key] = value


def _reject_constant(value):
    raise JSONImportError("JSON nedrīkst saturēt NaN vai Infinity. Izmantojiet galīgas skaitliskas vērtības.")


def read_json_offers(stream):
    """Read a binary file-like object, validating every row before any DB writes."""
    try:
        raw = stream.read(MAX_FILE_BYTES + 1)
    except (OSError, ValueError) as error:
        raise JSONImportError("JSON failu neizdevās nolasīt.") from error
    if not isinstance(raw, bytes):
        raise JSONImportError("JSON fails jāatver binārajā režīmā.")
    if len(raw) > MAX_FILE_BYTES:
        raise JSONImportError("JSON fails pārsniedz atļauto izmēru: 2 MiB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise JSONImportError("JSON failam jābūt UTF-8 kodējumā.") from error
    if not text.strip():
        raise JSONImportError("JSON fails ir tukšs.")
    try:
        records = json.loads(text, parse_float=Decimal, parse_constant=_reject_constant,
                             object_pairs_hook=_JSONObject)
    except json.JSONDecodeError as error:
        raise JSONImportError(f"JSON sintakses kļūda: faila rinda {error.lineno}, kolonna {error.colno}.",
                              line=error.lineno, column=error.colno) from error
    except (ValueError, RecursionError) as error:
        if isinstance(error, JSONImportError):
            raise
        raise JSONImportError("JSON struktūra vai skaitļa pieraksts nav derīgs.") from error
    if not isinstance(records, list):
        raise JSONImportError("JSON saknē jābūt piedāvājumu masīvam [...].")
    if len(records) > MAX_RECORDS:
        raise JSONImportError(f"Vienā failā atļauti ne vairāk kā {MAX_RECORDS} piedāvājumi.")
    result = []
    for row, record in enumerate(records, 1):
        if not isinstance(record, _JSONObject):
            raise JSONImportError("Piedāvājumam jābūt JSON objektam {...}.", row=row)
        if record.duplicates:
            raise JSONImportError("JSON objektā atkārtojas lauks.", row=row, field=record.duplicates[0])
        unknown = set(record) - FIELDS
        if unknown:
            raise JSONImportError("JSON ierakstā ir neatbalstīts lauks.", row=row, field=sorted(unknown)[0])
        for field in REQUIRED_FIELDS:
            if field not in record:
                raise JSONImportError(f"Trūkst obligātā lauka {field}.", row=row, field=field)
        for field, value in record.items():
            if field in TEXT_FIELDS:
                valid = isinstance(value, str)
                expected = "teksts"
            elif field in INTEGER_FIELDS:
                valid = type(value) is int
                expected = "vesels JSON skaitlis"
            elif field in BOOLEAN_FIELDS:
                valid = type(value) is bool
                expected = "JSON true vai false"
            else:
                valid = (field == "vat_rate" and value is None) or (
                    field in DECIMAL_FIELDS and not isinstance(value, bool)
                    and isinstance(value, (str, int, Decimal)))
                expected = "skaitlis vai decimālās vērtības teksts"
            if not valid:
                raise JSONImportError(f"Lauka {field} datu tips nav derīgs; nepieciešams {expected}.",
                                      row=row, field=field)
        try:
            result.append(validate_import_record(record, row))
        except OfferImportError as error:
            # Retain the common validation message and its record/field context.
            raise JSONImportError(str(error).removeprefix(f"Rinda {row}: "),
                                  row=error.row, field=error.field) from error
    return result


def import_json_offers(stream, *, admin_id):
    return save_imported_offers(read_json_offers(stream), source="JSON", admin_id=admin_id)
