from flask import Flask, render_template

from .config import Config
from .extensions import db, login_manager
from .routes import register_blueprints


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)
    if isinstance(config_class, dict):
        app.config.from_mapping(config_class)
    elif config_class is not Config:
        app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    register_blueprints(app)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
