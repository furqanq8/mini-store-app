from __future__ import annotations

import calendar
import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fpdf import FPDF
from sqlalchemy import func, or_
from sqlmodel import Session, select

from .db import get_session, init_db
from .models import (
    CreditLedger,
    Customer,
    CustomerPayment,
    Item,
    ItemType,
    PaymentType,
    StockMoveType,
    Purchase,
    PurchaseLine,
    Sale,
    SaleLine,
    Setting,
    Supplier,
)
from .reports.reporting import (
    credit_aging,
    inventory_on_hand,
    profit_summary,
    purchases_in_month,
    sales_in_month,
)
from .services.inventory import (
    StockError,
    add_stock_ledger_entry,
    consume_fifo,
    create_stock_lot,
    ensure_stock_balance,
    quantize_quantity,
    update_credit_ledger,
)

app = FastAPI(title="Mini Store App")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def get_settings(session: Session) -> dict[str, str]:
    settings = session.exec(select(Setting)).all()
    return {setting.key: setting.value for setting in settings}


def get_setting(session: Session, key: str, default: str) -> str:
    return get_settings(session).get(key, default)


def parse_decimal(value: Any, fallback: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=f"Invalid decimal value {value}") from exc


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = session.exec(select(Item)).all()
    purchases = session.exec(select(Purchase)).all()
    sales = session.exec(select(Sale)).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "item_count": len(items),
            "purchase_count": len(purchases),
            "sale_count": len(sales),
        },
    )


# Item CRUD
@app.get("/items", response_class=HTMLResponse)
def list_items(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = session.exec(select(Item)).all()
    return templates.TemplateResponse("items/list.html", {"request": request, "items": items})


@app.get("/items/new", response_class=HTMLResponse)
def new_item(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "items/form.html", {"request": request, "item": None, "types": list(ItemType)}
    )


@app.get("/items/{item_id}/edit", response_class=HTMLResponse)
def edit_item(item_id: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "items/form.html", {"request": request, "item": item, "types": list(ItemType)}
    )


@app.post("/items")
def create_item(
    name: str = Form(...),
    sku: str = Form(...),
    barcode: str | None = Form(None),
    item_type: ItemType = Form(...),
    default_price: Decimal = Form(Decimal("0")),
    allow_negative: bool = Form(False),
    session: Session = Depends(get_session),
):
    item = Item(
        name=name,
        sku=sku,
        barcode=barcode,
        item_type=item_type,
        default_price=default_price,
        allow_negative=allow_negative,
    )
    session.add(item)
    session.commit()
    return RedirectResponse("/items", status_code=303)


@app.post("/items/{item_id}")
def update_item(
    item_id: int,
    name: str = Form(...),
    sku: str = Form(...),
    barcode: str | None = Form(None),
    item_type: ItemType = Form(...),
    default_price: Decimal = Form(Decimal("0")),
    allow_negative: bool = Form(False),
    session: Session = Depends(get_session),
):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404)
    item.name = name
    item.sku = sku
    item.barcode = barcode
    item.item_type = item_type
    item.default_price = default_price
    item.allow_negative = allow_negative
    session.add(item)
    session.commit()
    return RedirectResponse("/items", status_code=303)


@app.post("/items/{item_id}/delete")
def delete_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404)
    session.delete(item)
    session.commit()
    return RedirectResponse("/items", status_code=303)


