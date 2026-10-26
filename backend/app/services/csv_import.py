"""Read CSV offers into the same normalized format as the JSON adapter."""

import csv
from io import StringIO
from pathlib import Path

from .offer_import import FIELDS, MAX_FILE_BYTES, MAX_RECORDS, REQUIRED_FIELDS, OfferImportError, save_imported_offers, validate_import_record


SAMPLE_FILE = Path(__file__).resolve().parents[3] / "data_samples" / "offers_import.csv"
OPTIONAL_FIELDS = FIELDS - set(REQUIRED_FIELDS)


class CSVImportError(OfferImportError):
    """CSV errors use physical file lines, including the header line."""


class CSVRecords(list):
    def __init__(self):
        super().__init__()
        self.lines = []


def read_csv_offers(stream):
    try:
        raw = stream.read(MAX_FILE_BYTES + 1)
    except (OSError, ValueError) as error:
        raise CSVImportError("CSV failu neizdevās nolasīt.") from error
    if not isinstance(raw, bytes):
        raise CSVImportError("CSV fails jāatver binārajā režīmā.")
    if len(raw) > MAX_FILE_BYTES:
        raise CSVImportError("CSV fails pārsniedz atļauto izmēru: 2 MiB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CSVImportError("CSV failam jābūt UTF-8 kodējumā.") from error
    if not text.strip():
        raise CSVImportError("CSV fails ir tukšs.")
    # Valid column names contain neither delimiter. Inspect the parsed headers
    # rather than guessing from numeric values or quoted supplier names.
    candidates = []
    for delimiter in (",", ";"):
        reader = csv.reader(StringIO(text, newline=""), delimiter=delimiter, strict=True)
        try:
            header = next(reader)
        except (StopIteration, csv.Error):
            continue
        candidates.append((sum(field.strip() in FIELDS for field in header), len(header), reader, header))
    if not candidates:
        raise CSVImportError("CSV galvene nav derīga.", row=1)
    _, _, reader, header = max(candidates, key=lambda candidate: candidate[:2])
    header = [field.strip() for field in header]
    if not header or any(not field for field in header):
        raise CSVImportError("CSV galvenē ir tukšs kolonnas nosaukums.", row=1)
    if len(header) != len(set(header)):
        raise CSVImportError("CSV galvenē atkārtojas kolonnas nosaukums.", row=1)
    unknown = set(header) - FIELDS
    if unknown:
        raise CSVImportError("CSV galvenē ir neatbalstīta kolonna.", row=1, field=sorted(unknown)[0])
    for field in REQUIRED_FIELDS:
        if field not in header:
            raise CSVImportError(f"Trūkst obligātās kolonnas {field}.", row=1, field=field)
    if not {"supplier_id", "supplier_name"}.intersection(header):
        raise CSVImportError("Galvenē nepieciešama supplier_id vai supplier_name kolonna.", row=1,
                             field="supplier_id")
    result = CSVRecords()
    while True:
        line = reader.line_num + 1
        try:
            values = next(reader)
        except StopIteration:
            break
        except csv.Error as error:
            raise CSVImportError("CSV struktūra nav derīga: pārbaudiet pēdiņas un šūnu izmērus.", row=line) from error
        if not values:  # Ignore entirely blank lines without losing their physical numbering.
            continue
        if len(values) != len(header):
            raise CSVImportError(f"Kolonnu skaits nesakrīt ar galveni: gaidītas {len(header)}, saņemtas {len(values)}.", row=line)
        if len(result) >= MAX_RECORDS:
            raise CSVImportError(f"Vienā failā atļauti ne vairāk kā {MAX_RECORDS} piedāvājumi.", row=line)
        data = {field: value.strip() for field, value in zip(header, values)
                if value.strip() or field not in OPTIONAL_FIELDS}
        try:
            normalized = validate_import_record(data, line)
        except OfferImportError as error:
            raise CSVImportError(str(error).removeprefix(f"Rinda {line}: "), row=line, field=error.field) from error
        result.append(normalized)
        result.lines.append(line)
    return result


def import_csv_offers(stream, *, admin_id):
    records = read_csv_offers(stream)
    try:
        return save_imported_offers(records, source="CSV", admin_id=admin_id)
    except OfferImportError as error:
        if error.row is None:
            raise
        line = records.lines[error.row - 1]
        raise CSVImportError(str(error).removeprefix(f"Rinda {error.row}: "),
                             row=line, field=error.field) from error
