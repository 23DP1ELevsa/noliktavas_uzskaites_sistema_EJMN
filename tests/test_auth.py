import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.extensions import db
from backend.app.models import CompanyProfile, User


def registration_data(**overrides):
    data = {
        "full_name": "Anna Kalniņa",
        "email": "anna@example.test",
        "password": "Droša-parole!",
        "password_confirmation": "Droša-parole!",
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
    assert user.check_password("Droša-parole!")
    assert db.session.scalar(db.select(CompanyProfile).where(CompanyProfile.user_id == user.id))

    client.get("/auth/logout")
    response = client.post("/auth/login", data={
        "email": "anna@example.test",
        "password": "Droša-parole!",
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
        password="Jauna-parole!",
        password_confirmation="Jauna-parole!",
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


@pytest.mark.parametrize("password", ["", "Ab!1234", "abcdefgh!", "ABCDEFGH", "Abcdefg "])
def test_weak_password_cannot_create_account_even_without_javascript(database_app, password):
    response = database_app.test_client().post("/auth/register", data=registration_data(
        password=password, password_confirmation=password,
    ))
    assert response.status_code == 200
    assert db.session.scalar(db.select(User.id)) is None
    user = User(email="weak@example.test", full_name="Test")
    with pytest.raises(ValueError):
        user.set_password(password)


@pytest.mark.parametrize("password", ["Abcdefg!", "Ābcdefg!", "Abcdefg_", "Abcdefg€", "Abcdefg😀"])
def test_password_accepts_minimum_length_and_unicode(database_app, password):
    response = database_app.test_client().post("/auth/register", data=registration_data(
        password=password, password_confirmation=password,
    ))
    assert response.status_code == 302
    user = db.session.scalar(db.select(User))
    assert user.check_password(password)


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


def test_profile_creates_missing_company_and_reloads_saved_data(database_app):
    user = User(email="admin@example.test", full_name="Administrators", role="admin")
    user.set_password("Test-password!")
    db.session.add(user)
    db.session.commit()
    user_id = user.id
    client = database_app.test_client()
    client.post("/auth/login", data={"email": user.email, "password": "Test-password!"})

    response = client.get("/auth/profile")
    assert response.status_code == 200
    assert "Pievienojiet sava uzņēmuma datus" in response.get_data(as_text=True)
    data = registration_data(
        full_name="  Jānis Bērziņš  ", company_name="  Bērziņš SIA  ",
        delivery_address="  Liepāja, Noliktavas iela 5  ",
        phone="  +371 20000000  ", vat_no="  LV40100000001  ",
    )
    response = client.post("/auth/profile", data=data)
    assert response.status_code == 302

    db.session.remove()
    user = db.session.get(User, user_id)
    assert user.full_name == "Jānis Bērziņš"
    assert user.company_profile.company_name == "Bērziņš SIA"
    assert user.company_profile.registration_no == "40100000001"
    assert user.company_profile.vat_no == "LV40100000001"
    assert user.company_profile.phone == "+371 20000000"
    assert user.company_profile.address == data["address"]
    assert user.company_profile.delivery_address == "Liepāja, Noliktavas iela 5"
    assert user.company_profile.effective_delivery_address == "Liepāja, Noliktavas iela 5"
    # A fresh app context mirrors the next request after closing the DB session.
    with database_app.app_context():
        html = client.get("/auth/profile").get_data(as_text=True)
    for value in (user.full_name, user.company_profile.company_name,
                  user.company_profile.delivery_address, user.company_profile.phone):
        assert f'value="{value}"' in html


@pytest.mark.parametrize("field,value", [
    ("full_name", " "), ("full_name", "A" * 151),
    ("company_name", " "), ("company_name", "A" * 256),
    ("registration_no", ""), ("registration_no", "A" * 51),
    ("registration_no", "401!000"), ("vat_no", "LV@40100000001"),
    ("vat_no", "A" * 51), ("phone", "zvaniet vēlāk"),
    ("phone", "+371 123"), ("phone", "1" * 16),
    ("phone", "++37120000000"), ("phone", "1" * 51), ("phone", "((1234567"),
    ("address", " "), ("address", "A" * 256),
    ("address", "Rīga\x00iela 1"), ("delivery_address", "A" * 256),
])
def test_profile_rejects_invalid_input_without_changing_saved_data(database_app, field, value):
    client = database_app.test_client()
    client.post("/auth/register", data=registration_data())
    user = db.session.scalar(db.select(User).where(User.email == "anna@example.test"))
    profile_id = user.company_profile.id
    response = client.post("/auth/profile", data=registration_data(**{
        "company_name": "Jauns uzņēmums", "full_name": "Jauns vārds", field: value,
    }))
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Profils nav saglabāts." in html
    assert f'id="{field}-error"' in html
    assert 'aria-invalid="true"' in html

    db.session.remove()
    profile = db.session.get(CompanyProfile, profile_id)
    assert profile.company_name == "Anna SIA"
    assert profile.user.full_name == "Anna Kalniņa"
    assert profile.phone is None
    assert profile.delivery_address is None


def test_profile_clears_optional_fields_and_uses_company_address(database_app):
    client = database_app.test_client()
    client.post("/auth/register", data=registration_data(
        phone="+371 20000000", vat_no="LV40100000001", delivery_address="Jelgava, iela 1",
    ))
    user = db.session.scalar(db.select(User).where(User.email == "anna@example.test"))
    profile_id = user.company_profile.id
    response = client.post("/auth/profile", data=registration_data(
        phone=" ", vat_no=" ", delivery_address=" ", address="Cēsis, iela 2",
    ))
    assert response.status_code == 302
    db.session.remove()
    profile = db.session.get(CompanyProfile, profile_id)
    assert profile.phone is None and profile.vat_no is None and profile.delivery_address is None
    assert profile.effective_delivery_address == "Cēsis, iela 2"


def test_profile_edits_only_current_user(database_app):
    client = database_app.test_client()
    client.post("/auth/register", data=registration_data())
    first = db.session.scalar(db.select(User).where(User.email == "anna@example.test"))
    first_id, first_profile_id = first.id, first.company_profile.id
    client.get("/auth/logout")
    client.post("/auth/register", data=registration_data(email="other@example.test"))
    response = client.post("/auth/profile", data=registration_data(
        company_name="Other SIA", user_id=str(first_id), company_profile_id=str(first_profile_id),
        email="stolen@example.test", role="admin",
    ))
    assert response.status_code == 302
    db.session.remove()
    first = db.session.get(User, first_id)
    assert first.company_profile.company_name == "Anna SIA"
    other = db.session.scalar(db.select(User).where(User.email == "other@example.test"))
    assert other.company_profile.company_name == "Other SIA"
    assert other.role == "user"


@pytest.mark.parametrize("field,value", [("phone", "123"), ("company_name", "A" * 256),
                                        ("registration_no", "bad@number"),
                                        ("delivery_address", "A" * 256)])
def test_registration_validates_company_data(database_app, field, value):
    response = database_app.test_client().post("/auth/register", data=registration_data(**{field: value}))
    assert response.status_code == 200
    assert f'id="{field}-error"' in response.get_data(as_text=True)
    assert db.session.scalar(db.select(User)) is None
    assert db.session.scalar(db.select(CompanyProfile)) is None


def test_profile_post_requires_login(database_app):
    response = database_app.test_client().post("/auth/profile", data=registration_data())
    assert response.status_code == 302 and "/auth/login" in response.headers["Location"]
    assert db.session.scalar(db.select(CompanyProfile)) is None


def test_profile_save_failure_rolls_back_and_preserves_form(database_app, monkeypatch):
    client = database_app.test_client()
    client.post("/auth/register", data=registration_data())
    user_id = db.session.scalar(db.select(User.id))

    def fail_commit():
        raise IntegrityError("test write failure", {}, Exception("test failure"))

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        response = client.post("/auth/profile", data=registration_data(company_name="Jauns uzņēmums"))
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Profilu neizdevās saglabāt." in html
    assert 'value="Jauns uzņēmums"' in html
    db.session.remove()
    assert db.session.get(User, user_id).company_profile.company_name == "Anna SIA"
