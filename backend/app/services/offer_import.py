"""Atomic persistence for records supplied by CSV and JSON adapters."""

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
import re

from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Offer, Product, Supplier, User


SOURCES = {"CSV", "JSON"}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 10000
REQUIRED_FIELDS = ("product_sku", "supplier_sku", "currency", "unit_price", "vat_included",
                   "min_order_qty", "stock_qty", "delivery_days")
FIELDS = {"product_sku", "supplier_sku", "supplier_id", "supplier_name", "currency",
          "unit_price", "vat_included", "vat_rate", "min_order_qty", "stock_qty",
          "delivery_days", "delivery_price", "is_active"}


class OfferImportError(ValueError):
    """Safe user-facing failure; row is one-based and field identifies bad input."""

    def __init__(self, message, *, row=None, field=None):
        self.row, self.field = row, field
        super().__init__((f"Rinda {row}: " if row is not None else "") + message)


def _text(value, field, row, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise OfferImportError(f"Lauks {field} ir obligāts teksts līdz {limit} rakstzīmēm.",
                              row=row, field=field)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise OfferImportError(f"Lauks {field} satur vadības rakstzīmes.", row=row, field=field)
    return value.strip()


def _integer(value, field, row, minimum=0, maximum=2147483647):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise OfferImportError(f"Laukā {field} jānorāda vesels skaitlis.", row=row, field=field)
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,19}", text) or not minimum <= int(text) <= maximum:
        raise OfferImportError(f"Laukā {field} jānorāda skaitlis no {minimum} līdz {maximum}.",
                              row=row, field=field)
    return int(text)


def _decimal(value, field, row, *, rate=False):
    # Importā pieņemam gan komatu, gan punktu; naudu apstrādājam ar Decimal.
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise OfferImportError(f"Laukā {field} jānorāda skaitliska vērtība.", row=row, field=field)
    text = str(value).strip().replace(",", ".")
    digits = 3 if rate else 8
    if not re.fullmatch(rf"[0-9]{{1,{digits}}}(?:\.[0-9]{{1,2}})?", text):
        raise OfferImportError(f"Lauks {field}: nenegatīvs skaitlis ar ne vairāk kā divām zīmēm aiz komata.",
                              row=row, field=field)
    number = Decimal(text)
    if rate and number > 100:
        raise OfferImportError("PVN likmei jābūt no 0 līdz 100 %.", row=row, field=field)
    return number


def _boolean(value, field, row):
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, int)):
        text = str(value).strip().lower()
        if text in {"true", "1"}:
            return True
        if text in {"false", "0"}:
            return False
    raise OfferImportError(f"Laukā {field} jānorāda true/false vai 1/0.", row=row, field=field)


def validate_import_record(record, row):
    """Validate and normalize one adapter record without accessing the database."""
    if not isinstance(record, Mapping):
        raise OfferImportError("Ierakstam jābūt lauku un vērtību kopai.", row=row)
    if set(record) - FIELDS:
        # Nezināmus laukus noraidām, lai kļūdains kolonnu nosaukums nepaliktu nepamanīts.
        raise OfferImportError("Ierakstā ir neatbalstīti lauki.", row=row)
    data = {field: _text(record.get(field), field, row, 100)
            for field in ("product_sku", "supplier_sku")}
    if record.get("currency") != "EUR":
        raise OfferImportError("Atļauta tikai EUR valūta.", row=row, field="currency")
    data["currency"] = "EUR"
    data["unit_price"] = _decimal(record.get("unit_price"), "unit_price", row)
    data["vat_included"] = _boolean(record.get("vat_included"), "vat_included", row)
    rate = record.get("vat_rate")
    if rate is None or rate == "":
        if not data["vat_included"]:
            raise OfferImportError("Cenai bez PVN jānorāda PVN likme.", row=row, field="vat_rate")
        data["vat_rate"] = None
    else:
        data["vat_rate"] = _decimal(rate, "vat_rate", row, rate=True)
    for field in ("stock_qty", "min_order_qty", "delivery_days"):
        data[field] = _integer(record.get(field), field, row, minimum=1 if field == "min_order_qty" else 0)
    if "delivery_price" in record:
        data["delivery_price"] = _decimal(record["delivery_price"], "delivery_price", row)
    if "is_active" in record:
        data["is_active"] = _boolean(record["is_active"], "is_active", row)
    if "supplier_id" in record:
        data["supplier_id"] = _integer(record["supplier_id"], "supplier_id", row,
                                       minimum=1, maximum=9223372036854775807)
    if "supplier_name" in record:
        data["supplier_name"] = " ".join(_text(record["supplier_name"], "supplier_name", row, 255).split())
    if "supplier_id" not in data and "supplier_name" not in data:
        raise OfferImportError("Norādiet supplier_id vai supplier_name.", row=row, field="supplier_id")
    return data


