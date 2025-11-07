# Mini Store App

A single-user inventory and sales web application built with FastAPI, SQLModel, HTMX, and Alpine.js. It tracks products sold by count or weight, manages suppliers and customers, enforces FIFO-based cost of goods sold, and generates month-end reports with export options.

## Features

- FastAPI with Jinja2 server-rendered views styled with Bulma and enhanced with HTMX/Alpine.js.
- SQLModel ORM backed by SQLite with Alembic-style migrations.
- Item, Supplier, Customer CRUD with barcode/SKU search.
- Purchase receipts (stock-in) and Sales invoices (stock-out) with FIFO costing and VAT (0–15%) support.
- Customer payments with credit ledger and configurable negative-stock enforcement.
- Inventory ledger maintains on-hand quantities and FIFO COGS (no negative stock when disabled).
- Month-end reports for Inventory, Purchases, Sales, Customer Credit Aging, and Profit Summary plus CSV/PDF exports.
- Seed script for demo data and pytest unit tests for FIFO logic and customer credit balances.

## Getting Started

### Prerequisites

- Python 3.10+
- (Optional) virtual environment manager such as `venv` or `poetry`

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Database Migration & Seed

Run the Alembic migration and optional seed data:

```bash
alembic upgrade head
python seed.py
```

### Development Server

Start the FastAPI development server with auto-reload:

```bash
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000` to access the dashboard.

### Running Tests

```bash
pytest
```

## Project Layout

```
app/
  main.py              # FastAPI routes and views
  models.py            # SQLModel ORM models
  db.py                # Engine/session helpers
  services/            # FIFO & ledger utilities
  reports/             # Reporting helpers
  templates/           # Jinja2 templates (HTMX/Alpine ready)
  static/              # Static assets placeholder
migrations/            # Alembic environment + revisions
seed.py                # Demo data loader
requirements.txt
```

## Configuration

- Settings are stored in the `setting` table and editable in the UI (`/settings`).
- VAT defaults to `0` and can be configured up to `15` percent.
- Negative stock prevention is enabled by default but can be toggled per item or globally.

## Exports

- Inventory on-hand can be exported as CSV or PDF from the reports section.

## License

MIT
