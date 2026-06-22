# Daybook Lite — `manager` App

> Reference doc compiled from project development history. Confirm against the live codebase if anything here looks out of date.

## 1. Purpose

The `manager` app owns three things for each shop:

1. The **chart-of-accounts hierarchy** (Group → Type → Account) that every transaction in `entries` posts against.
2. **Shop-level configuration** (the `Configuration` model).
3. The **export/import sync system** that backs up and transfers a shop's data as JSON.

It also holds the `ActivityLog` model used for auditing what happened in the system.

## 2. The Core Hierarchy: Group → Type → Account

This is the chart-of-accounts structure. Every Account a transaction can be posted to belongs to a Type, and every Type belongs to a Group.

```
Group  (top-level classification)
 └── Type   (sub-category within a Group)
      └── Account   (the actual ledger account transactions post to)
```

**Why three levels instead of two?** It lets reporting roll up at different levels of granularity — you can show a dashboard total for an entire Group (e.g. "all Assets"), a subtotal for a Type (e.g. "Cash accounts"), or drill down to one specific Account.

### Example

| Level | Example value |
|---|---|
| Group | `Assets` |
| Type | `Bank` |
| Account | `SBI Current A/c — 1234` |

| Level | Example value |
|---|---|
| Group | `Liabilities` |
| Type | `Loans Payable` |
| Account | `Vehicle Loan — HDFC` |

A transaction is never posted directly to a Group or a Type — only to a leaf-level **Account**. Group and Type exist purely for classification and roll-up reporting.

### Relationship rules
- **Group → Type**: one-to-many. A Type belongs to exactly one Group.
- **Type → Account**: one-to-many. An Account belongs to exactly one Type.
- **Account → shop**: each Account is scoped to a specific `shop` (via a `shop` ForeignKey), which is how multi-shop isolation is enforced inside a single shared database.
- Balances are **not** stored on the Account row — they're computed dynamically via `get_balance()` from the transaction history, so Group/Type totals are always a live rollup rather than a cached number that can drift.

### UI: Shop Meta Page
The hierarchy is presented to the user as a **three-level Bootstrap accordion** — expand a Group to see its Types, expand a Type to see its Accounts — with **balance summary cards** at each level, and **bilingual Tamil/English labels** throughout.

## 3. What Is "Sync"?

Daybook Lite is **offline-first** — there's no central server each installation talks to. "Sync" here doesn't mean live, real-time replication between devices. It means a **JSON-based export/import mechanism**:

- **Export** turns a shop's data into a JSON file/snapshot.
- **Import** reads that JSON file back into a (potentially different) installation's database, reconciling it against whatever is already there.

This is what lets a shop owner move their data between a desktop and a laptop, take backups, or hand data off to support — without needing networking, a hosted server, or always-on connectivity.

> Note: this was a deliberate choice over a live VPN-based sync (WireGuard was evaluated and set aside) — JSON export/import is simpler to reason about, easier to debug, and doesn't require any networking setup from the end user.

## 4. How Sync Works

### What gets synced
The export/import covers these models:
- `Type`
- `Accounts`
- `Transactions`
- `Loan`

### Export
Serializes the above models for a shop into a JSON payload.

### Import
This is not a blind overwrite — it's a **reconciliation**, handling three cases per record:
- **Create** — record exists in the JSON but not in the target DB.
- **Update** — record exists in both; target DB row is updated to match the JSON.
- **Delete** — record was removed on the source side and that removal needs to be reflected in the target.

### Handling deletions: `_deleted_count` helper
Because deletions can't just be "absence from the JSON" (that would also catch records the importing side hasn't seen yet), there's a `_deleted_count` helper that explicitly handles two JSON shapes:
- **Flat format** — a simple list of records.
- **Nested format** — records grouped/wrapped (e.g. by model or by shop).

This lets the same import logic work whether the JSON payload was produced as one flat dump or as a more structured nested export.

### Safety
Bulk-affecting operations (like bulk loan creation, and by extension large import batches) are wrapped in `db_transaction.atomic()` so a failure partway through doesn't leave the database in a half-updated state.

## 5. `Configuration` Model

Holds shop/app-level settings (the specifics of which settings live here should be checked against the current model definition). When the schema for `Configuration` changes, it's handled through **explicit Django data migrations** rather than ad-hoc scripts, so existing installs upgrade cleanly.

## 6. `ActivityLog` Model

Tracks user actions across the app for audit/troubleshooting purposes — useful for answering "what changed, and who/what changed it" without digging through `HistoricalRecords` on every individual model.

## 7. Other `manager`-Adjacent Details Worth Remembering

- **Alphanumeric primary keys**: Account/shop records using non-numeric PKs need `<str:pk>` in the URL pattern, not the default `<int:pk>` — this caused a routing mismatch bug previously.
- **SQLite FK constraint errors at `COMMIT`**: seen in the `add_shop` view — SQLite defers foreign key checks to commit time, so an FK violation can surface later than expected, away from the line that actually caused it. Worth checking insertion order (parent rows before child rows) when this resurfaces.
- **Logging**: `manager`-level operations log through the app's `TimedRotatingFileHandler` setup rather than the older size-based `RotatingFileHandler`.