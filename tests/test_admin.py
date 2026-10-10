from backend.app.extensions import db
from backend.app.models import Category, Product, User


def admin_data():
    return {
        "full_name": "Admin Demo",
        "email": "admin@example.test",
        "password": "admin-password",
        "password_confirmation": "admin-password",
        "company_name": "Admin SIA",
        "registration_no": "40000000000",
        "address": "Rīga, Testa iela 1",
    }


def login_admin(client):
    client.post("/auth/register", data=admin_data())
    user = db.session.scalar(db.select(User).where(User.email == "admin@example.test"))
    user.role = "admin"
    db.session.commit()
    client.post("/auth/logout")
    return client.post("/auth/login", data={
        "email": "admin@example.test",
        "password": "admin-password",
    })


def test_admin_can_create_update_and_delete_category(database_app):
    client = database_app.test_client()
    response = login_admin(client)
    assert response.status_code == 302

    response = client.post("/admin/categories/new", data={
        "name": "Darba aprīkojums",
        "description": "Biroja un noliktavas aprīkojums.",
    })
    assert response.status_code == 302
    category = db.session.scalar(db.select(Category).where(Category.name == "Darba aprīkojums"))
    assert category.description == "Biroja un noliktavas aprīkojums."

    response = client.post(f"/admin/categories/{category.id}/edit", data={
        "name": "Noliktavas aprīkojums",
        "description": "Atjaunots apraksts.",
    })
    assert response.status_code == 302
    db.session.refresh(category)
    assert category.name == "Noliktavas aprīkojums"

    response = client.post(f"/admin/categories/{category.id}/delete")
    assert response.status_code == 302
    assert db.session.get(Category, category.id) is None


def test_category_delete_is_blocked_when_products_are_attached(database_app):
    client = database_app.test_client()
    login_admin(client)
    category = Category(name="Izmanto")
    db.session.add(category)
    db.session.flush()
    db.session.add(Product(category=category, sku="ADMIN-001", name="Testa prece"))
    db.session.commit()

    response = client.post(f"/admin/categories/{category.id}/delete")
    assert response.status_code == 302
    assert db.session.get(Category, category.id) is not None
    assert "nevar dzēst" in client.get("/admin/categories").get_data(as_text=True)


def test_non_admin_cannot_open_category_crud(database_app):
    client = database_app.test_client()
    client.post("/auth/register", data=admin_data())
    client.post("/auth/logout")
    response = client.get("/admin/categories")
    assert response.status_code == 403
