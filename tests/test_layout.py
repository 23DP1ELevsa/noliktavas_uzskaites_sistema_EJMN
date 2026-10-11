import re

from backend.app.services.demo_data import ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def test_all_pages_render_the_same_single_footer(database_app):
    result = database_app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    client = database_app.test_client()
    expected = None

    def check_footer(path):
        nonlocal expected
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        footers = re.findall(r"<footer\b.*?</footer>", html, flags=re.S)
        assert len(footers) == 1, path
        if expected is None:
            expected = footers[0]
        assert footers[0] == expected, path
        assert html.index("</main>") < html.index("<footer"), path

    for path in ("/", "/catalog/page", "/catalog/products/1", "/auth/login", "/auth/register"):
        check_footer(path)

    client.post("/auth/login", data={"email": ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD})
    for path in ("/auth/profile", "/admin/products", "/admin/products/new",
                 "/admin/products/1", "/admin/products/1/edit", "/admin/products/1/delete",
                 "/admin/categories", "/admin/categories/new", "/admin/categories/1/edit"):
        check_footer(path)
