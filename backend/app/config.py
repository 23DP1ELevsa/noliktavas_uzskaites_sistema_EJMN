import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def normalize_database_url(value):
    """Use the installed PyMySQL driver for MySQL URLs, including Railway URLs."""
    url = make_url(value)
    if url.drivername == "mysql":
        url = url.set(drivername="mysql+pymysql")
    if url.drivername == "mysql+pymysql" and "charset" not in url.query:
        url = url.update_query_dict({"charset": "utf8mb4"})
    return url


def environment_config():
    """Read settings at app creation, without overriding deployment variables."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY", "dev-only-change-me"),
        "SQLALCHEMY_DATABASE_URI": os.getenv("DATABASE_URL")
        or os.getenv("MYSQL_URL")
        or "mysql+pymysql://stockflow:stockflow@localhost/stockflow",
    }


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
