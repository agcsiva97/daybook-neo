# Daybook Lite

> Reference doc compiled from project development history. Confirm against the live codebase if anything here looks out of date.

## 1. What It Is

Daybook Lite is an **offline-first, multi-shop financial management application** built for small businesses in India. It runs on a **one-time payment model** (no subscription), uses a **local SQLite database**, and is designed to work without a constant internet connection.

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django (Python) |
| Database | SQLite — single DB, not multi-tenant/DB-per-shop |
| Frontend | Bootstrap 5, HTMX (dynamic UI without a JS framework) |
| Charts | ApexCharts (stacked column, radial gauge, pie) |
| PDF generation | ReportLab + NotoSansTamil fonts |
| History/Audit | django-simple-history (`HistoricalRecords`) |
| Deployment | NSSM (Windows service) + waitress WSGI server |

## 3. App Structure

The project is split into four Django apps:

- **`accounts`** — user/auth-related functionality.
- **`entries`** — day-to-day transaction entry, ledgers, loans.
- **`manager`** — chart-of-accounts hierarchy (Group → Type → Account), shop configuration, activity logging, and the export/import sync system. *(See the separate `manager_app.md` doc for full detail.)*
- **`api`** — Django REST Framework layer for inter-app / external API access.

## 4. Core Architectural Decisions

These were deliberate trade-offs made early in the project, worth remembering when extending the app:

- **Single SQLite DB + `shop` ForeignKey** for multi-shop isolation — chosen over a separate database per shop, and over a VPN-based (WireGuard) live-sync approach. Simpler to back up, simpler to sync via JSON export/import.
- **Dynamic `get_balance()`** instead of a stored `shop.balance` column — avoids balance drift from missed updates. Balance is always computed from the transaction history, not cached.
- **`Decimal` with `.quantize()`** used throughout for currency math to avoid floating-point precision bugs.
- **Composite database indexes** on transaction tables to keep large-volume queries fast.
- **`post_migrate` signal** used to seed default groups/permissions.

## 5. Key Features

### Transactions & Ledger
- Shared helper module `transaction_helper.py` centralizes transaction mutation logic:
  - `_add_or_create_transaction`
  - `_apply_amount_delta`
  - `_reduce_or_delete_transaction`
- **Infinite scroll** via HTMX for transaction lists with large volumes.
- **Shared modal pattern** (`sharedInfoModal`, `sharedDeleteModal`) — one modal instance reused across rows instead of one-per-row, to keep the DOM light with large datasets.

### Loans
- **Bulk loan creation** — dynamic JS-generated form rows, saved inside `db_transaction.atomic()` for all-or-nothing commits.
- **Pawn number formatting** — `_parse_pawn_nos` and `append_pawn_no_range_to_remark` handle pawn-number ranges in loan remarks across four lifecycle scenarios (create, partial release, full release, re-pledge, etc.).

### Dashboard & Reporting
- ApexCharts-based dashboard: stacked column charts, radial gauges, pie charts.
- Print layouts use a "wrapper table" technique for correct A5 paper output.
- `indian_format` — a custom template tag registered as a global builtin, formats numbers in the Indian lakh/crore grouping style.
- Skeleton loaders for perceived performance on slower devices.

### Localization
- Bilingual Tamil/English labels throughout the UI.
- Tamil PDF rendering via ReportLab with NotoSansTamil fonts.
- Indian financial year (April–March) logic baked into reporting.

### Export / Import (Sync)
- A JSON-based sync system lets data move between installations/devices without a live network connection. Full mechanics are documented in `manager_app.md`, since the sync engine lives alongside the chart-of-accounts logic in the `manager` app.

### Deployment
- Runs as a **Windows service via NSSM**, served by **waitress**, started through `run_server.py`.
- Logging migrated from `RotatingFileHandler` to `TimedRotatingFileHandler` for cleaner daily log rotation.

## 6. Known Issues / In Progress (as of June 2026)

- **Keyman Tamil typing** has an unresolved input conflict in Django form fields when used in Chrome.
- Cascading dropdown restoration logic (capturing a pre-selected value before a dependent fetch call fires) was being hardened.

## 7. Useful Patterns Established in This Project

- Custom ID generation patterns for human-readable record IDs.
- `select_related`, `aggregate`, and `Case`/`When` used for conditional aggregation queries.
- `update_or_create` used heavily in import/sync flows.
- Alphanumeric primary keys require `<str:pk>` in URL patterns, not the default `<int:pk>`.