"""Consistent, bounded pagination for administrator lists."""

from dataclasses import dataclass
import re

from flask import abort, request, url_for

from ..extensions import db


@dataclass
class AdminPage:
    items: list
    total: int
    page: int
    pages: int
    previous_url: str | None
    next_url: str | None

    @property
    def first(self):
        return (self.page - 1) * 10 + 1 if self.total else 0

    @property
    def last(self):
        return min(self.page * 10, self.total)


def paginate_admin(query, **filters):
    values = request.args.getlist("page")
    value = values[0] if values else "1"
    if len(values) > 1 or not re.fullmatch(r"[0-9]{1,7}", value) or not 1 <= int(value) <= 1000000:
        abort(400, description="Nederīgs lapas numurs.")
    total = db.session.scalar(db.select(db.func.count()).select_from(query.order_by(None).subquery()))
    pages = max(1, (total + 9) // 10)
    page = min(int(value), pages)
    items = db.session.scalars(query.limit(10).offset((page - 1) * 10)).all()
    return AdminPage(
        items=items, total=total, page=page, pages=pages,
        previous_url=url_for(request.endpoint, **filters, page=page - 1) if page > 1 else None,
        next_url=url_for(request.endpoint, **filters, page=page + 1) if page < pages else None,
    )
