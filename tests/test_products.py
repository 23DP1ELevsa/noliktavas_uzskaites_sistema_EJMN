import pytest

from backend.app.extensions import db
from backend.app.models import Cart, CartItem, Category, Offer, Order, OrderItem, Product, User
from test_admin import admin_data, login_admin


@pytest.fixture
def inventory(database_app):
    client = database_app.test_client()
    login_admin(client)
    category = Category(name="Preču testa kategorija")
    db.session.add(category)
    db.session.commit()
    assert client.get("/admin/products/new").status_code == 200
    with client.session_transaction() as session:
        token = session["product_csrf_token"]
    data = {"name": "Testa prece", "sku": "test-001", "category_id": str(category.id),
            "description": "Preces apraksts", "image_url": "https://example.test/product.png",
            "unit": "gab.", "brand": "Test", "model": "One", "is_active": "1", "csrf_token": token}
    return client, category, data


def create_product(inventory):
    client, _, data = inventory
    response = client.post("/admin/products/new", data=data)
    assert response.status_code == 302
    product = db.session.scalar(db.select(Product))
    return product


def test_admin_product_create_read_update_and_delete(inventory):
    client, _, data = inventory
    product = create_product(inventory)
    identifier = product.id
    assert product.sku == "TEST-001"
    assert product.image_url == data["image_url"]
    assert client.get("/admin/products").status_code == 200
    detail = client.get(f"/admin/products/{identifier}").get_data(as_text=True)
    assert "Preces apraksts" in detail and "TEST-001" in detail
    assert client.get(f"/admin/products/{identifier}/edit").status_code == 200
    updated = dict(data, name="Atjaunota prece", sku="test-002", image_url="")
    assert client.post(f"/admin/products/{identifier}/edit", data=updated).status_code == 302
    db.session.refresh(product)
    assert product.name == "Atjaunota prece" and product.sku == "TEST-002"
    assert product.image_url is None
    # Reading the confirmation page must not perform a deletion.
    response = client.get(f"/admin/products/{identifier}/delete")
    assert response.status_code == 200 and db.session.get(Product, identifier) is not None
    assert "Apstiprināt dzēšanu" in response.get_data(as_text=True)
    response = client.post(f"/admin/products/{identifier}/delete", data={
        "csrf_token": data["csrf_token"], "confirmed": "1"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Prece veiksmīgi dzēsta." in response.get_data(as_text=True)
    assert db.session.get(Product, identifier) is None


@pytest.mark.parametrize("field,value", [
    ("name", " "), ("sku", ""), ("category_id", ""), ("category_id", "999999"),
    ("category_id", "1.5"), ("category_id", "9" * 100), ("unit", ""),
    ("name", "a" * 256), ("sku", "a" * 101), ("brand", "a" * 101),
    ("model", "a" * 101), ("unit", "a" * 31), ("image_url", "javascript:alert(1)"),
    ("image_url", "https://"), ("image_url", "https://user:password@example.test/image.png"),
    ("image_url", "https://example.test:bad/image.png"),
    ("image_url", "https://example.test/with space.png"), ("image_url", "https://example.test/" + "a" * 2048),
])
def test_invalid_product_is_not_saved_and_form_values_are_kept(inventory, field, value):
    client, _, data = inventory
    response = client.post("/admin/products/new", data=dict(data, **{field: value}))
    assert response.status_code == 422
    html = response.get_data(as_text=True)
    assert 'aria-invalid="true"' in html and 'id="' + field + '-error"' in html
    assert "Preces apraksts" in html
    assert db.session.scalar(db.select(db.func.count(Product.id))) == 0


def test_sku_is_unique_ignoring_case_and_edit_keeps_own_sku(inventory):
    client, _, data = inventory
    product = create_product(inventory)
    response = client.post("/admin/products/new", data=dict(data, sku="TeSt-001"))
    assert response.status_code == 422
    assert "unikālu SKU" in response.get_data(as_text=True)
    assert client.post(f"/admin/products/{product.id}/edit", data=data).status_code == 302
    assert db.session.scalar(db.select(db.func.count(Product.id))) == 1


def test_linked_product_is_deactivated_without_losing_offers_cart_or_order(inventory):
    client, _, data = inventory
    product = create_product(inventory)
    admin = db.session.scalar(db.select(User).where(User.role == "admin"))
    profile = admin.company_profile
    offer = Offer(product=product, created_by_admin=admin, supplier_name="Testa piegādātājs",
                  unit_price=10, vat_included=True, stock_qty=5)
    cart_item = CartItem(cart=Cart(user=admin), offer=offer, quantity=1)
    order = Order(user=admin, company_profile=profile, total_amount=10)
    order_item = OrderItem(order=order, offer=offer, product_name=product.name,
                           supplier_name=offer.supplier_name, unit_price=10, quantity=1,
                           delivery_price=0, line_total=10, vat_included=True)
    db.session.add_all([offer, cart_item, order_item])
    db.session.commit()
    assert "Apstiprināt deaktivizēšanu" in client.get(
        f"/admin/products/{product.id}/delete").get_data(as_text=True)
    response = client.post(f"/admin/products/{product.id}/delete", data={
        "csrf_token": data["csrf_token"], "confirmed": "1"}, follow_redirects=True)
    assert "Prece deaktivizēta" in response.get_data(as_text=True)
    db.session.refresh(product)
    assert product.is_active is False
    assert db.session.get(Offer, offer.id) is not None
    assert db.session.get(CartItem, cart_item.id).offer_id == offer.id
    assert db.session.get(OrderItem, order_item.id).offer_id == offer.id
    assert client.get("/catalog").json["items"] == []
    assert client.get(f"/catalog/products/{product.id}").status_code == 404
    assert client.post(f"/admin/products/{product.id}/edit", data=data).status_code == 302
    assert client.get("/catalog").json["count"] == 1


def test_admin_list_filters_and_public_product_image(inventory):
    client, category, data = inventory
    product = create_product(inventory)
    db.session.add(Product(name="Slēpta prece", sku="HIDDEN", category=category, is_active=False))
    db.session.commit()
    assert "Slēpta prece" not in client.get("/admin/products?status=active").get_data(as_text=True)
    assert "Testa prece" not in client.get("/admin/products?status=inactive").get_data(as_text=True)
    assert "Slēpta prece" not in client.get("/admin/products?q=test-001").get_data(as_text=True)
    item = client.get("/catalog").json["items"][0]
    assert item["image_url"] == data["image_url"]
    response = client.get(item["detail_url"])
    assert response.status_code == 200
    assert "Preces apraksts" in response.get_data(as_text=True)
    assert str(product.id) in item["detail_url"]


def test_product_posts_require_csrf_and_delete_confirmation(inventory):
    client, _, data = inventory
    assert client.post("/admin/products/new", data=dict(data, csrf_token="invalid")).status_code == 400
    assert client.post("/admin/products/new", data=dict(data, csrf_token="ā")).status_code == 400
    product = create_product(inventory)
    assert client.post(f"/admin/products/{product.id}/edit", data={}).status_code == 400
    assert client.post(f"/admin/products/{product.id}/delete", data={"confirmed": "1"}).status_code == 400
    assert client.post(f"/admin/products/{product.id}/delete", data={"csrf_token": data["csrf_token"]}).status_code == 400
    assert db.session.get(Product, product.id) is not None


@pytest.mark.parametrize("path,method", [
    ("/admin/products", "get"), ("/admin/products/new", "get"),
    ("/admin/products/new", "post"), ("/admin/products/1", "get"),
    ("/admin/products/1/edit", "post"), ("/admin/products/1/delete", "get"),
    ("/admin/products/1/delete", "post"),
])
def test_product_management_is_only_available_to_admins(database_app, path, method):
    client = database_app.test_client()
    assert getattr(client, method)(path).status_code == 302
    client.post("/auth/register", data=admin_data())
    assert getattr(client, method)(path).status_code == 403


def test_empty_category_list_and_unknown_product(inventory):
    client, category, _ = inventory
    db.session.delete(category)
    db.session.commit()
    html = client.get("/admin/products/new").get_data(as_text=True)
    assert "izveidojiet kategoriju" in html and "disabled" in html
    for suffix in ("", "/edit", "/delete"):
        assert client.get("/admin/products/999999" + suffix).status_code == 404
