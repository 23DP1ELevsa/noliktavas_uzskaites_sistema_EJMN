import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.extensions import db
from backend.app.models import CompanyProfile, User


OLD_PASSWORD = "Current-secret!"
NEW_PASSWORD = "Jauna-parole123!"


def account_client(app, role="user"):
    user = User(email="password@example.test", full_name="Paroles Pārbaude", role=role)
    user.set_password(OLD_PASSWORD)
    user.company_profile = CompanyProfile(company_name="Paroles SIA", registration_no="40000000001",
                                          address="Rīga, Pārbaudes iela 1")
    db.session.add(user)
    db.session.commit()
    client = app.test_client()
    client.post("/auth/login", data={"email": user.email, "password": OLD_PASSWORD})
    html = client.get("/auth/profile").get_data(as_text=True)
    with client.session_transaction() as session:
        token = session["cart_csrf_token"]
    assert 'action="/auth/password"' in html
    assert f'name="csrf_token" value="{token}"' in html
    assert "Konta veids" not in html
    return client, user.id, token


def password_data(token, **changes):
    return {"csrf_token": token, "current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD, **changes}


@pytest.mark.parametrize("role", ["user", "admin"])
def test_password_change_updates_only_current_account_and_can_log_in_with_new_password(database_app, role):
    client, user_id, token = account_client(database_app, role)
    other = User(email="other-password@example.test", full_name="Cits Lietotājs")
    other.set_password(OLD_PASSWORD)
    db.session.add(other)
    db.session.commit()
    other_id = other.id

    response = client.post("/auth/password", data=password_data(
        token, user_id=str(other_id), email="injected@example.test", role="admin", company_name="Mainīts"))

    assert response.status_code == 302
    assert response.location == "/auth/profile"
    html = client.get(response.location).get_data(as_text=True)
    assert "Parole veiksmīgi nomainīta." in html
    assert OLD_PASSWORD not in html and NEW_PASSWORD not in html
    db.session.remove()
    saved = db.session.get(User, user_id)
    assert saved.check_password(NEW_PASSWORD)
    assert not saved.check_password(OLD_PASSWORD)
    assert saved.password_hash not in (OLD_PASSWORD, NEW_PASSWORD)
    assert saved.full_name == "Paroles Pārbaude" and saved.role == role
    assert saved.email == "password@example.test"
    assert saved.company_profile.company_name == "Paroles SIA"
    assert db.session.get(User, other_id).check_password(OLD_PASSWORD)

    client.get("/auth/logout")
    old_login = client.post("/auth/login", data={"email": saved.email, "password": OLD_PASSWORD})
    assert old_login.status_code == 200
    assert "Nepareizs e-pasts vai parole." in old_login.get_data(as_text=True)
    new_login = client.post("/auth/login", data={"email": saved.email, "password": NEW_PASSWORD})
    assert new_login.status_code == 302


@pytest.mark.parametrize("changes,field,message", [
    ({"current_password": "Wrong-secret!"}, "current_password", "Pašreizējā parole nav pareiza."),
    ({"current_password": ""}, "current_password", "Ievadiet pašreizējo paroli."),
    ({"new_password_confirmation": "Different-secret!"}, "new_password_confirmation", "Paroles nesakrīt."),
    ({"new_password_confirmation": ""}, "new_password_confirmation", "Atkārtojiet jauno paroli."),
    ({"new_password": "Short!", "new_password_confirmation": "Short!"}, "new_password", "vismaz 8"),
    ({"new_password": "lowercase!", "new_password_confirmation": "lowercase!"}, "new_password", "lielais burts"),
    ({"new_password": "Nosymbol123", "new_password_confirmation": "Nosymbol123"}, "new_password", "speciālais simbols"),
    ({"new_password": "", "new_password_confirmation": ""}, "new_password", "vismaz 8"),
])
def test_invalid_password_change_keeps_saved_data_and_never_echoes_passwords(database_app, changes, field, message):
    client, user_id, token = account_client(database_app)
    values = password_data(token, **changes)

    response = client.post("/auth/password", data=values)

    assert response.status_code == 422
    html = response.get_data(as_text=True)
    assert message in html
    assert f'id="{field}"' in html and 'aria-invalid="true"' in html
    assert 'value="Paroles Pārbaude"' in html and 'value="Paroles SIA"' in html
    for key in ("current_password", "new_password", "new_password_confirmation"):
        assert not values[key] or values[key] not in html
    db.session.remove()
    saved = db.session.get(User, user_id)
    assert saved.check_password(OLD_PASSWORD)
    assert saved.company_profile.company_name == "Paroles SIA"


@pytest.mark.parametrize("token", ["", "incorrect-token"])
def test_password_change_rejects_invalid_csrf(database_app, token):
    client, user_id, _ = account_client(database_app)

    response = client.post("/auth/password", data=password_data(token))

    assert response.status_code == 400
    db.session.remove()
    assert db.session.get(User, user_id).check_password(OLD_PASSWORD)


def test_password_change_requires_login_and_post(database_app):
    client = database_app.test_client()
    response = client.post("/auth/password", data=password_data("unused"))
    assert response.status_code == 302 and "/auth/login" in response.location
    assert client.get("/auth/password").status_code == 405
    assert db.session.scalar(db.select(User.id)) is None


def test_failed_password_write_rolls_back_hash(database_app, monkeypatch):
    client, user_id, token = account_client(database_app)

    def fail_commit():
        raise IntegrityError("test write failure", {}, Exception("test failure"))

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "commit", fail_commit)
        response = client.post("/auth/password", data=password_data(token))

    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert "Paroli neizdevās nomainīt." in html
    assert OLD_PASSWORD not in html and NEW_PASSWORD not in html
    db.session.remove()
    assert db.session.get(User, user_id).check_password(OLD_PASSWORD)
