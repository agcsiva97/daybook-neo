# Daybook Lite — Database Migration Guide

This guide covers three common scenarios:

1. **Export current SQLite DB and move it to another machine (SQLite → SQLite)**
2. **Migrate data from SQLite to PostgreSQL**
3. **Migrate data from SQLite to MySQL**

> ✅ Recommended method for cross-database migration is **Django fixtures** (`dumpdata` / `loaddata`) rather than raw SQL dumps.

---

## 1) Before You Start

- Source machine has the current database at:
  - `daybook_lite/db.sqlite3`
- Django project root (where `manage.py` exists):
  - `daybook_lite/`
- Activate your virtual environment before running commands.

### Safety backup (required)

Create a backup of the current DB file first.

---

## 2) SQLite → SQLite (Different Machine)

You have two options.

### Option A (fastest): Copy database file directly

Use this when **both environments are SQLite** and app version/migrations are aligned.

1. Stop the app on source machine.
2. Copy these from source to target machine:
   - `daybook_lite/db.sqlite3`
   - Project code (same branch/version)
3. On target machine:
   - Install dependencies
   - Run `python manage.py migrate` (safe to run even if already applied)
   - Start app

### Option B (portable): Export/import using fixture

Use this if you want cleaner transfer or future migration to PostgreSQL/MySQL.

#### On source machine

From `daybook_lite/` (where `manage.py` exists):

- Export all business data to JSON fixture:
   - `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission --indent 2 --output data_backup.json`

Copy `data_backup.json` to target machine.

#### On target machine

1. Ensure code and migrations are up to date.
2. Run:
   - `python manage.py migrate`
3. Import:
   - `python manage.py loaddata data_backup.json`

---

## 3) SQLite → PostgreSQL

Your current `requirements.txt` already includes:
- `psycopg2-binary`

Your current `settings.py` already supports PostgreSQL via `DATABASE_URL`.

### Step-by-step

#### A. Export data from SQLite

From source machine (`daybook_lite/`):

- `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission --indent 2 --output data_backup.json`

#### B. Prepare PostgreSQL database (target machine)

Create DB/user in PostgreSQL (example names):
- Database: `daybook_lite`
- User: `daybook_user`
- Password: strong password

#### C. Configure connection in `.env`

In `daybook_lite/.env`, set:

- `DATABASE_URL=postgresql://daybook_user:YOUR_PASSWORD@localhost:5432/daybook_lite`
- Optional: `DB_SSLMODE=prefer` (or `require` for managed/cloud DBs)

#### D. Create schema and import data

From `daybook_lite/`:

1. Create tables:
   - `python manage.py migrate`
2. Load fixture:
   - `python manage.py loaddata data_backup.json`

#### E. Reset sequences (important)

After loading explicit IDs, reset auto-increment sequences:

- `python manage.py sqlsequencereset accounts entries | python manage.py dbshell`

---

## 4) SQLite → MySQL

> ⚠️ Important: current `daybook_lite/settings.py` has built-in handling for SQLite/PostgreSQL only. For MySQL, add a MySQL `DATABASES` config (example below) or create a MySQL-specific settings file.

### Step-by-step

#### A. Export data from SQLite

From source machine (`daybook_lite/`):

- `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission --indent 2 --output data_backup.json`

#### B. Install MySQL driver

In your virtual environment:

- `pip install mysqlclient`

If wheel install fails on Windows, install required Visual C++ build tools or use `PyMySQL` as fallback.

#### C. Configure MySQL DB in Django settings

Example `DATABASES` block for MySQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'daybook_lite',
        'USER': 'daybook_user',
        'PASSWORD': 'YOUR_PASSWORD',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}
```

#### D. Run schema + import data

From `daybook_lite/`:

1. `python manage.py migrate`
2. `python manage.py loaddata data_backup.json`

#### E. Reset sequences / auto increment

Run in MySQL:

- `ALTER TABLE <table_name> AUTO_INCREMENT = 1;`

(For many projects this self-corrects on insert, but verify after import.)

---

## 5) Verification Checklist (All Scenarios)

After import:

- Login works for existing users
- Ledgers and transactions are visible
- Reports open without errors
- New transaction insert works
- Admin panel loads

Optional quick checks:

- `python manage.py check`
- `python manage.py showmigrations`

---

## 6) Troubleshooting

### `IntegrityError` during `loaddata`
- Ensure target DB is empty or freshly migrated before load.
- If not empty, recreate DB and run `migrate` again.

### Missing tables
- Run `python manage.py migrate` before `loaddata`.

### PostgreSQL SSL/auth errors
- Verify `DATABASE_URL`, host, port, username, password.
- Set `DB_SSLMODE` correctly for your server.

### MySQL collation/charset issues
- Use `utf8mb4` charset.
- Ensure server/database default collation supports UTF-8.

### `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff...`
This means the fixture was saved as UTF-16 (common in Windows PowerShell when using `>` redirection).

Fix existing file:
- `python -c "from pathlib import Path; p=Path('data_backup.json'); t=p.read_text(encoding='utf-16'); p.write_text(t, encoding='utf-8')"`

Prevent future issue:
- Use `--output data_backup.json` with `dumpdata` (already shown above), instead of `> data_backup.json`.

---

## 7) Recommended Migration Path for Your Team

For your Daybook Lite project, use this sequence:

1. SQLite source → `dumpdata` JSON
2. Move JSON file to new machine
3. Import into SQLite (if needed) for validation
4. Point app to PostgreSQL or MySQL
5. Run `migrate` + `loaddata`
6. Validate and take a fresh backup

This gives a repeatable, low-risk migration process across machines and databases.
