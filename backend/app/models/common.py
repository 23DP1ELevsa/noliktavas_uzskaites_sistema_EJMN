from sqlalchemy.dialects.mysql import BIGINT

from ..extensions import db


# SQLite requires INTEGER for auto-increment; MySQL retains BIGINT UNSIGNED.
ID_TYPE = db.BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(
    db.Integer(), "sqlite"
)
TABLE_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4",
                 "mysql_collate": "utf8mb4_unicode_ci"}


class IdentityMixin:
    id = db.Column(ID_TYPE, primary_key=True, autoincrement=True)


class CreatedMixin:
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())


def active_column():
    return db.Column(db.Boolean(create_constraint=True, name="is_active_boolean"), nullable=False, default=True,
                     server_default=db.true())
