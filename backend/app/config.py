import os
import socket
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def normalize_database_url(value):
    """Use the installed PyMySQL driver for MySQL URLs, including Railway URLs."""
    if value is None:
        value = "sqlite:///stockflow.db"
    url = make_url(value)
    if url.drivername == "mysql":
        url = url.set(drivername="mysql+pymysql")
    if url.drivername == "mysql+pymysql" and "charset" not in url.query:
        url = url.update_query_dict({"charset": "utf8mb4"})
    return url


def _local_mysql_is_available(url):
    if url.drivername not in {"mysql", "mysql+pymysql", "mysql+mysqldb"}:
        return True

    host = url.host or "localhost"
    if host not in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return True

    port = url.port or 3306
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def environment_config():
    """Read settings at app creation, without overriding deployment variables."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    raw_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    database_url = "sqlite:///stockflow.db"
    if raw_url:
        parsed_url = normalize_database_url(raw_url)
        if not parsed_url.drivername.startswith("mysql") or _local_mysql_is_available(parsed_url):
            database_url = raw_url

    return {
        "SECRET_KEY": os.getenv("SECRET_KEY", "dev-only-change-me"),
        "SQLALCHEMY_DATABASE_URI": database_url,
    }


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
