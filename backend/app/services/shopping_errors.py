from flask import current_app, render_template

from ..extensions import db


def shopping_database_error(error):
    db.session.rollback()
    current_app.logger.error("Shopping database operation failed", exc_info=error)
    return render_template("shopping_error.html"), 503
