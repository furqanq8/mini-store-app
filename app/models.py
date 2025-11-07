from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class ItemType(str, enum.Enum):
    COUNT = "COUNT"
    WEIGHT = "WEIGHT"


class StockMoveType(str, enum.Enum):
    PURCHASE = "PURCHASE"
    SALE = "SALE"
    ADJUSTMENT = "ADJUSTMENT"


class PaymentType(str, enum.Enum):
    CASH = "CASH"
    CREDIT = "CREDIT"


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    contact: Optional[str] = None
    email: Optional[str] = None

    purchases: list["Purchase"] = Relationship(back_populates="supplier")


class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    contact: Optional[str] = None
    email: Optional[str] = None

    sales: list["Sale"] = Relationship(back_populates="customer")
    payments: list["CustomerPayment"] = Relationship(back_populates="customer")


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    sku: str = Field(index=True, unique=True)
    barcode: Optional[str] = Field(default=None, index=True)
    item_type: ItemType
    default_price: Decimal = Field(
        default=Decimal("0"), sa_column_kwargs={"type_": "NUMERIC(12,2)"}
    )
    allow_negative: bool = Field(default=False)

    purchase_lines: list["PurchaseLine"] = Relationship(back_populates="item")
    sale_lines: list["SaleLine"] = Relationship(back_populates="item")


class Purchase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    reference: str
    date: date = Field(default_factory=date.today)
    notes: Optional[str] = None

    supplier: Optional[Supplier] = Relationship(back_populates="purchases")
    lines: list["PurchaseLine"] = Relationship(back_populates="purchase")


class PurchaseLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_id: int = Field(foreign_key="purchase.id")
    item_id: int = Field(foreign_key="item.id")
    quantity: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    unit_cost: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})

    purchase: Purchase = Relationship(back_populates="lines")
    item: Item = Relationship(back_populates="purchase_lines")
    stock_lots: list["StockLot"] = Relationship(back_populates="purchase_line")


class Sale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    reference: str
    date: date = Field(default_factory=date.today)
    payment_type: PaymentType = Field(default=PaymentType.CASH)
    vat_rate: Decimal = Field(
        default=Decimal("0"), sa_column_kwargs={"type_": "NUMERIC(5,2)"}
    )

    customer: Optional[Customer] = Relationship(back_populates="sales")
    lines: list["SaleLine"] = Relationship(back_populates="sale")


class SaleLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: int = Field(foreign_key="sale.id")
    item_id: int = Field(foreign_key="item.id")
    quantity: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    unit_price: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    unit_cost: Decimal = Field(
        default=Decimal("0"), sa_column_kwargs={"type_": "NUMERIC(14,4)"}
    )

    sale: Sale = Relationship(back_populates="lines")
    item: Item = Relationship(back_populates="sale_lines")


class CustomerPayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    date: date = Field(default_factory=date.today)
    amount: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,2)"})
    reference: Optional[str] = None

    customer: Customer = Relationship(back_populates="payments")


class StockLot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_line_id: int = Field(foreign_key="purchaseline.id")
    item_id: int = Field(foreign_key="item.id")
    quantity: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    remaining_quantity: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    unit_cost: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})

    purchase_line: PurchaseLine = Relationship(back_populates="stock_lots")


class StockLedger(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id")
    ref_type: StockMoveType
    ref_id: int
    date: datetime = Field(default_factory=datetime.utcnow)
    quantity_delta: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    unit_cost: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    total_cost: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    running_quantity: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})
    running_cost: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,4)"})


class CreditLedger(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    ref_type: str
    ref_id: int
    date: date = Field(default_factory=date.today)
    amount: Decimal = Field(sa_column_kwargs={"type_": "NUMERIC(14,2)"})