def save_imported_offers(records, *, source, admin_id):
    """Validate and commit one complete batch, returning added/updated counts.

    Requires a clean application session; source/admin_id come from the adapter,
    never from an imported row. Existing products and suppliers are required.
    """
    session = db.session
    if session.new or session.dirty or session.deleted:
        raise OfferImportError("Pirms importa pabeidziet citas nesaglabātās izmaiņas.", field="transaction")
    try:
        if not isinstance(source, str) or source not in SOURCES:
            raise OfferImportError("Importa avotam jābūt CSV vai JSON.", field="source")
        actor_id = _integer(admin_id, "admin_id", None, minimum=1, maximum=9223372036854775807)
        actor = session.get(User, actor_id)
        if actor is None or actor.role != "admin" or not actor.is_active:
            raise OfferImportError("Importu drīkst saglabāt tikai aktīvs administrators.", field="admin_id")
        if isinstance(records, (str, bytes, Mapping)):
            raise OfferImportError("Importam jānodod ierakstu saraksts, nevis fails vai JSON teksts.")
        prepared = []
        # Vispirms pārbaudām visu ievadi; tikai pēc tam sākam mainīt piedāvājumus.
        identities = set()
        for row, record in enumerate(records, 1):
            data = validate_import_record(record, row)
            supplier = (session.get(Supplier, data["supplier_id"]) if "supplier_id" in data else
                        session.scalar(db.select(Supplier).where(
                            Supplier.name_key == data["supplier_name"].casefold())))
            if supplier is None or not supplier.is_active:
                raise OfferImportError("Piegādātājs neeksistē vai nav aktīvs.", row=row, field="supplier_id")
            if "supplier_name" in data and supplier.name_key != data["supplier_name"].casefold():
                raise OfferImportError("Piegādātāja ID un nosaukums nesakrīt.", row=row, field="supplier_name")
            product = session.scalar(db.select(Product).where(Product.sku == data["product_sku"]))
            if product is None or not product.is_active:
                raise OfferImportError("Preces kods neeksistē vai prece nav aktīva.", row=row, field="product_sku")
            identity = (supplier.id, data["supplier_sku"].casefold())
            if identity in identities:
                raise OfferImportError("Importā atkārtojas piegādātājs un tā preces kods.", row=row,
                                      field="supplier_sku")
            identities.add(identity)
            prepared.append((row, data, supplier.id, product.id))

        # Piegādātājus bloķējam vienādā secībā, samazinot savstarpējas bloķēšanās risku.
        suppliers = {supplier.id: supplier for supplier in session.scalars(
            db.select(Supplier).where(Supplier.id.in_(sorted({item[2] for item in prepared})))
            .order_by(Supplier.id).with_for_update().execution_options(populate_existing=True))}
        added = updated = 0
        activated_pairs = set()
        updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for row, data, supplier_id, product_id in prepared:
            supplier = suppliers.get(supplier_id)
            if supplier is None or not supplier.is_active:
                raise OfferImportError("Piegādātājs vairs nav aktīvs.", row=row, field="supplier_id")
            matches = session.scalars(db.select(Offer).where(
                Offer.supplier_sku == data["supplier_sku"],
                db.or_(Offer.supplier_id == supplier_id,
                       db.and_(Offer.supplier_id.is_(None), Offer.supplier_name == supplier.name)))
                .with_for_update().execution_options(populate_existing=True)).all()
            if len(matches) > 1:
                raise OfferImportError("Datubāzē ir vairāki piedāvājumi ar šo piegādātāju un kodu.",
                                      row=row, field="supplier_sku")
            offer = matches[0] if matches else None
            if offer is not None and offer.product_id != product_id:
                raise OfferImportError("Piegādātāja kods jau piesaistīts citai precei.", row=row, field="product_sku")
            # A supplier may have multiple historical/inactive offers, but only one
            # active price for a given catalog product. Different supplier SKUs must
            # not silently create duplicate live comparison rows.
            will_be_active = data.get("is_active", offer.is_active if offer is not None else True)
            if will_be_active:
                pair = (supplier_id, product_id)
                if pair in activated_pairs:
                    raise OfferImportError(
                        "Vienam piegādātājam nevar importēt divus aktīvus piedāvājumus par vienu preci.",
                        row=row, field="product_sku")
                conflict_query = db.select(Offer.id).where(
                    Offer.product_id == product_id, Offer.is_active.is_(True),
                    db.or_(Offer.supplier_id == supplier_id,
                           db.and_(Offer.supplier_id.is_(None),
                                   Offer.supplier_name == supplier.name)))
                if offer is not None:
                    conflict_query = conflict_query.where(Offer.id != offer.id)
                if session.scalar(conflict_query.limit(1)) is not None:
                    raise OfferImportError(
                        "Šim piegādātājam jau ir aktīvs piedāvājums par šo preci. "
                        "Atjauniniet esošo piegādātāja kodu vai deaktivizējiet dublikātu.",
                        row=row, field="product_sku")
                activated_pairs.add(pair)
            if offer is None:
                offer = Offer(product_id=product_id, created_by_admin_id=actor_id)
                session.add(offer)
                added += 1
            else:
                updated += 1
            offer.supplier_id, offer.supplier_name = supplier_id, supplier.name
            for field in ("supplier_sku", "currency", "unit_price", "vat_included", "vat_rate",
                          "min_order_qty", "delivery_days"):
                setattr(offer, field, data[field])
            offer.imported_stock_qty = data["stock_qty"]
            # Jaunais piegādātāja atlikums nedrīkst atjaunot jau rezervētās vienības.
            offer.stock_qty = max(0, data["stock_qty"] - (offer.allocated_qty or 0))
            offer.delivery_price = data.get("delivery_price", supplier.delivery_price)
            if "is_active" in data:
                offer.is_active = data["is_active"]
            offer.data_source, offer.updated_at = source, updated_at
        session.commit()
        return {"added": added, "updated": updated}
    except OfferImportError:
        # Jebkura importa kļūda atceļ visu partiju, neatstājot daļēji saglabātus datus.
        session.rollback()
        raise
    except SQLAlchemyError as error:
        session.rollback()
        raise OfferImportError("Importu neizdevās saglabāt; visas importa izmaiņas atceltas.") from error
    except Exception as error:
        session.rollback()
        raise OfferImportError("Importa datus neizdevās nolasīt; visas importa izmaiņas atceltas.") from error
