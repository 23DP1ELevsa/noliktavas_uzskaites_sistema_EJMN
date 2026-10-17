from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import MetaData, Table, select, func
from flask_migrate import downgrade, upgrade
from sqlalchemy.exc import IntegrityError

from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Category, CompanyProfile, Offer, Order, OrderItem, Product, Supplier, User
from backend.app.services.offer_import import OfferImportError, save_imported_offers
from conftest import MIGRATIONS


@pytest.fixture
def inventory(database_app):
    admin = User(email="import@example.test", full_name="Import admin", role="admin", password_hash="hash")
    buyer = User(email="customer@example.test", full_name="Buyer", password_hash="hash")
    category = Category(name="Importa preces")
    products = [Product(category=category, sku=f"IMPORT-{i}", name=f"Prece {i}") for i in (1, 2)]
    suppliers = [Supplier(name=f"Piegādātājs {i}", name_key=f"piegādātājs {i}",
                          delivery_price=Decimal("3.50")) for i in (1, 2)]
    db.session.add_all([admin, buyer, *products, *suppliers])
    db.session.commit()
    return admin, buyer, products, suppliers


def record(inventory, **changes):
    _, _, products, suppliers = inventory
    data = dict(product_sku=products[0].sku, supplier_id=suppliers[0].id,
                supplier_sku="SUP-001", currency="EUR", unit_price="10.25",
                vat_included=False, vat_rate="21.00", min_order_qty="2",
                stock_qty="15", delivery_days="3")
    return {**data, **changes}


def save(inventory, rows, source="CSV"):
    return save_imported_offers(rows, source=source, admin_id=inventory[0].id)


def offers():
    return db.session.scalars(db.select(Offer).order_by(Offer.id)).all()


@pytest.mark.parametrize("source", ["CSV", "JSON", "API"])
def test_add_repeat_and_update_use_one_identity_and_success_timestamp(inventory, source):
    admin, _, products, suppliers = inventory
    assert save(inventory, [record(inventory)], source) == {"added": 1, "updated": 0}
    offer = offers()[0]
    identifier = offer.id
    assert offer.product_id == products[0].id and offer.supplier_id == suppliers[0].id
    assert offer.unit_price == Decimal("10.25") and offer.vat_rate == Decimal("21.00")
    assert offer.delivery_price == Decimal("3.50") and offer.data_source == source
    assert offer.created_by_admin_id == admin.id and offer.updated_at is not None
    offer.updated_at = datetime(2000, 1, 1)
    db.session.commit()
    assert save(inventory, [record(inventory)], source) == {"added": 0, "updated": 1}
    assert offers()[0].id == identifier and offers()[0].updated_at > datetime(2000, 1, 1)
    assert save(inventory, [record(inventory, unit_price="12,50", stock_qty=7, delivery_price="0.00")], "API") == {
        "added": 0, "updated": 1}
    assert len(offers()) == 1
    assert offers()[0].unit_price == Decimal("12.50") and offers()[0].stock_qty == 7
    assert offers()[0].delivery_price == Decimal("0.00") and offers()[0].data_source == "API"


def test_same_code_from_different_suppliers_and_multiple_codes_are_distinct(inventory):
    rows = [record(inventory), record(inventory, supplier_id=inventory[3][1].id),
            record(inventory, supplier_sku="SUP-002")]
    assert save(inventory, rows) == {"added": 3, "updated": 0}
    assert save(inventory, rows, "JSON") == {"added": 0, "updated": 3}
    assert len(offers()) == 3


@pytest.mark.parametrize("field,value", [
    ("product_sku", ""), ("product_sku", "missing"), ("product_sku", "x" * 101),
    ("supplier_id", 0), ("supplier_id", True), ("supplier_id", 999999),
    ("supplier_sku", ""), ("supplier_sku", "x" * 101), ("supplier_sku", "A\nB"),
    ("currency", "USD"), ("currency", "eur"), ("currency", None),
    ("unit_price", "-1"), ("unit_price", "NaN"), ("unit_price", "Infinity"),
    ("unit_price", "1e2"), ("unit_price", "0.001"), ("unit_price", "100000000"),
    ("unit_price", True), ("unit_price", None), ("unit_price", "9" * 500),
    ("vat_rate", ""), ("vat_rate", "100.01"), ("vat_rate", "-1"), ("vat_rate", "21.001"),
    ("vat_included", "yes"), ("vat_included", None), ("stock_qty", -1), ("stock_qty", "1.5"),
    ("stock_qty", 2147483648), ("stock_qty", True), ("min_order_qty", 0),
    ("delivery_days", "1e2"), ("delivery_price", "-0.01"), ("is_active", "maybe"),
])
def test_bad_later_row_saves_nothing(inventory, field, value):
    first = record(inventory)
    second = record(inventory, **{"supplier_sku": "SUP-002", field: value})
    with pytest.raises(OfferImportError) as failure:
        save(inventory, [first, second])
    assert failure.value.row == 2 and failure.value.field == field
    assert offers() == []


