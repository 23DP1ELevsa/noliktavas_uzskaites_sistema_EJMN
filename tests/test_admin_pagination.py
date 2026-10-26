from contextlib import contextmanager
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import template_rendered

from backend.app.extensions import db
from backend.app.models import Category, CompanyProfile, Offer, Order, Product, Supplier, User


LISTS = ["orders", "suppliers", "products", "supplier-products", "categories"]


class PageLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inside = False
        self.links = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav":
            self.inside = "data-admin-pagination" in attrs
        elif self.inside and tag == "a":
            self.links[attrs["rel"]] = attrs["href"]

    def handle_endtag(self, tag):
        if tag == "nav":
            self.inside = False


@contextmanager
def rendered_context(app):
    captured = []

    def record(sender, template, context, **extra):
        captured.append(context)

    template_rendered.connect(record, app)
    try:
        yield captured
    finally:
        template_rendered.disconnect(record, app)


@pytest.fixture
def admin_lists(database_app):
    admin = User(email="admin-pages@example.test", full_name="Lapošanas administrators",
                 password_hash="unused", role="admin")
    admin.company_profile = CompanyProfile(company_name="Lapošanas SIA", registration_no="40000000001",
                                           address="Rīga")
    db.session.add(admin)
    db.session.flush()
    ids = {section: [] for section in LISTS}
    for index in range(23):
        category = Category(name=f"Lapošana {index:02}")
        supplier = Supplier(name=f"Lapošana {index:02}", name_key=f"lapošana {index:02}",
                            is_active=index < 21)
        # Identical names and dates exercise the ID tie-breakers across page boundaries.
        product = Product(name="Lapošana prece", sku=f"PAGE-{index:02}", category=category,
                          is_active=index < 21)
        order = Order(user=admin, company_profile=admin.company_profile, total_amount="10.00",
                      created_at=datetime(2026, 1, 1), status="iesniegts" if index < 21 else "noraidīts")
        offer = Offer(product=product, supplier=supplier, supplier_name="Lapošana piegādātājs",
                      supplier_sku=f"PAGE-{index:02}", created_by_admin=admin,
                      unit_price="1.00", vat_included=True, is_active=index < 21)
        db.session.add_all([category, supplier, product, order, offer])
        db.session.flush()
        for section, item in zip(LISTS, [order, supplier, product, offer, category]):
            ids[section].append(item.id)
    db.session.commit()
    client = database_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"], session["_fresh"] = str(admin.id), True
    return database_app, client, ids


@pytest.mark.parametrize("section", LISTS)
def test_admin_lists_show_ten_with_complete_nonoverlapping_pages(admin_lists, section):
    app, client, ids = admin_lists
    url = f"/admin/{section}?status=all"
    actual = []
    for page, count in [(1, 10), (2, 10), (3, 3)]:
        with rendered_context(app) as captured:
            response = client.get(f"{url}&page={page}")
        assert response.status_code == 200
        pagination = captured[-1]["pagination"]
        assert len(pagination.items) == count
        assert (pagination.total, pagination.page, pagination.pages) == (23, page, 3)
        actual.extend(item.id for item in pagination.items)
        html = response.get_data(as_text=True)
        assert f"{(page - 1) * 10 + 1}–{min(page * 10, 23)} no 23 ierakstiem" in html
        assert f"{page}. lapa no 3" in html
        links = PageLinks(html).links
        assert ("prev" in links) == (page > 1)
        assert ("next" in links) == (page < 3)
        if page < 3:
            assert parse_qs(urlsplit(links["next"]).query)["page"] == [str(page + 1)]
    assert actual == (list(reversed(ids[section])) if section == "orders" else ids[section])


@pytest.mark.parametrize("section", LISTS[:-1])
def test_admin_pagination_preserves_filters_and_sort_and_resets_on_search(admin_lists, section):
    app, client, ids = admin_lists
    query = "status=iesniegts&sort=date-asc" if section == "orders" else "q=Lapošana&status=active"
    with rendered_context(app) as captured:
        response = client.get(f"/admin/{section}?{query}&page=2")
    pagination = captured[-1]["pagination"]
    assert pagination.total == 21
    assert [item.id for item in pagination.items] == ids[section][10:20]
    html = response.get_data(as_text=True)
    for direction, expected_page in [("prev", "1"), ("next", "3")]:
        url = PageLinks(html).links[direction]
        args = parse_qs(urlsplit(url).query)
        assert args == dict(parse_qs(query), page=[expected_page])
        with rendered_context(app) as captured:
            assert client.get(url).status_code == 200
        assert captured[-1]["pagination"].page == int(expected_page)
    assert 'name="page"' not in html  # Submitting filters starts on page one.
    with rendered_context(app) as captured:
        client.get(f"/admin/{section}?{query}")
    assert captured[-1]["pagination"].page == 1
    if section == "products":
        assert captured[-1]["total"] == 23 and captured[-1]["active"] == 21


@pytest.mark.parametrize("section", LISTS)
def test_admin_pagination_clamps_after_records_are_removed_and_handles_empty(admin_lists, section):
    app, client, _ = admin_lists
    with rendered_context(app) as captured:
        assert client.get(f"/admin/{section}?status=all&page=1000000").status_code == 200
    assert captured[-1]["pagination"].page == 3
    if section == "categories":
        # Unlinked categories can disappear between requests.
        for product in db.session.scalars(db.select(Product)):
            product.category_id = 1
        db.session.flush()
        db.session.execute(db.delete(Category).where(Category.id != 1))
        db.session.commit()
        path = "/admin/categories?page=3"
    else:
        query = "status=apstiprināts" if section == "orders" else "q=NO-MATCH"
        path = f"/admin/{section}?{query}&page=3"
    with rendered_context(app) as captured:
        response = client.get(path)
    pagination = captured[-1]["pagination"]
    assert pagination.page == pagination.pages == 1
    assert pagination.total == (1 if section == "categories" else 0)
    assert not PageLinks(response.get_data(as_text=True)).links


@pytest.mark.parametrize("section", LISTS)
def test_all_admin_lists_reject_invalid_or_duplicate_page_numbers(admin_lists, section):
    _, client, _ = admin_lists
    for query in ["page=0", "page=-1", "page=", "page=NaN", "page=1.5", "page=1000001",
                  "page=999999999999", "page=1&page=2"]:
        assert client.get(f"/admin/{section}?{query}").status_code == 400
