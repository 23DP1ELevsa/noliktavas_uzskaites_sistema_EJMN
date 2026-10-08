"""Public catalogue queries and validation of optional search filters."""

from dataclasses import dataclass
from decimal import Decimal
import re

from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import Offer, Product


class CatalogFilterError(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class CatalogFilters:
    q: str = ""
    category_id: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    supplier: str = ""
    in_stock: bool | None = None

    @classmethod
    def from_args(cls, args):
        values = {}
        for field in cls.__dataclass_fields__:
            if len(args.getlist(field)) > 1:
                raise CatalogFilterError(field, "Katru filtru drīkst norādīt tikai vienu reizi.")
            values[field] = args.get(field, "").strip()

        for field in ("q", "supplier"):
            if len(values[field]) > 255:
                raise CatalogFilterError(field, "Teksts nedrīkst pārsniegt 255 rakstzīmes.")

        category_id = None
        if values["category_id"]:
            value = values["category_id"]
            if not re.fullmatch(r"[0-9]{1,20}", value) or not 0 < int(value) <= 18446744073709551615:
                raise CatalogFilterError("category_id", "Norādiet derīgu pozitīvu kategorijas ID.")
            category_id = int(value)

        prices = {}
        for field in ("min_price", "max_price"):
            value = values[field]
            if value and not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,2})?", value):
                raise CatalogFilterError(
                    field, "Cena jānorāda no 0 līdz 99999999.99, ar ne vairāk kā divām zīmēm aiz punkta."
                )
            prices[field] = Decimal(value) if value else None
        if (prices["min_price"] is not None and prices["max_price"] is not None
                and prices["min_price"] > prices["max_price"]):
            raise CatalogFilterError("max_price", "Maksimālā cena nedrīkst būt mazāka par minimālo cenu.")

        in_stock = None
        value = values["in_stock"].lower()
        if value:
            if value not in {"true", "false", "1", "0"}:
                raise CatalogFilterError("in_stock", "Pieejamībai norādiet true, false, 1 vai 0.")
            in_stock = value in {"true", "1"}

        return cls(q=values["q"], category_id=category_id, supplier=values["supplier"],
                   in_stock=in_stock, **prices)


def search_catalog(filters):
    offer_conditions = [Offer.is_active.is_(True)]
    if filters.min_price is not None:
        offer_conditions.append(Offer.unit_price >= filters.min_price)
    if filters.max_price is not None:
        offer_conditions.append(Offer.unit_price <= filters.max_price)
    if filters.supplier:
        offer_conditions.append(func.lower(Offer.supplier_name) == filters.supplier.lower())

    available = Offer.stock_qty >= Offer.min_order_qty
    if filters.in_stock is True:
        offer_conditions.append(available)

    query = db.select(Product).where(Product.is_active.is_(True))
    if filters.q:
        # Treat LIKE wildcards in user input as literal characters.
        query = query.where(Product.name.icontains(filters.q, autoescape=True))
    if filters.category_id is not None:
        # SQLite's integer range is smaller than MySQL's BIGINT UNSIGNED.
        if db.engine.dialect.name == "sqlite" and filters.category_id > 9223372036854775807:
            return []
        query = query.where(Product.category_id == filters.category_id)

    # All offer filters must match ONE offer, not different suppliers' offers.
    if (filters.min_price is not None or filters.max_price is not None
            or filters.supplier or filters.in_stock is True):
        query = query.where(Product.offers.any(and_(*offer_conditions)))
    if filters.in_stock is False:
        query = query.where(~Product.offers.any(and_(*offer_conditions, available)))

    query = query.options(
        joinedload(Product.category),
        selectinload(Product.offers.and_(*offer_conditions)),
    ).order_by(Product.id).execution_options(populate_existing=True)
    return [_serialize_product(product) for product in db.session.scalars(query)]


def _serialize_product(product):
    offers = sorted(product.offers, key=lambda offer: (offer.unit_price, offer.id))
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "category_id": product.category_id,
        "category": product.category.name,
        "brand": product.brand,
        "model": product.model,
        "description": product.description,
        "unit": product.unit,
        "active": product.is_active,
        # Keep the existing API's numeric price; no arithmetic is done in float.
        "price": float(offers[0].unit_price) if offers else None,
        "currency": "EUR",
        "available": any(offer.stock_qty >= offer.min_order_qty for offer in offers),
        "offer_count": len(offers),
        "offers": [{
            "id": offer.id,
            "supplier_name": offer.supplier_name,
            "supplier_sku": offer.supplier_sku,
            "unit_price": float(offer.unit_price),
            "vat_included": offer.vat_included,
            "min_order_qty": offer.min_order_qty,
            "stock_qty": offer.stock_qty,
            "delivery_price": float(offer.delivery_price),
            "delivery_days": offer.delivery_days,
            "available": offer.stock_qty >= offer.min_order_qty,
            "updated_at": offer.updated_at.isoformat(timespec="seconds") + "Z",
        } for offer in offers],
    }