@app.get("/items/search", response_class=HTMLResponse)
def search_item(q: str, session: Session = Depends(get_session)) -> HTMLResponse:
    stmt = select(Item).where(
        or_(Item.sku == q, Item.barcode == q, Item.name.contains(q))
    )
    results = session.exec(stmt).all()
    html = ['<ul>']
    for item in results:
        html.append(f'<li>{item.name} (SKU: {item.sku}) - Price {item.default_price}</li>')
    if not results:
        html.append('<li>No matches</li>')
    html.append('</ul>')
    return HTMLResponse("
".join(html))


# Supplier CRUD
@app.get("/suppliers", response_class=HTMLResponse)
def list_suppliers(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    suppliers = session.exec(select(Supplier)).all()
    return templates.TemplateResponse(
        "suppliers/list.html", {"request": request, "suppliers": suppliers}
    )


@app.get("/suppliers/new", response_class=HTMLResponse)
def new_supplier(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "suppliers/form.html", {"request": request, "supplier": None}
    )


@app.get("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
def edit_supplier(
    supplier_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "suppliers/form.html", {"request": request, "supplier": supplier}
    )


@app.post("/suppliers")
def create_supplier(
    name: str = Form(...),
    contact: str | None = Form(None),
    email: str | None = Form(None),
    session: Session = Depends(get_session),
):
    supplier = Supplier(name=name, contact=contact, email=email)
    session.add(supplier)
    session.commit()
    return RedirectResponse("/suppliers", status_code=303)


@app.post("/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: int,
    name: str = Form(...),
    contact: str | None = Form(None),
    email: str | None = Form(None),
    session: Session = Depends(get_session),
):
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404)
    supplier.name = name
    supplier.contact = contact
    supplier.email = email
    session.add(supplier)
    session.commit()
    return RedirectResponse("/suppliers", status_code=303)


@app.post("/suppliers/{supplier_id}/delete")
def delete_supplier(supplier_id: int, session: Session = Depends(get_session)):
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404)
    session.delete(supplier)
    session.commit()
    return RedirectResponse("/suppliers", status_code=303)


# Customer CRUD
@app.get("/customers", response_class=HTMLResponse)
def list_customers(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    customers = session.exec(select(Customer)).all()
    balances = {}
    for customer in customers:
        result = session.exec(
            select(func.sum(CreditLedger.amount)).where(CreditLedger.customer_id == customer.id)
        ).first()
        amount = result[0] if result else 0
        balances[customer.id] = Decimal(amount or 0)
    return templates.TemplateResponse(
        "customers/list.html",
        {"request": request, "customers": customers, "balances": balances},
    )


@app.get("/customers/new", response_class=HTMLResponse)
def new_customer(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "customers/form.html", {"request": request, "customer": None}
    )


@app.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
def edit_customer(
    customer_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "customers/form.html", {"request": request, "customer": customer}
    )


@app.post("/customers")
def create_customer(
    name: str = Form(...),
    contact: str | None = Form(None),
    email: str | None = Form(None),
    session: Session = Depends(get_session),
):
    customer = Customer(name=name, contact=contact, email=email)
    session.add(customer)
    session.commit()
    return RedirectResponse("/customers", status_code=303)


@app.post("/customers/{customer_id}")
def update_customer(
    customer_id: int,
    name: str = Form(...),
    contact: str | None = Form(None),
    email: str | None = Form(None),
    session: Session = Depends(get_session),
):
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404)
    customer.name = name
    customer.contact = contact
    customer.email = email
    session.add(customer)
    session.commit()
    return RedirectResponse("/customers", status_code=303)


@app.post("/customers/{customer_id}/delete")
def delete_customer(customer_id: int, session: Session = Depends(get_session)):
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404)
    session.delete(customer)
    session.commit()
    return RedirectResponse("/customers", status_code=303)


