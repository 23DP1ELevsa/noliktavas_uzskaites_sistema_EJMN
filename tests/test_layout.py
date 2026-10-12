import re

from backend.app.extensions import db
from backend.app.models import Category, Offer, Product, Supplier
from backend.app.services.demo_data import ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, USER_EMAIL, DEFAULT_USER_PASSWORD


def test_all_pages_render_the_same_single_footer(database_app):
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    client = database_app.test_client()
    product_id = db.session.scalar(db.select(Product.id).where(Product.is_active.is_(True)).order_by(Product.id))
    supplier_id = db.session.scalar(db.select(Supplier.id).order_by(Supplier.id))
    offer_id = db.session.scalar(db.select(Offer.id).order_by(Offer.id))
    category_id = db.session.scalar(db.select(Category.id).order_by(Category.id))
    expected = None

    def check_footer(path):
        nonlocal expected
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        footers = re.findall(r"<footer\b.*?</footer>", html, flags=re.S)
        assert len(footers) == 1, path
        if expected is None:
            expected = footers[0]
        assert footers[0] == expected, path
        assert html.index("</main>") < html.index("<footer"), path

    for path in ("/", "/catalog/page", f"/catalog/products/{product_id}", "/auth/login", "/auth/register"):
        check_footer(path)

    client.get('/auth/logout')
    client.post('/auth/login', data={'email': USER_EMAIL, 'password': DEFAULT_USER_PASSWORD})
    check_footer('/orders/checkout')
    check_footer('/orders')

    client.get('/auth/logout')
    client.post("/auth/login", data={"email": ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD})
    for path in ("/auth/profile", "/cart", "/admin", "/admin/import/json", "/admin/supplier-products",
                 "/admin/orders",
                 "/admin/supplier-products/new", f"/admin/supplier-products/{offer_id}/edit",
                 f"/admin/supplier-products/{offer_id}/delete",
                 f"/admin/products/new?supplier_id={supplier_id}", "/admin/suppliers", "/admin/suppliers/new",
                 f"/admin/suppliers/{supplier_id}", f"/admin/suppliers/{supplier_id}/edit", f"/admin/suppliers/{supplier_id}/delete",
                 "/admin/products", "/admin/products/new",
                 f"/admin/products/{product_id}", f"/admin/products/{product_id}/edit", f"/admin/products/{product_id}/delete",
                 "/admin/categories", "/admin/categories/new", f"/admin/categories/{category_id}/edit"):
        check_footer(path)
