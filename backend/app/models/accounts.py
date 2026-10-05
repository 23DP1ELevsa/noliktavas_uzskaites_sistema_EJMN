from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .common import CreatedMixin, IdentityMixin, ID_TYPE, TABLE_OPTIONS, active_column


class User(IdentityMixin, CreatedMixin, UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('user', 'admin')", name="valid_role"),
        TABLE_OPTIONS,
    )

    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user", server_default="user")
    is_active = active_column()

    company_profile = db.relationship("CompanyProfile", back_populates="user", uselist=False,
                                      passive_deletes="all")
    cart = db.relationship("Cart", back_populates="user", uselist=False,
                           passive_deletes="all")
    offers_created = db.relationship("Offer", back_populates="created_by_admin",
                                     passive_deletes="all")
    orders = db.relationship("Order", back_populates="user", foreign_keys="Order.user_id",
                             passive_deletes="all")
    orders_processed = db.relationship("Order", back_populates="processed_by_admin",
                                       foreign_keys="Order.processed_by_admin_id",
                                       passive_deletes="all")

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError("Password must contain at least 8 characters.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CompanyProfile(IdentityMixin, db.Model):
    __tablename__ = "company_profiles"
    __table_args__ = TABLE_OPTIONS

    user_id = db.Column(ID_TYPE, db.ForeignKey("users.id", ondelete="RESTRICT"),
                        nullable=False, unique=True)
    company_name = db.Column(db.String(255), nullable=False)
    registration_no = db.Column(db.String(50), nullable=False)
    vat_no = db.Column(db.String(50))
    phone = db.Column(db.String(50))
    address = db.Column(db.String(255), nullable=False)

    user = db.relationship("User", back_populates="company_profile")
    orders = db.relationship("Order", back_populates="company_profile", passive_deletes="all")
