from sqlalchemy.engine import URL

from backend.app import create_app
from backend.app.config import normalize_database_url


def test_railway_url_uses_pymysql_and_preserves_encoded_password():
    url = normalize_database_url("mysql://user:p%40ss%2Fword@host:3307/stockflow")
    assert url.drivername == "mysql+pymysql"
    assert url.password == "p@ss/word"
    assert url.port == 3307
    assert url.database == "stockflow"
    assert url.query["charset"] == "utf8mb4"


def test_explicit_charset_is_preserved():
    url = normalize_database_url("mysql+pymysql://user:pass@host/db?charset=utf8")
    assert url.query["charset"] == "utf8"


def test_sqlite_url_is_unchanged():
    assert str(normalize_database_url("sqlite:///:memory:")) == "sqlite:///:memory:"


def test_explicit_app_config_overrides_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@host/db")
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert app.config["SQLALCHEMY_DATABASE_URI"].drivername == "sqlite"


def test_environment_is_read_each_time_an_app_is_created(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "first-test-secret")
    assert create_app().config["SECRET_KEY"] == "first-test-secret"
    monkeypatch.setenv("SECRET_KEY", "second-test-secret")
    assert create_app().config["SECRET_KEY"] == "second-test-secret"


def test_unavailable_local_mysql_does_not_fall_back_to_sqlite(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:password@127.0.0.1:3306/stockflow")
    def unavailable(*args, **kwargs):
        raise OSError("MySQL is unavailable")

    monkeypatch.setattr("socket.create_connection", unavailable)

    app = create_app()

    url = app.config["SQLALCHEMY_DATABASE_URI"]
    assert url.drivername == "mysql+pymysql"
    assert url.host == "127.0.0.1"
    assert url.database == "stockflow"


def test_url_object_is_supported():
    url = URL.create("mysql", username="user", password="p@ss", host="host", database="db")
    assert normalize_database_url(url).password == "p@ss"