# Purchases
@app.get("/purchases", response_class=HTMLResponse)
def list_purchases(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    purchases = session.exec(select(Purchase)).all()
    suppliers = {supplier.id: supplier for supplier in session.exec(select(Supplier)).all()}
    return templates.TemplateResponse(
        "purchases/list.html",
        {"request": request, "purchases": purchases, "suppliers": suppliers},
    )


@app.get("/purchases/new", response_class=HTMLResponse)
def new_purchase(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    suppliers = session.exec(select(Supplier)).all()
    items = session.exec(select(Item)).all()
    return templates.TemplateResponse(
        "purchases/form.html",
        {
            "request": request,
            "suppliers": suppliers,
            "items": items,
            "today": date.today(),
        },
    )


@app.post("/purchases")
async def create_purchase(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    supplier_id = form.get("supplier_id")
    reference = form.get("reference")
    date_value = form.get("date")
    notes = form.get("notes")
    if not reference:
        raise HTTPException(status_code=400, detail="Reference required")
    purchase = Purchase(
        supplier_id=int(supplier_id) if supplier_id else None,
        reference=reference,
        date=date.fromisoformat(date_value) if date_value else date.today(),
        notes=notes,
    )
    session.add(purchase)
    session.flush()

    index = 0
    while True:
        item_id = form.get(f"lines-{index}-item_id")
        if not item_id:
            break
        quantity = parse_decimal(form.get(f"lines-{index}-quantity"))
        unit_cost = parse_decimal(form.get(f"lines-{index}-unit_cost"))
        line = PurchaseLine(
            purchase_id=purchase.id,
            item_id=int(item_id),
            quantity=quantity,
            unit_cost=unit_cost,
        )
        session.add(line)
        session.flush()
        create_stock_lot(session, line)
        item = session.get(Item, line.item_id)
        if item:
            add_stock_ledger_entry(
                session,
                item,
                ref_type=StockMoveType.PURCHASE,
                ref_id=purchase.id,
                quantity_delta=quantity,
                unit_cost=unit_cost,
            )
        index += 1

    session.commit()
    return RedirectResponse("/purchases", status_code=303)


# Sales
@app.get("/sales", response_class=HTMLResponse)
def list_sales(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    sales = session.exec(select(Sale)).all()
    customers = {customer.id: customer for customer in session.exec(select(Customer)).all()}
    return templates.TemplateResponse(
        "sales/list.html",
        {"request": request, "sales": sales, "customers": customers},
    )


@app.get("/sales/new", response_class=HTMLResponse)
def new_sale(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    customers = session.exec(select(Customer)).all()
    items = session.exec(select(Item)).all()
    vat_rate = Decimal(get_setting(session, "vat_rate", "0"))
    return templates.TemplateResponse(
        "sales/form.html",
        {
            "request": request,
            "customers": customers,
            "items": items,
            "vat_rate": vat_rate,
            "today": date.today(),
        },
    )


@app.post("/sales")
async def create_sale(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    customer_id = form.get("customer_id")
    reference = form.get("reference")
    date_value = form.get("date")
    payment_type = PaymentType(form.get("payment_type", PaymentType.CASH))
    vat_rate = parse_decimal(form.get("vat_rate") or get_setting(session, "vat_rate", "0"))
    if vat_rate < 0 or vat_rate > 15:
        raise HTTPException(status_code=400, detail="VAT rate must be between 0 and 15")
    if not reference:
        raise HTTPException(status_code=400, detail="Reference required")

    sale = Sale(
        customer_id=int(customer_id) if customer_id else None,
        reference=reference,
        date=date.fromisoformat(date_value) if date_value else date.today(),
        payment_type=payment_type,
        vat_rate=vat_rate,
    )
    session.add(sale)
    session.flush()

    no_negative = get_setting(session, "no_negative_stock", "true").lower() == "true"

    subtotal = Decimal("0")
    total_cogs = Decimal("0")
    index = 0
    while True:
        item_id = form.get(f"lines-{index}-item_id")
        if not item_id:
            break
        item = session.get(Item, int(item_id))
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        quantity = parse_decimal(form.get(f"lines-{index}-quantity"))
        quantity = quantize_quantity(item, quantity)
        unit_price = parse_decimal(form.get(f"lines-{index}-unit_price") or item.default_price)
        if no_negative and not item.allow_negative:
            try:
                ensure_stock_balance(session, item, quantity, allow_negative=False)
            except StockError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        try:
            fifo_result = consume_fifo(session, item, quantity)
        except StockError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        total_cost = fifo_result.total_cost
        unit_cost = total_cost / quantity if quantity else Decimal("0")
        line = SaleLine(
            sale_id=sale.id,
            item_id=item.id,
            quantity=quantity,
            unit_price=unit_price,
            unit_cost=unit_cost,
        )
        session.add(line)
        add_stock_ledger_entry(
            session,
            item,
            ref_type=StockMoveType.SALE,
            ref_id=sale.id,
            quantity_delta=-quantity,
            unit_cost=unit_cost,
        )
        subtotal += quantity * unit_price
        total_cogs += total_cost
        index += 1

    vat_amount = subtotal * vat_rate / Decimal("100")
    total_sale = subtotal + vat_amount

    if sale.customer_id and payment_type == PaymentType.CREDIT:
        update_credit_ledger(session, sale.customer_id, "SALE", sale.id, total_sale)

    session.commit()
    return RedirectResponse("/sales", status_code=303)


# Payments
@app.get("/payments", response_class=HTMLResponse)
def list_payments(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    payments = session.exec(select(CustomerPayment)).all()
    customers = {customer.id: customer for customer in session.exec(select(Customer)).all()}
    return templates.TemplateResponse(
        "payments/list.html",
        {"request": request, "payments": payments, "customers": customers},
    )


@app.get("/payments/new", response_class=HTMLResponse)
def new_payment(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    customers = session.exec(select(Customer)).all()
    return templates.TemplateResponse(
        "payments/form.html", {"request": request, "customers": customers, "today": date.today()}
    )


@app.post("/payments")
async def create_payment(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    customer_id = form.get("customer_id")
    amount = parse_decimal(form.get("amount"))
    reference = form.get("reference")
    date_value = form.get("date")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer required")
    payment = CustomerPayment(
        customer_id=int(customer_id),
        amount=amount,
        reference=reference,
        date=date.fromisoformat(date_value) if date_value else date.today(),
    )
    session.add(payment)
    update_credit_ledger(session, payment.customer_id, "PAYMENT", payment.id, -amount)
    session.commit()
    return RedirectResponse("/payments", status_code=303)


# Reports and Exports
@app.get("/reports/inventory", response_class=HTMLResponse)
def inventory_report(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    inventory = inventory_on_hand(session)
    return templates.TemplateResponse(
        "reports/inventory.html", {"request": request, "inventory": inventory}
    )


@app.get("/reports/inventory.csv")
def inventory_csv(session: Session = Depends(get_session)) -> StreamingResponse:
    inventory = inventory_on_hand(session)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Item", "Quantity", "Unit Cost", "Value"])
    for entry in inventory:
        writer.writerow(
            [
                entry["item"].name,
                entry["quantity"],
                f"{entry['unit_cost']:.2f}",
                f"{entry['value']:.2f}",
            ]
        )
    buffer.seek(0)
    headers = {"Content-Disposition": "attachment; filename=inventory.csv"}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)


@app.get("/reports/inventory.pdf")
def inventory_pdf(session: Session = Depends(get_session)) -> StreamingResponse:
    inventory = inventory_on_hand(session)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Inventory On Hand", ln=True, align="C")
    pdf.set_font("Arial", size=10)
    for entry in inventory:
        line = f"{entry['item'].name} - Qty: {entry['quantity']} Value: {entry['value']:.2f}"
        pdf.multi_cell(0, 8, line)
    content = pdf.output(dest="S").encode("latin1")
    headers = {"Content-Disposition": "attachment; filename=inventory.pdf"}
    return StreamingResponse(iter([content]), media_type="application/pdf", headers=headers)


@app.get("/reports/monthly", response_class=HTMLResponse)
def monthly_report(
    request: Request, month: str | None = None, session: Session = Depends(get_session)
) -> HTMLResponse:
    today = date.today()
    if month:
        year, month_num = map(int, month.split("-"))
    else:
        year, month_num = today.year, today.month
    start = date(year, month_num, 1)
    end = date(year, month_num, calendar.monthrange(year, month_num)[1])
    purchases = purchases_in_month(session, start, end)
    sales = sales_in_month(session, start, end)
    inventory = inventory_on_hand(session)
    credit = credit_aging(session)
    profit = profit_summary(session, start, end)
    return templates.TemplateResponse(
        "reports/monthly.html",
        {
            "request": request,
            "start": start,
            "end": end,
            "purchases": purchases,
            "sales": sales,
            "inventory": inventory,
            "credit": credit,
            "profit": profit,
        },
    )


# Settings
@app.get("/settings", response_class=HTMLResponse)
def settings_view(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    settings = get_settings(session)
    return templates.TemplateResponse(
        "settings/form.html",
        {
            "request": request,
            "settings": settings,
        },
    )


@app.post("/settings")
async def settings_update(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    vat_rate = parse_decimal(form.get("vat_rate") or "0")
    if vat_rate < 0 or vat_rate > 15:
        raise HTTPException(status_code=400, detail="VAT must be between 0 and 15")
    no_negative = form.get("no_negative_stock", "off") == "on"
    for key, value in {"vat_rate": str(vat_rate), "no_negative_stock": str(no_negative).lower()}.items():
        setting = session.exec(select(Setting).where(Setting.key == key)).first()
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))
    session.commit()
    return RedirectResponse("/settings", status_code=303)
