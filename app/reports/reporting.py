from __future__ import annotations

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Session, func, select

from ..models import CreditLedger, Customer, Item, Purchase, Sale, StockLedger


def _current_inventory(session: Session) -> list[dict]:
    latest: dict[int, StockLedger] = {}
    entries = session.exec(
        select(StockLedger).order_by(StockLedger.item_id, StockLedger.id)
    ).all()
    for entry in entries:
        latest[entry.item_id] = entry
    results: list[dict] = []
    for item_id, entry in latest.items():
        item = session.get(Item, item_id)
        if not item:
            continue
        cost = entry.running_cost if entry.running_quantity else Decimal("0")
        unit_cost = cost / entry.running_quantity if entry.running_quantity else Decimal("0")
        results.append(
            {
                "item": item,
                "quantity": entry.running_quantity,
                "unit_cost": unit_cost,
                "value": entry.running_quantity * unit_cost,
            }
        )
    return results


def inventory_on_hand(session: Session) -> list[dict]:
    return _current_inventory(session)


def purchases_in_month(session: Session, start: date, end: date) -> list[Purchase]:
    return session.exec(
        select(Purchase).where(Purchase.date >= start, Purchase.date <= end)
    ).all()


def sales_in_month(session: Session, start: date, end: date) -> list[Sale]:
    return session.exec(select(Sale).where(Sale.date >= start, Sale.date <= end)).all()


def credit_aging(session: Session) -> list[dict]:
    balances = session.exec(
        select(
            CreditLedger.customer_id,
            func.sum(CreditLedger.amount),
        ).group_by(CreditLedger.customer_id)
    ).all()
    results: list[dict] = []
    for customer_id, balance in balances:
        customer = session.get(Customer, customer_id)
        if not customer:
            continue
        results.append({"customer": customer, "balance": Decimal(balance or 0)})
    return results


def profit_summary(session: Session, start: date, end: date) -> dict:
    sales_total = Decimal("0")
    cogs_total = Decimal("0")
    sales = sales_in_month(session, start, end)
    for sale in sales:
        line_total = sum((line.quantity * line.unit_price for line in sale.lines), Decimal("0"))
        sales_total += line_total
        cogs_total += sum((line.quantity * line.unit_cost for line in sale.lines), Decimal("0"))
    return {
        "sales": sales_total,
        "cogs": cogs_total,
        "gross_profit": sales_total - cogs_total,
    }
