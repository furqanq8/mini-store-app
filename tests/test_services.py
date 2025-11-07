from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models import Customer, Item, ItemType, Purchase, PurchaseLine
from app.services.inventory import (
    calculate_customer_balance,
    consume_fifo,
    create_stock_lot,
    update_credit_ledger,
)


def test_fifo_consumption(session):
    item = Item(name="Widget", sku="W1", barcode="111", item_type=ItemType.COUNT, default_price=Decimal("5.00"))
    purchase = Purchase(reference="PO1", date=date.today())
    session.add(item)
    session.add(purchase)
    session.commit()

    line1 = PurchaseLine(purchase_id=purchase.id, item_id=item.id, quantity=Decimal("5"), unit_cost=Decimal("10"))
    line2 = PurchaseLine(purchase_id=purchase.id, item_id=item.id, quantity=Decimal("7"), unit_cost=Decimal("12"))
    session.add(line1)
    session.add(line2)
    session.commit()

    create_stock_lot(session, line1)
    create_stock_lot(session, line2)
    session.commit()

    result = consume_fifo(session, item, Decimal("8"))
    assert len(result.lines) == 2
    lot1, qty1, cost1 = result.lines[0]
    lot2, qty2, cost2 = result.lines[1]
    assert qty1 == Decimal("5")
    assert qty2 == Decimal("3")
    assert cost1 == Decimal("50")
    assert cost2 == Decimal("36")
    assert result.total_cost == Decimal("86")


def test_credit_balance_updates(session):
    customer = Customer(name="Acme Corp")
    session.add(customer)
    session.commit()

    update_credit_ledger(session, customer.id, "SALE", 1, Decimal("150.00"))
    update_credit_ledger(session, customer.id, "PAYMENT", 2, Decimal("-50.00"))
    session.commit()

    balance = calculate_customer_balance(session, customer.id)
    assert balance == Decimal("100.00")
