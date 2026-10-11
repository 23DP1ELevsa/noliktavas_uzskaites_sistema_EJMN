from ..extensions import db
from ..models import Notification, User


def customer_details(order):
    if order.customer_snapshot:
        return order.customer_snapshot
    profile, user = order.company_profile, order.user
    return dict(company_name=profile.company_name, registration_no=profile.registration_no,
                vat_no=profile.vat_no or "", address=profile.address,
                delivery_address=profile.effective_delivery_address,
                full_name=user.full_name, email=user.email, phone=profile.phone or "", note="")


def notify_submission(order):
    db.session.flush()
    admins = db.session.scalars(db.select(User).where(User.role == "admin", User.is_active.is_(True))).all()
    for admin in admins:
        db.session.add(Notification(user_id=admin.id, order_id=order.id, kind="submitted",
                                    message=f"Saņemts jauns pieteikums #{order.id}. Tas gaida izskatīšanu."))
    if order.user_id not in {admin.id for admin in admins}:
        db.session.add(Notification(user_id=order.user_id, order_id=order.id, kind="submitted",
                                    message=f"Pieteikums #{order.id} iesniegts un nodots administratoram."))


def notify_decision(order):
    approved = order.status == "apstiprināts"
    kind = "approved" if approved else "declined"
    message = f"Pieteikums #{order.id} ir {order.status}."
    recipients = set(db.session.scalars(db.select(User.id).where(User.role == "admin", User.is_active.is_(True))).all())
    recipients.add(order.user_id)
    for user_id in recipients:
        db.session.add(Notification(user_id=user_id, order_id=order.id, kind=kind, message=message))
    db.session.execute(db.update(Notification).where(Notification.order_id == order.id,
                        Notification.kind == "submitted", Notification.user_id.in_(recipients)).values(is_read=True))
