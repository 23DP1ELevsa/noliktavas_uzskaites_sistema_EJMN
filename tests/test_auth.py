from backend.app.extensions import db
from backend.app.models import CompanyProfile, User


def registration_data(**overrides):
    data = {
        "full_name": "Anna Kalniņa",
        "email": "anna@example.test",
        "password": "droša-parole",
        "password_confirmation": "droša-parole",
        "company_name": "Anna SIA",
        "registration_no": "40100000001",
        "address": "Rīga, Brīvības iela 1",
    }
    data.update(overrides)
    return data


def test_register_login_and_logout(database_app):
    client = database_app.test_client()

    response = client.post("/auth/register", data=registration_data())

    assert response.status_code == 302
    user = db.session.scalar(db.select(User).where(User.email == "anna@example.test"))
    assert user is not None
    assert user.check_password("droša-parole")
    assert db.session.scalar(db.select(CompanyProfile).where(CompanyProfile.user_id == user.id))

    client.get("/auth/logout")
    response = client.post("/auth/login", data={
        "email": "anna@example.test",
        "password": "droša-parole",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_register_rejects_invalid_password_and_duplicate_email(database_app):
    client = database_app.test_client()
    client.post("/auth/register", data=registration_data())
    client.get("/auth/logout")

    response = client.post("/auth/register", data=registration_data(
        password="short",
        password_confirmation="short",
    ))
    assert response.status_code == 200
    assert "vismaz 8 rakstzīmes" in response.get_data(as_text=True)

    response = client.post("/auth/register", data=registration_data(
        password="jauna-parole",
        password_confirmation="jauna-parole",
    ))
    assert response.status_code == 200
    assert "jau pastāv" in response.get_data(as_text=True)


def test_login_rejects_unknown_credentials(database_app):
    response = database_app.test_client().post("/auth/login", data={
        "email": "unknown@example.test",
        "password": "wrong-password",
    })

    assert response.status_code == 200
    assert "Nepareizs e-pasts vai parole." in response.get_data(as_text=True)


def test_profile_can_be_updated_and_requires_login(database_app):
    client = database_app.test_client()
    response = client.get("/auth/profile")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    client.post("/auth/register", data=registration_data())
    response = client.post("/auth/profile", data={
        "full_name": "Anna Ozola",
        "company_name": "Ozola SIA",
        "registration_no": "40200000002",
        "vat_no": "LV40200000002",
        "address": "Rīga, Centra iela 2",
        "phone": "+371 20000000",
    })
    assert response.status_code == 302
    assert "Profils veiksmīgi saglabāts." in client.get("/auth/profile").get_data(as_text=True)

    user = db.session.scalar(db.select(User).where(User.email == "anna@example.test"))
    assert user.full_name == "Anna Ozola"
    assert user.company_profile.company_name == "Ozola SIA"
