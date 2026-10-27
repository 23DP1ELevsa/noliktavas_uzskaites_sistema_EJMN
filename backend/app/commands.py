import click
from datetime import datetime
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

    @app.cli.command("audit-offer-duplicates")
    @click.option("--fix", is_flag=True, help="Deactivate duplicate active offers, keeping the newest.")
    def audit_offer_duplicates(fix):
        """Inspect (or safely deactivate) duplicate supplier/product offers.

        Never deletes offers, carts, or order history. Without --fix this is
        read-only and prints which offer would remain active.
        """
        from .models import Offer, Supplier

        try:
            suppliers = {item.name_key: item.id
                         for item in db.session.scalars(db.select(Supplier))}
            groups = {}
            active = db.session.scalars(
                db.select(Offer).where(Offer.is_active.is_(True))
                .order_by(Offer.product_id, Offer.id)
            ).all()
            for offer in active:
                name_key = " ".join(offer.supplier_name.split()).casefold()
                supplier_id = offer.supplier_id or suppliers.get(name_key)
                supplier_key = ("id", supplier_id) if supplier_id else ("name", name_key)
                groups.setdefault((offer.product_id, supplier_key), []).append(offer)
            duplicates = [group for group in groups.values() if len(group) > 1]
            if not duplicates:
                click.echo("No duplicate active offers for the same supplier and product.")
                return

            count = 0
            for group in duplicates:
                # Most recently updated offer wins, using ID for equal timestamps.
                ranked = sorted(group, key=lambda item: (item.updated_at or datetime.min, item.id),
                                reverse=True)
                keeper, redundant = ranked[0], ranked[1:]
                count += len(redundant)
                click.echo(f"Product {keeper.product.sku}; supplier {keeper.supplier_name}: "
                           f"keep offer #{keeper.id}, deactivate "
                           + ", ".join(f"#{item.id}" for item in redundant))
                if fix:
                    for item in redundant:
                        item.is_active = False
            if fix:
                db.session.commit()
                click.echo(f"Deactivated {count} duplicate offers across {len(duplicates)} groups. "
                           "Orders and carts were preserved.")
            else:
                click.echo(f"Found {count} duplicate offers in {len(duplicates)} groups. "
                           "Run with --fix to deactivate them; no data changed.")
        except SQLAlchemyError as error:
            db.session.rollback()
            raise click.ClickException("Could not audit offers; no changes were saved.") from error

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