@pytest.mark.parametrize("field", ["currency", "unit_price", "vat_included", "min_order_qty", "stock_qty", "delivery_days"])
def test_missing_required_field_is_rejected(inventory, field):
    data = record(inventory)
    del data[field]
    with pytest.raises(OfferImportError) as failure:
        save(inventory, [data])
    assert failure.value.field == field and offers() == []


def test_resolve_supplier_name_and_reject_id_name_mismatch(inventory):
    data = record(inventory, supplier_name="  PIEGĀDĀTĀJS   1 ")
    del data["supplier_id"]
    assert save(inventory, [data]) == {"added": 1, "updated": 0}
    with pytest.raises(OfferImportError) as failure:
        save(inventory, [record(inventory, supplier_name=inventory[3][1].name)])
    assert failure.value.field == "supplier_name" and len(offers()) == 1


@pytest.mark.parametrize("model", ["product", "supplier"])
def test_inactive_catalog_entity_is_rejected(inventory, model):
    (inventory[2][0] if model == "product" else inventory[3][0]).is_active = False
    db.session.commit()
    with pytest.raises(OfferImportError):
        save(inventory, [record(inventory)])
    assert offers() == []


@pytest.mark.parametrize("actor", ["missing", "buyer", "inactive"])
def test_active_admin_is_required(inventory, actor):
    admin = inventory[0]
    identifier = 99999 if actor == "missing" else inventory[1].id if actor == "buyer" else admin.id
    if actor == "inactive":
        admin.is_active = False
        db.session.commit()
    with pytest.raises(OfferImportError) as failure:
        save_imported_offers([record(inventory)], source="CSV", admin_id=identifier)
    assert failure.value.field == "admin_id" and offers() == []


def test_duplicate_batch_identity_is_rejected_before_writes(inventory):
    with pytest.raises(OfferImportError) as failure:
        save(inventory, [record(inventory), record(inventory, unit_price="12.50")])
    assert failure.value.row == 2 and failure.value.field == "supplier_sku"
    assert offers() == []


def test_product_code_cannot_reassign_offer_and_prior_changes_roll_back(inventory):
    save(inventory, [record(inventory)])
    offer = offers()[0]
    offer.updated_at = datetime(2000, 1, 1)
    db.session.commit()
    with pytest.raises(OfferImportError):
        save(inventory, [record(inventory, supplier_sku="NEW"),
                         record(inventory, product_sku=inventory[2][1].sku, unit_price="99")])
    assert len(offers()) == 1 and offers()[0].unit_price == Decimal("10.25")
    assert offers()[0].updated_at == datetime(2000, 1, 1)


def test_commit_failure_rolls_back_update_insert_and_timestamp(inventory, monkeypatch):
    save(inventory, [record(inventory)])
    offers()[0].updated_at = datetime(2000, 1, 1)
    db.session.commit()

    def fail_commit():
        db.session.flush()
        raise IntegrityError("commit", {}, Exception("simulated database failure"))

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        with pytest.raises(OfferImportError, match="visas importa izmaiņas atceltas"):
            save(inventory, [record(inventory, unit_price="99"), record(inventory, supplier_sku="NEW")])
    assert len(offers()) == 1 and offers()[0].unit_price == Decimal("10.25")
    assert offers()[0].updated_at == datetime(2000, 1, 1)
    assert save(inventory, [record(inventory)]) == {"added": 0, "updated": 1}


def test_existing_author_and_inactive_state_preserved_without_explicit_activation(inventory):
    save(inventory, [record(inventory, is_active=False)])
    identifier, author = offers()[0].id, offers()[0].created_by_admin_id
    other = User(email="other-admin@example.test", full_name="Admin 2", role="admin", password_hash="hash")
    db.session.add(other)
    db.session.commit()
    assert save_imported_offers([record(inventory)], source="API", admin_id=other.id) == {"added": 0, "updated": 1}
    offer = offers()[0]
    assert offer.id == identifier and offer.created_by_admin_id == author and not offer.is_active
    save(inventory, [record(inventory, is_active="true")])
    assert offers()[0].is_active


def test_legacy_offer_is_attached_not_duplicated(inventory):
    admin, _, products, suppliers = inventory
    old = Offer(product_id=products[0].id, created_by_admin_id=admin.id, supplier_name=suppliers[0].name,
                supplier_sku="SUP-001", unit_price=Decimal("1.00"), vat_included=True)
    db.session.add(old)
    db.session.commit()
    identifier = old.id
    assert save(inventory, [record(inventory)]) == {"added": 0, "updated": 1}
    assert offers()[0].id == identifier and offers()[0].supplier_id == suppliers[0].id


