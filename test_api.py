"""Optional standalone launch of the same team demo API on port 5001."""

from backend.test_api import create_test_api


app = create_test_api()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
