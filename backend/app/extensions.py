from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, event


db = SQLAlchemy(metadata=MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}))
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def configure_engine(engine):
    @event.listens_for(engine, "connect")
    def configure_connection(connection, _record):
        cursor = connection.cursor()
        try:
            if engine.dialect.name == "sqlite":
                cursor.execute("PRAGMA foreign_keys=ON")
            elif engine.dialect.name in {"mysql", "mariadb"}:
                cursor.execute("SET time_zone = '+00:00'")
        finally:
            cursor.close()


@login_manager.user_loader
def load_user(user_id):
    from .models import User

    try:
        identifier = int(user_id)
    except (TypeError, ValueError):
        return None
    if not 0 < identifier <= 18446744073709551615:
        return None
    user = db.session.get(User, identifier)
    return user if user is not None and user.is_active else None
