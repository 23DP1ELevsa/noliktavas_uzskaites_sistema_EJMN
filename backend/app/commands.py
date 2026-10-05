import click
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db


def register_commands(app):
    @app.cli.command("db-check")
    def db_check():
        """Check connectivity and presence of all application tables without changing data."""
        try:
            db.session.execute(text("SELECT 1"))
            existing = set(inspect(db.engine).get_table_names())
        except SQLAlchemyError:
            raise click.ClickException(
                "Database connection failed. Check DATABASE_URL and database availability."
            ) from None
        missing = set(db.metadata.tables) - existing
        if missing:
            raise click.ClickException(
                "Missing tables: " + ", ".join(sorted(missing)) + ". Run flask --app run db upgrade."
            )
        click.echo(f"Database connection OK; all {len(db.metadata.tables)} application tables exist.")
