from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import template_rendered

from backend.app.extensions import db
from backend.app.models import CompanyProfile, Notification, Order, User


class PaginationLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.kind = None
        self.links = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav":
            self.kind = attrs.get("data-profile-pagination")
        elif tag == "a" and self.kind:
            self.links[self.kind, attrs["rel"]] = attrs["href"]

    def handle_endtag(self, tag):
        if tag == "nav":
            self.kind = None


@contextmanager
def profile_context(app):
    captured = []

    def record(sender, template, context, **extra):
        if template.name == "auth/profile.html":
            captured.append(context)

    template_rendered.connect(record, app)
    try:
        yield captured
    finally:
        template_rendered.disconnect(record, app)


@pytest.fixture(params=["user", "admin"])
def profile_history(database_app, request):
    owner = User(email="profile-pages@example.test", full_name="Lapošanas lietotājs",
                 role=request.param, password_hash="unused")
    owner.company_profile = CompanyProfile(company_name="Lapošanas SIA", registration_no="40000000001",
                                            address="Rīga, Pārbaudes iela 1")
    other = User(email="private-pages@example.test", full_name="Cits lietotājs", password_hash="unused")
    other.company_profile = CompanyProfile(company_name="Privāts uzņēmums", registration_no="40000000002",
                                            address="Cita adrese")
    db.session.add_all([owner, other])
    db.session.flush()
    orders, notices = [], []
    for index in range(12):
        # Equal timestamps on the newest pair exercise the deterministic ID tie-breaker.
        timestamp = datetime(2026, 1, 1) + timedelta(days=min(index, 10))
        order = Order(user_id=owner.id, company_profile_id=owner.company_profile.id,
                      total_amount=Decimal("10.00"), created_at=timestamp)
        db.session.add(order)
        db.session.flush()
        notice = Notification(user_id=owner.id, order_id=order.id, kind="submitted",
                              message=f"Paziņojums {index + 1}", is_read=index != 0, created_at=timestamp)
        db.session.add(notice)
        db.session.flush()
        orders.append(order.id)
        notices.append(notice.id)
    private_order = Order(user_id=other.id, company_profile_id=other.company_profile.id,
                          total_amount=Decimal("99.00"), created_at=datetime(2027, 1, 1))
    db.session.add(private_order)
    db.session.flush()
    db.session.add(Notification(user_id=other.id, order_id=private_order.id, kind="submitted",
                                message="PRIVĀTS PAZIŅOJUMS", created_at=datetime(2027, 1, 1)))
    db.session.commit()
    client = database_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"], session["_fresh"] = str(owner.id), True
    return database_app, client, orders, notices, other.id


def get_profile(data, path="/auth/profile"):
    app, client, *_ = data
    with profile_context(app) as captured:
        response = client.get(path)
    assert response.status_code == 200
    return response.get_data(as_text=True), captured[0]


def test_profile_starts_with_five_newest_records_and_counts_only_the_owner(profile_history):
    _, _, orders, notices, other_id = profile_history
    html, context = get_profile(profile_history, f"/auth/profile?user_id={other_id}")

    assert [item.id for item in context["notifications"]] == list(reversed(notices[-5:]))
    assert [item.id for item in context["orders"]] == list(reversed(orders[-5:]))
    assert context["unread"] == 1  # The oldest unread notice must not displace newer notices.
    assert context["notification_pagination"]["total"] == 12
    assert context["order_pagination"]["total"] == 12
    assert "PRIVĀTS PAZIŅOJUMS" not in html
    assert html.count('class="profile-order-row"') == 5
    assert html.count('class="notification-row ') == 5
    links = PaginationLinks(html).links
    assert ("notifications", "prev") not in links and ("orders", "prev") not in links
    assert parse_qs(urlsplit(links["notifications", "next"]).query) == {
        "notifications_page": ["2"], "orders_page": ["1"]}


def test_profile_lists_page_independently_and_expose_both_directions(profile_history):
    _, _, orders, notices, _ = profile_history
    html, context = get_profile(profile_history, "/auth/profile?notifications_page=2&orders_page=3")

    assert [item.id for item in context["notifications"]] == list(reversed(notices[2:7]))
    assert [item.id for item in context["orders"]] == list(reversed(orders[:2]))
    links = PaginationLinks(html).links
    for direction, target in (("prev", "1"), ("next", "3")):
        url = urlsplit(links["notifications", direction])
        assert parse_qs(url.query) == {"notifications_page": [target], "orders_page": ["3"]}
        assert url.fragment == "profile-notifications-content"
    assert ("orders", "next") not in links
    order_previous = urlsplit(links["orders", "prev"])
    assert parse_qs(order_previous.query) == {"notifications_page": ["2"], "orders_page": ["2"]}
    assert order_previous.fragment == "profile-orders-content"
    _, next_context = get_profile(profile_history, links["notifications", "next"])
    assert [item.id for item in next_context["notifications"]] == list(reversed(notices[:2]))
    assert [item.id for item in next_context["orders"]] == list(reversed(orders[:2]))


def test_profile_clamps_large_valid_pages_to_the_last_owned_page(profile_history):
    _, _, orders, notices, _ = profile_history
    _, context = get_profile(profile_history, "/auth/profile?notifications_page=1000000&orders_page=1000000")

    assert context["notification_pagination"]["page"] == context["order_pagination"]["page"] == 3
    assert [item.id for item in context["notifications"]] == list(reversed(notices[:2]))
    assert [item.id for item in context["orders"]] == list(reversed(orders[:2]))


@pytest.mark.parametrize("query", [
    "notifications_page=0", "orders_page=-1", "notifications_page=1.5", "orders_page=NaN",
    "notifications_page=", "orders_page=9999999", "notifications_page=2&notifications_page=3",
    "orders_page=1&orders_page=1",
])
def test_profile_rejects_invalid_and_duplicate_page_values(database_app, query):
    user = User(email="page-validation@example.test", full_name="Lapu pārbaude", password_hash="unused")
    db.session.add(user)
    db.session.commit()
    client = database_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"], session["_fresh"] = str(user.id), True

    response = client.get("/auth/profile?" + query)

    assert response.status_code == 400
    assert "Nederīgs profila sadaļas lapas numurs." in response.get_data(as_text=True)


def test_empty_profile_keeps_empty_states_without_pagination_links(database_app):
    user = User(email="empty-pages@example.test", full_name="Tukšs profils", password_hash="unused")
    db.session.add(user)
    db.session.commit()
    client = database_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"], session["_fresh"] = str(user.id), True
    with profile_context(database_app) as captured:
        response = client.get("/auth/profile?notifications_page=99&orders_page=99")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Pagaidām nav paziņojumu." in html and "Jums vēl nav pieteikumu." in html
    assert not PaginationLinks(html).links
    assert captured[0]["notification_pagination"]["page"] == captured[0]["order_pagination"]["page"] == 1
