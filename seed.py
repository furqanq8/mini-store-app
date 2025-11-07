from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Session

from app.db import engine, init_db
from app.models import (
    Customer,
    Item,
    ItemType,
    Purchase,
    PurchaseLine,
    Setting,
    StockMoveType,
    Supplier,
)
from app.services.inventory import add_stock_ledger_entry, create_stock_lot


def seed() -> None:
    init_db()
    with Session(engine) as session:
        if session.query(Item).count():  # type: ignore[attr-defined]
            print("Database already seeded")
            return
        # Settings
        session.add(Setting(key="vat_rate", value="15"))
        session.add(Setting(key="no_negative_stock", value="true"))

        supplier = Supplier(name="Acme Supplies", contact="John Doe", email="john@example.com")
        session.add(supplier)
        customer = Customer(name="Jane Smith", contact="555-0100", email="jane@example.com")
        session.add(customer)

        item1 = Item(name="Coffee Beans", sku="COF-001", barcode="1234567890123", item_type=ItemType.WEIGHT, default_price=Decimal("12.50"))
        item2 = Item(name="Tea Bags", sku="TEA-001", barcode="9876543210987", item_type=ItemType.COUNT, default_price=Decimal("4.00"))
        session.add(item1)
        session.add(item2)
        session.commit()

        purchase = Purchase(supplier_id=supplier.id, reference="PO-1001", date=date.today())
        session.add(purchase)
        session.commit()

        line1 = PurchaseLine(purchase_id=purchase.id, item_id=item1.id, quantity=Decimal("10"), unit_cost=Decimal("8.00"))
        line2 = PurchaseLine(purchase_id=purchase.id, item_id=item2.id, quantity=Decimal("100"), unit_cost=Decimal("2.00"))
        session.add(line1)
        session.add(line2)
        session.commit()

        create_stock_lot(session, line1)
        add_stock_ledger_entry(session, item1, ref_type=StockMoveType.PURCHASE, ref_id=purchase.id, quantity_delta=Decimal("10"), unit_cost=Decimal("8.00"))
        create_stock_lot(session, line2)
        add_stock_ledger_entry(session, item2, ref_type=StockMoveType.PURCHASE, ref_id=purchase.id, quantity_delta=Decimal("100"), unit_cost=Decimal("2.00"))
        session.commit()
        print("Seed data created")


if __name__ == "__main__":
    seed()
