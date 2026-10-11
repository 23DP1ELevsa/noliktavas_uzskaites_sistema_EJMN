from flask import Flask, render_template
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from .config import Config, environment_config, normalize_database_url
from .extensions import configure_engine, db, login_manager, migrate
from .routes import register_blueprints
from .commands import register_commands


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.from_mapping(environment_config())
    if isinstance(config_class, dict):
        app.config.from_mapping(config_class)
    elif config_class is not Config:
        app.config.from_object(config_class)

    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(
        app.config["SQLALCHEMY_DATABASE_URI"]
    )
    db.init_app(app)
    with app.app_context():
        configure_engine(db.engine)
    from . import models  # noqa: F401 -- register all tables before migrations

    migrate.init_app(app, db)
    login_manager.init_app(app)
    register_blueprints(app)
    register_commands(app)

    @app.context_processor
    def navigation_notifications():
        if not current_user.is_authenticated:
            return {"nav_unread": 0}
        from .models import Notification
        try:
            count = db.session.scalar(db.select(db.func.count(Notification.id)).where(
                Notification.user_id == current_user.id, Notification.is_read.is_(False)))
        except SQLAlchemyError:
            count = 0
        return {"nav_unread": count}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
