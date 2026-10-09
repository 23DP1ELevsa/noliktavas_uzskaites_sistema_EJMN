import click
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .services.demo_data import (
    ADMIN_EMAIL, USER_EMAIL, DEFAULT_ADMIN_PASSWORD, DEFAULT_USER_PASSWORD,
    DemoDataError, seed_demo_data,
)


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

    @app.cli.command("seed-demo")
    @click.option("--admin-password", envvar="DEMO_ADMIN_PASSWORD", default=DEFAULT_ADMIN_PASSWORD,
                  help="Password for a new demo administrator; existing passwords are preserved.")
    @click.option("--user-password", envvar="DEMO_USER_PASSWORD", default=DEFAULT_USER_PASSWORD,
                  help="Password for a new demo buyer; existing passwords are preserved.")
    def seed_demo(admin_password, user_password):
        """Load demo categories, products, offers and accounts after db upgrade."""
        try:
            created = seed_demo_data(admin_password, user_password)
            db.session.commit()
        except DemoDataError as error:
            db.session.rollback()
            raise click.ClickException(str(error)) from None
        except SQLAlchemyError:
            db.session.rollback()
            raise click.ClickException(
                "Demo data was not saved. Check DATABASE_URL and run flask --app run db upgrade."
            ) from None
        except (OSError, ValueError, KeyError, TypeError):
            db.session.rollback()
            raise click.ClickException(
                "Cannot load data_samples/demo_catalog.json; no demo changes were saved."
            ) from None

        click.echo("Demo data ready. Created: " + ", ".join(
            f"{name}={count}" for name, count in created.items()
        ))
        click.echo(f"Demo accounts: {ADMIN_EMAIL} (admin), {USER_EMAIL} (user).")
        click.echo("Existing data and passwords were preserved. See docs/demo-data.md for demo credentials.")
