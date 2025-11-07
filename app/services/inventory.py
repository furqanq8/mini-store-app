from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Deque, Iterable, Tuple

from sqlmodel import Session, select

from ..models import (
    CreditLedger,
    Item,
    ItemType,
    PurchaseLine,
    SaleLine,
    StockLedger,
    StockLot,
    StockMoveType,
)



@dataclass
class FifoResult:
    lines: list[Tuple[StockLot, Decimal, Decimal]]
    total_cost: Decimal


class StockError(Exception):
    pass


def quantize_quantity(item: Item, quantity: Decimal) -> Decimal:
    precision = Decimal("1") if item.item_type == ItemType.COUNT else Decimal("0.001")
    return quantity.quantize(precision, rounding=ROUND_HALF_UP)


def build_fifo_queue(session: Session, item_id: int) -> Deque[StockLot]:
    lots = session.exec(
        select(StockLot).where(StockLot.item_id == item_id, StockLot.remaining_quantity > 0)
    ).all()
    return deque(sorted(lots, key=lambda lot: lot.id))


def consume_fifo(session: Session, item: Item, quantity: Decimal) -> FifoResult:
    queue = build_fifo_queue(session, item.id)
    needed = quantize_quantity(item, quantity)
    consumed: list[Tuple[StockLot, Decimal, Decimal]] = []
    total_cost = Decimal("0")

    while needed > 0 and queue:
        lot = queue[0]
        take_qty = min(lot.remaining_quantity, needed)
        needed -= take_qty
        lot.remaining_quantity -= take_qty
        cost = take_qty * lot.unit_cost
        total_cost += cost
        consumed.append((lot, take_qty, cost))
        if lot.remaining_quantity <= Decimal("0"):
            queue.popleft()

    if needed > 0:
        raise StockError("Insufficient stock for FIFO consumption")

    for lot, _, _ in consumed:
        session.add(lot)

    return FifoResult(lines=consumed, total_cost=total_cost)


def create_stock_lot(session: Session, purchase_line: PurchaseLine) -> None:
    lot = StockLot(
        purchase_line_id=purchase_line.id,
        item_id=purchase_line.item_id,
        quantity=purchase_line.quantity,
        remaining_quantity=purchase_line.quantity,
        unit_cost=purchase_line.unit_cost,
    )
    session.add(lot)


def add_stock_ledger_entry(
    session: Session,
    item: Item,
    ref_type: StockMoveType,
    ref_id: int,
    quantity_delta: Decimal,
    unit_cost: Decimal,
) -> StockLedger:
    last_entry = session.exec(
        select(StockLedger)
        .where(StockLedger.item_id == item.id)
        .order_by(StockLedger.id.desc())
    ).first()
    running_qty = (last_entry.running_quantity if last_entry else Decimal("0")) + quantity_delta
    running_cost = (last_entry.running_cost if last_entry else Decimal("0")) + quantity_delta * unit_cost
    ledger = StockLedger(
        item_id=item.id,
        ref_type=ref_type,
        ref_id=ref_id,
        quantity_delta=quantity_delta,
        unit_cost=unit_cost,
        total_cost=quantity_delta * unit_cost,
        running_quantity=running_qty,
        running_cost=running_cost,
    )
    session.add(ledger)
    return ledger


def update_credit_ledger(
    session: Session, customer_id: int, ref_type: str, ref_id: int, amount: Decimal
) -> None:
    session.add(
        CreditLedger(
            customer_id=customer_id,
            ref_type=ref_type,
            ref_id=ref_id,
            amount=amount,
        )
    )


def ensure_stock_balance(session: Session, item: Item, required: Decimal, allow_negative: bool) -> None:
    stock = session.exec(
        select(StockLedger.running_quantity)
        .where(StockLedger.item_id == item.id)
        .order_by(StockLedger.id.desc())
    ).first()
    available = stock if stock is not None else Decimal("0")
    if not allow_negative and available < required:
        raise StockError(f"Insufficient stock for item {item.name}")


def calculate_customer_balance(session: Session, customer_id: int) -> Decimal:
    total = session.exec(
        select(CreditLedger.amount).where(CreditLedger.customer_id == customer_id)
    ).all()
    return sum(total, Decimal("0"))


def summarize_fifo_lines(lines: Iterable[Tuple[StockLot, Decimal, Decimal]]) -> Decimal:
    return sum((cost for _, _, cost in lines), Decimal("0"))
