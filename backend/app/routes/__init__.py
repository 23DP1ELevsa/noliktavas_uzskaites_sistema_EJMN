from flask import Flask

from .admin import admin_bp
from .auth import auth_bp
from .cart import cart_bp
from .catalog import catalog_bp
from .import_data import import_bp
from .offers import offers_bp
from .orders import orders_bp


def register_blueprints(app: Flask):
    for blueprint in (
        auth_bp,
        catalog_bp,
        offers_bp,
        cart_bp,
        orders_bp,
        admin_bp,
        import_bp,
    ):
        app.register_blueprint(blueprint)
