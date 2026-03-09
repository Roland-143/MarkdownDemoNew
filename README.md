# Operational Summary Reconciler

Streamlit app that reconciles production, inspection, and shipping records by canonical `Lot ID + Date`, then surfaces completeness gaps and shipped-lot defect risk.

## Quick Start

1. Install dependencies with Poetry:

```bash
poetry install
```

2. Install Playwright browser binaries:

```bash
poetry run playwright install chromium
```

3. Configure environment files in the project root:

- `.env` (production Render DB URL)

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>/<db>
```

- `.env.test` (test DB URL used by integration/e2e tests)

```env
TEST_DATABASE_URL=sqlite:///./.tmp/test_ops_summary.db
AUTO_LOAD_DB_ON_START=0
```

4. Run the app:

```bash
poetry run streamlit run app.py
```

## Test Commands

Run all tests (unit + integration + e2e):

```bash
poetry run pytest
```

Run only Playwright e2e tests:

```bash
poetry run pytest tests/e2e -m e2e
```

## What Is Implemented

- `ops_summary.normalize`: canonical lot/date/type coercion helpers.
- `ops_summary.reconcile`: union-key reconciliation, source completeness flags, priority ranking, and drill-down trace payloads.
- `ops_summary.db`: DB loaders for production/shipping/inspection sources.
- `app.py`: Streamlit UI with CSV upload mode and DB mode.
- Integration and Playwright e2e test coverage against `TEST_DATABASE_URL`.

## Database Assets

SQL schema/seed/query artifacts remain under `db/`:

- `db/schema.sql`
- `db/seed.sql`
- `db/sample_queries.sql`
