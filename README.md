# Daybook Neo

Daybook Neo is an offline-first, SQLite-backed financial management desktop application built for small businesses in India. It runs locally per shop, works without a permanent internet connection, and can optionally sync data between multiple shop locations over a secure VPN.

## Features

- **Denomination entries** — record cash denomination counts (notes, bundles, coins, damaged notes) per shop, per time period, with live totals and per-user field visibility preferences.
- **Loan & Release management** — bulk entry of pawn loans and releases with ledger selection, auto-incrementing pawn numbers, and live per-row and grand totals for principal, interest, and combined amounts.
- **Transaction reporting** — daily reports covering shop balances (opening/closing, debit/credit, expected vs. actual balance from denominations), loan/release summaries, and other ledger transactions, with a print-optimized layout for A5 paper.
- **Multi-shop support** — a single database with shop-level data isolation, so one installation can manage several branch locations.
- **Multi-shop sync** — Auto Sync over Tailscale (WireGuard-based VPN) pulls data from remote shop APIs with paginated imports and conflict resolution, plus a JSON export/import fallback.
- **Bilingual UI** — interface and PDF reports support Tamil and English (Tamil PDF rendering via ReportLab with NotoSansTamil fonts).
- **Audit trail** — change history tracked via `django-simple-history`.
- **Offline-friendly notifications** — sync completion and backup status surfaced through the browser Notification API.

## Tech Stack

- **Backend:** Django, organized into four apps — `accounts`, `entries`, `manager`, `api`
- **Database:** SQLite, with shop-level foreign key isolation
- **Frontend:** HTMX + Bootstrap 5
- **PDF generation:** ReportLab (with Tamil font support)
- **Sync transport:** Tailscale VPN + Django REST Framework (token authentication for machine-to-machine sync)
- **Deployment:** Runs as a Windows service (via NSSM + waitress)

## Architecture

Daybook Neo is designed to run independently at each shop location:

- Each installation keeps its own SQLite database, scoped by `Shop`.
- Configuration (default shop, feature flags, report paper size, etc.) is stored in a `Configuration` model and exposed to templates via a context processor, alongside app version, current shop, and last sync time.
- A background Auto Sync process can pull data from other shops' APIs over Tailscale, using a dedicated `sync_service` account with token authentication.
- A three-tier backup strategy protects against data loss.

## Getting Started

> Adjust paths, environment variable names, and commands below to match your local setup — these are the standard steps for a Django project of this shape.

```bash
# Clone the repository
git clone <your-repo-url>
cd daybook-neo

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

## Deployment

Production deployments run as a Windows service using **NSSM** (Non-Sucking Service Manager) with **waitress** as the WSGI server. The included `deploy.ps1` script handles:

1. Stopping the service
2. Taking a timestamped database backup
3. Checking out the target git tag
4. Running migrations
5. Restarting the service
6. Verifying the deployed version

Versioning follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH), with changes tracked in `CHANGELOG.md` following the [Keep a Changelog](https://keepachangelog.com/) format.

## License

_Add your license here._

## Contact

Maintained by Sivasubramanian.
