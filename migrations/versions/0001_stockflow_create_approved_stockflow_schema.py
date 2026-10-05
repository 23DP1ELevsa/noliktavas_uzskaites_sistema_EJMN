"""Create approved StockFlow schema

Revision ID: 0001_stockflow
Revises: 
Create Date: 2026-10-04 11:15:36.501584

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '0001_stockflow'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Keep this schema frozen; future changes belong in new revisions.
    op.create_table('categories',
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_categories')),
    sa.UniqueConstraint('name', name=op.f('uq_categories_name')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('role', sa.String(length=20), server_default='user', nullable=False),
    sa.Column('is_active', sa.Boolean(create_constraint=True, name='is_active_boolean'), server_default=sa.text('1'), nullable=False),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("role IN ('user', 'admin')", name=op.f('ck_users_valid_role')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('carts',
    sa.Column('user_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("status = 'active'", name=op.f('ck_carts_valid_status')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_carts_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_carts')),
    sa.UniqueConstraint('user_id', name=op.f('uq_carts_user_id')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('company_profiles',
    sa.Column('user_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('registration_no', sa.String(length=50), nullable=False),
    sa.Column('vat_no', sa.String(length=50), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_company_profiles_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_company_profiles')),
    sa.UniqueConstraint('user_id', name=op.f('uq_company_profiles_user_id')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('products',
    sa.Column('category_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('sku', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('brand', sa.String(length=100), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('unit', sa.String(length=30), server_default='gab.', nullable=False),
    sa.Column('is_active', sa.Boolean(create_constraint=True, name='is_active_boolean'), server_default=sa.text('1'), nullable=False),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_products_category_id_categories'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    sa.UniqueConstraint('sku', name=op.f('uq_products_sku')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_products_category_id'), ['category_id'], unique=False)

    op.create_table('offers',
    sa.Column('product_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('created_by_admin_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('supplier_name', sa.String(length=255), nullable=False),
    sa.Column('supplier_sku', sa.String(length=100), nullable=True),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('vat_included', sa.Boolean(create_constraint=True, name='vat_included_boolean'), nullable=False),
    sa.Column('min_order_qty', sa.Integer(), server_default='1', nullable=False),
    sa.Column('stock_qty', sa.Integer(), server_default='0', nullable=False),
    sa.Column('delivery_price', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
    sa.Column('delivery_days', sa.Integer(), server_default='0', nullable=False),
    sa.Column('data_source', sa.String(length=20), server_default='manual', nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('is_active', sa.Boolean(create_constraint=True, name='is_active_boolean'), server_default=sa.text('1'), nullable=False),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.CheckConstraint("data_source IN ('manual', 'CSV', 'JSON', 'API')", name=op.f('ck_offers_valid_data_source')),
    sa.CheckConstraint('delivery_days >= 0', name=op.f('ck_offers_delivery_days_nonnegative')),
    sa.CheckConstraint('delivery_price >= 0', name=op.f('ck_offers_delivery_price_nonnegative')),
    sa.CheckConstraint('min_order_qty >= 1', name=op.f('ck_offers_min_order_qty_positive')),
    sa.CheckConstraint('stock_qty >= 0', name=op.f('ck_offers_stock_qty_nonnegative')),
    sa.CheckConstraint('unit_price >= 0', name=op.f('ck_offers_unit_price_nonnegative')),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['users.id'], name=op.f('fk_offers_created_by_admin_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_offers_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_offers')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('offers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_offers_created_by_admin_id'), ['created_by_admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_offers_product_id'), ['product_id'], unique=False)

    op.create_table('orders',
    sa.Column('user_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('company_profile_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('status', sa.String(length=30), server_default='iesniegts', nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('admin_note', sa.Text(), nullable=True),
    sa.Column('processed_by_admin_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('processed_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("status IN ('iesniegts', 'apstiprināts', 'noraidīts')", name=op.f('ck_orders_valid_status')),
    sa.CheckConstraint('total_amount >= 0', name=op.f('ck_orders_total_amount_nonnegative')),
    sa.ForeignKeyConstraint(['company_profile_id'], ['company_profiles.id'], name=op.f('fk_orders_company_profile_id_company_profiles'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['processed_by_admin_id'], ['users.id'], name=op.f('fk_orders_processed_by_admin_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_orders_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_orders')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_orders_company_profile_id'), ['company_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_processed_by_admin_id'), ['processed_by_admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_user_id'), ['user_id'], unique=False)

    op.create_table('cart_items',
    sa.Column('cart_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('offer_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_cart_items_quantity_positive')),
    sa.ForeignKeyConstraint(['cart_id'], ['carts.id'], name=op.f('fk_cart_items_cart_id_carts'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], name=op.f('fk_cart_items_offer_id_offers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cart_items')),
    sa.UniqueConstraint('cart_id', 'offer_id', name='uq_cart_items_cart_offer'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('cart_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cart_items_offer_id'), ['offer_id'], unique=False)

    op.create_table('order_items',
    sa.Column('order_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('offer_id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), nullable=True),
    sa.Column('product_name', sa.String(length=255), nullable=False),
    sa.Column('supplier_name', sa.String(length=255), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('delivery_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('line_total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('vat_included', sa.Boolean(create_constraint=True, name='vat_included_boolean'), nullable=False),
    sa.Column('id', sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), 'mysql').with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.CheckConstraint('delivery_price >= 0', name=op.f('ck_order_items_delivery_price_nonnegative')),
    sa.CheckConstraint('line_total >= 0', name=op.f('ck_order_items_line_total_nonnegative')),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_order_items_quantity_positive')),
    sa.CheckConstraint('unit_price >= 0', name=op.f('ck_order_items_unit_price_nonnegative')),
    sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], name=op.f('fk_order_items_offer_id_offers'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_order_items_order_id_orders'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_items')),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_order_items_offer_id'), ['offer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_order_items_order_id'), ['order_id'], unique=False)




def downgrade():
    # Keep this schema frozen; future changes belong in new revisions.
    op.drop_table('order_items')
    op.drop_table('cart_items')
    op.drop_table('orders')
    op.drop_table('offers')
    op.drop_table('products')
    op.drop_table('company_profiles')
    op.drop_table('carts')
    op.drop_table('users')
    op.drop_table('categories')

