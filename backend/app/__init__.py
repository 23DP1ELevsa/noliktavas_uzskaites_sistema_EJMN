from flask import Flask, render_template, request
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from .config import Config, environment_config, normalize_database_url
from .extensions import configure_engine, db, login_manager, migrate
from .routes import register_blueprints
from .commands import register_commands


def create_app(config_class=Config):
    # Katram lietotnes eksemplāram ielādējam vidi; testi var norādīt atsevišķu konfigurāciju.
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
    # Dzinēja iestatījumus piemērojam tikai pēc piesaistes konkrētajai lietotnei.
    with app.app_context():
        configure_engine(db.engine)
    from . import models  # noqa: F401 -- register all tables before migrations

    migrate.init_app(app, db)
    login_manager.init_app(app)
    register_blueprints(app)
    register_commands(app)

    def browser_error(error):
        # API saglabā savu atbildes formātu, bet pārlūka kļūdu lapas attēlojam latviski.
        if request.path.startswith("/api/") or request.path == "/catalog" or request.blueprint == "offers":
            return error
        messages = {
            400: ("Pieprasījumu neizdevās apstrādāt", "Pārbaudiet ievadītos datus un mēģiniet vēlreiz."),
            403: ("Piekļuve nav atļauta", "Jūsu kontam nav tiesību atvērt šo sadaļu."),
            404: ("Lapa nav atrasta", "Lapa vai izvēlētais ieraksts vairs nav pieejams. Atgriezieties katalogā, lai turpinātu."),
            405: ("Darbība nav atļauta", "Šai lapai izmantojiet paredzētās saites un veidlapas."),
            413: ("Fails ir pārāk liels", "Izvēlieties mazāku failu un mēģiniet augšupielādēt vēlreiz."),
            500: ("Neizdevās atvērt lapu", "Radās neparedzēta kļūda. Lūdzu, mēģiniet vēlreiz pēc brīža."),
            503: ("Pakalpojums īslaicīgi nav pieejams", "Lūdzu, mēģiniet vēlreiz pēc brīža."),
        }
        title, message = messages[error.code]
        if error.code < 500 and error.description != type(error).description:
            message = error.description
        response = error.get_response()
        response.set_data(render_template("error.html", code=error.code, error_title=title, error_message=message))
        response.content_type = "text/html; charset=utf-8"
        return response

    for code in (400, 403, 404, 405, 413, 500, 503):
        app.register_error_handler(code, browser_error)

    @app.context_processor
    def navigation_notifications():
        # Galvenē skaitām tikai pašreizējā lietotāja nelasītos paziņojumus.
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