def test_ambiguous_legacy_records_are_rejected(inventory):
    admin, _, products, suppliers = inventory
    for _ in range(2):
        db.session.add(Offer(product_id=products[0].id, created_by_admin_id=admin.id,
                             supplier_name=suppliers[0].name, supplier_sku="SUP-001",
                             unit_price=Decimal("1.00"), vat_included=True))
    db.session.commit()
    with pytest.raises(OfferImportError, match="vairāki piedāvājumi"):
        save(inventory, [record(inventory)])
    assert len(offers()) == 2 and all(offer.supplier_id is None for offer in offers())


@pytest.mark.parametrize("data", [None, "[]", {}, ["row"], [123]])
def test_malformed_input_is_safe(inventory, data):
    with pytest.raises(OfferImportError):
        save(inventory, data)
    assert offers() == []


def test_empty_batch_and_invalid_source(inventory):
    assert save(inventory, []) == {"added": 0, "updated": 0}
    with pytest.raises(OfferImportError):
        save(inventory, [record(inventory)], source="manual")
    assert offers() == []


def test_iterator_failure_and_untrusted_metadata_are_rejected(inventory):
    def broken():
        yield record(inventory)
        raise OSError("download interrupted")
    with pytest.raises(OfferImportError):
        save(inventory, broken())
    with pytest.raises(OfferImportError):
        save(inventory, [record(inventory, created_by_admin_id=inventory[1].id)])
    assert offers() == []


def test_import_does_not_commit_unrelated_pending_changes(inventory):
    data, admin_id = record(inventory), inventory[0].id
    inventory[2][0].name = "Unsaved edit"
    with pytest.raises(OfferImportError) as failure:
        save_imported_offers([data], source="CSV", admin_id=admin_id)
    assert failure.value.field == "transaction"
    assert inventory[2][0].name == "Unsaved edit"
    db.session.rollback()
    assert inventory[2][0].name == "Prece 1" and offers() == []


def test_database_unique_index_prevents_duplicate_offer_identity(inventory):
    save(inventory, [record(inventory)])
    original = offers()[0]
    db.session.add(Offer(product_id=original.product_id, created_by_admin_id=original.created_by_admin_id,
                         supplier_id=original.supplier_id, supplier_name=original.supplier_name,
                         supplier_sku=original.supplier_sku, unit_price=1, vat_included=True))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert len(offers()) == 1


def test_migration_and_import_preserve_cart_and_order_history(inventory):
    save(inventory, [record(inventory)])
    _, buyer, _, _ = inventory
    offer = offers()[0]
    product_name = offer.product.name
    profile = CompanyProfile(user=buyer, company_name="SIA Test", registration_no="123", address="Rīga")
    item = CartItem(cart=Cart(user=buyer), offer=offer, quantity=2)
    order = Order(user=buyer, company_profile=profile, total_amount=Decimal("24.00"))
    snapshot = OrderItem(order=order, offer=offer, product_name=product_name,
                         supplier_name=offer.supplier_name, unit_price=offer.unit_price,
                         quantity=2, delivery_price=offer.delivery_price, line_total=Decimal("24.00"),
                         vat_included=offer.vat_included, vat_rate=offer.vat_rate)
    db.session.add_all([item, snapshot])
    db.session.commit()
    identifiers = item.id, snapshot.id, offer.id
    db.session.rollback()  # Release MySQL metadata locks before separate DDL connection.
    downgrade(directory=MIGRATIONS, revision="0006_order_notifications")
    upgrade(directory=MIGRATIONS)
    db.session.expire_all()
    save(inventory, [record(inventory, unit_price="20.00")])
    assert db.session.get(CartItem, identifiers[0]).offer_id == identifiers[2]
    saved = db.session.get(OrderItem, identifiers[1])
    assert saved.offer_id == identifiers[2] and saved.unit_price == Decimal("10.25")
    assert saved.line_total == Decimal("24.00")
    assert offers()[0].unit_price == Decimal("20.00")


def test_migration_rejects_existing_duplicates_without_removing_them(inventory, database_app):
    save(inventory, [record(inventory)])
    original = offers()[0]
    duplicate_values = dict(product_id=original.product_id, created_by_admin_id=original.created_by_admin_id,
                            supplier_id=original.supplier_id, supplier_name=original.supplier_name,
                            supplier_sku=original.supplier_sku, unit_price=1, vat_included=True)
    db.session.rollback()
    downgrade(directory=MIGRATIONS, revision="0006_order_notifications")
    # Use the historical table shape, not the current ORM's newer columns.
    historical = Table("offers", MetaData(), autoload_with=db.engine)
    duplicate_id = db.session.execute(historical.insert().values(**duplicate_values)).inserted_primary_key[0]
    db.session.commit()
    result = database_app.test_cli_runner().invoke(args=["db", "upgrade"])
    assert result.exit_code == 1 and "Duplicate supplier offer codes" in result.output
    assert db.session.scalar(select(func.count()).select_from(historical)) == 2
    db.session.execute(historical.delete().where(historical.c.id == duplicate_id))
    db.session.commit()
    upgrade(directory=MIGRATIONS)
