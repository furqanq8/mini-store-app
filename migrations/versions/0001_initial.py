from __future__ import annotations

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "setting",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.String(), nullable=False),
    )
    op.create_table(
        "supplier",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("contact", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
    )
    op.create_table(
        "customer",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("contact", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
    )
    op.create_table(
        "item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sku", sa.String(), nullable=False, unique=True),
        sa.Column("barcode", sa.String(), nullable=True),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("default_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("allow_negative", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_item_sku", "item", ["sku"], unique=True)
    op.create_index("ix_item_barcode", "item", ["barcode"], unique=False)
    op.create_table(
        "purchase",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id")),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
    )
    op.create_table(
        "sale",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id")),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("payment_type", sa.String(), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "customerpayment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(), nullable=True),
    )
    op.create_table(
        "purchaseline",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchase.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("item.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
    )
    op.create_table(
        "saleline",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sale.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("item.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
    )
    op.create_table(
        "stocklot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_line_id", sa.Integer(), sa.ForeignKey("purchaseline.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("item.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
    )
    op.create_table(
        "stockledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("item.id"), nullable=False),
        sa.Column("ref_type", sa.String(), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("total_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("running_quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("running_cost", sa.Numeric(14, 4), nullable=False),
    )
    op.create_table(
        "creditledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("ref_type", sa.String(), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("creditledger")
    op.drop_table("stockledger")
    op.drop_table("stocklot")
    op.drop_table("saleline")
    op.drop_table("purchaseline")
    op.drop_table("customerpayment")
    op.drop_table("sale")
    op.drop_table("purchase")
    op.drop_index("ix_item_barcode", table_name="item")
    op.drop_index("ix_item_sku", table_name="item")
    op.drop_table("item")
    op.drop_table("customer")
    op.drop_table("supplier")
    op.drop_table("setting")
