"""Team demonstration REST API; serves only fictional sample offers."""

from pathlib import Path

from flask import Blueprint, Flask, Response


test_api_bp = Blueprint("test_api", __name__, url_prefix="/api/test")
SAMPLE_FILE = Path(__file__).resolve().parents[1] / "data_samples" / "offers_import.json"


@test_api_bp.get("/offers")
def offers():
    # Static examples never expose production offers, users or database details.
    return Response(SAMPLE_FILE.read_bytes(), mimetype="application/json",
                    headers={"Cache-Control": "no-store"})


def create_test_api():
    app = Flask(__name__)
    app.register_blueprint(test_api_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
