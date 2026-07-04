# Running Django as a Windows Service Using NSSM

This guide explains how to run the **Daybook Lite** Django application as a Windows Service using **Waitress** and **NSSM (Non-Sucking Service Manager)**.

---

# Prerequisites

* Windows machine
* Python virtual environment created
* Django project working locally
* Administrator privileges
* NSSM downloaded

Project structure:

```text
C:\
└── dbk\
    └── daybook_lite\
        ├── daybook_lite\
        │   ├── manage.py
        │   ├── run_server.py
        │   └── ...
        ├── venv\
        ├── logs\
        │   ├── daybook.log
        │   ├── daybook_errors.log
        │   ├── security.log
        │   ├── transactions.log
        │   ├── service_out.log
        │   └── service_err.log
        ├── data\
        │   ├── db.sqlite3
        │   └── backups\          ← default backup location
        └── nssm.exe
```

---

# Step 1 — Existing Logging in `settings.py`

Your current `LOGGING` config already covers the essentials. Here is a summary of what it captures and what it does not.

## What your existing logging captures

| Log File              | Captures                                              |
| --------------------- | ----------------------------------------------------- |
| `daybook.log`         | All INFO+ from Django internals, `entries`, `accounts`, root |
| `daybook_errors.log`  | All ERROR+ from `django.request`                      |
| `security.log`        | INFO+ from `django.security` and `accounts`           |
| `transactions.log`    | INFO+ from `entries`                                  |

## What it does NOT capture

| What                                | Reason                                                                                     | Fix                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| `DEBUG` level logs                  | All handlers start at `INFO`                                                               | Set handler level to `DEBUG` if needed during dev    |
| `print()` statements                | Go to NSSM `service_out.log` only, not any Django log file                                 | Replace with `logger.info()` in your code            |
| Waitress access logs                | `waitress` logger not declared — falls to `root` handler → goes to `daybook.log` ✓        | Already captured via root; no change needed          |
| `self.stdout.write()` in commands   | Goes to NSSM stdout only                                                                   | Add `logger.info()` alongside every `self.stdout.write()` |
| SQL queries                         | `django.db.backends` not declared — suppressed at INFO level via `django` logger          | Add `django.db.backends` logger at `WARNING` to keep it quiet |

## Recommended additions to your existing `LOGGING`

Add the following inside your existing `loggers` dict. No other changes needed:

```python
'loggers': {
    # ... your existing loggers ...

    # Suppress noisy SQL query logs — only show warnings
    'django.db.backends': {
        'handlers': ['file'],
        'level': 'WARNING',
        'propagate': False,
    },
    # Capture waitress access logs explicitly
    'waitress': {
        'handlers': ['file'],
        'level': 'INFO',
        'propagate': False,
    },
}
```

> Your `logs/` directory is at `BASE_DIR / 'logs'`. Make sure this folder exists before starting the service — NSSM will not create it.

```cmd
mkdir C:\dbk\daybook_lite\logs
```

---

# Step 2 — Add `BACKUP_DIR` to the Configuration Model

Add a new config key so users can set their preferred backup directory from the app's settings page.

**In `manager/models.py` — update your `Configuration` class:**

```python
class Key(models.TextChoices):
    # ... existing keys ...
    BACKUP_DIR = 'BACKUP_DIR', 'Database Backup Directory'

DEFAULTS = {
    # ... existing defaults ...
    Key.BACKUP_DIR: '',   # blank = use default data/backups/ path
}

KEY_GROUP_MAP = {
    # ... existing mappings ...
    Key.BACKUP_DIR: Group.APP,
}
```

---

# Step 3 — Data Migration for `BACKUP_DIR`

Create a data migration to insert the new config row on existing machines without wiping any data.

**Create:** `manager/migrations/0045_add_backup_dir_config.py`

```python
from django.db import migrations
import logging

logger = logging.getLogger('daybook')

def add_backup_dir(apps, schema_editor):
    Configuration = apps.get_model('manager', 'Configuration')
    obj, created = Configuration.objects.get_or_create(
        key='BACKUP_DIR',
        defaults={'group': 'APP', 'value': ''}
    )
    if created:
        logger.info('[Config] Created -> key=[BACKUP_DIR] | value=[]')
    else:
        logger.info('[Config] Already exists -> key=[BACKUP_DIR] (skipped)')

def remove_backup_dir(apps, schema_editor):
    apps.get_model('manager', 'Configuration').objects.filter(key='BACKUP_DIR').delete()
    logger.info('[Config] Removed -> key=[BACKUP_DIR]')

class Migration(migrations.Migration):
    dependencies = [
        ('manager', '0044_previous'),   # ← update to your actual last migration
    ]
    operations = [
        migrations.RunPython(add_backup_dir, remove_backup_dir),
    ]
```

Run it:

```cmd
C:\dbk\daybook_lite\venv\Scripts\python.exe manage.py migrate
```

---

# Step 4 — Config Migration Patterns (Reference)

Use these patterns whenever you need to add, rename, or remove a config key in future releases.

## Adding a new key

Add to `Key`, `DEFAULTS`, `KEY_GROUP_MAP`, then create a data migration using `get_or_create` as shown in Step 3. Safe to run multiple times.

## Renaming a key

Copy the old value across to the new key, then delete the old one:

```python
def rename_key(apps, schema_editor):
    Configuration = apps.get_model('manager', 'Configuration')
    old = Configuration.objects.filter(key='OLD_KEY').first()
    if old:
        Configuration.objects.get_or_create(
            key='NEW_KEY',
            defaults={'group': old.group, 'value': old.value}
        )
        old.delete()

def reverse_rename(apps, schema_editor):
    Configuration = apps.get_model('manager', 'Configuration')
    new = Configuration.objects.filter(key='NEW_KEY').first()
    if new:
        Configuration.objects.get_or_create(
            key='OLD_KEY',
            defaults={'group': new.group, 'value': new.value}
        )
        new.delete()
```

## Deleting a key

```python
def delete_key(apps, schema_editor):
    apps.get_model('manager', 'Configuration').objects.filter(key='OLD_KEY').delete()

def restore_key(apps, schema_editor):
    apps.get_model('manager', 'Configuration').objects.get_or_create(
        key='OLD_KEY',
        defaults={'group': 'APP', 'value': 'previous_default'}
    )
```

## Updating a default value on existing machines

```python
def update_default(apps, schema_editor):
    Configuration = apps.get_model('manager', 'Configuration')
    # Only update rows that still have the old default — don't overwrite user changes
    Configuration.objects.filter(key='SOME_KEY', value='old_default').update(value='new_default')

def reverse_update_default(apps, schema_editor):
    Configuration = apps.get_model('manager', 'Configuration').objects.filter(
        key='SOME_KEY', value='new_default'
    ).update(value='old_default')
```

---

# Step 5 — Create the Auto Backup Management Command

**Location:** `manager/management/commands/auto_backup.py`

```python
import os
import shutil
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger('daybook')

class Command(BaseCommand):
    help = 'Creates a timestamped SQLite backup. Backup dir is read from Configuration.'

    def handle(self, *args, **kwargs):
        from manager.models import Configuration  # avoid circular import at module level

        db_path = settings.DATABASES['default']['NAME']

        # ── Resolve backup directory ──────────────────────────
        custom_dir = Configuration.get_value(
            Configuration.Key.BACKUP_DIR, default=''
        ).strip()

        if custom_dir and os.path.isabs(custom_dir):
            backup_dir = custom_dir
            logger.info('[Backup] Using custom backup dir: %s', backup_dir)
        else:
            # Default: data/backups/ alongside the db file
            backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
            if custom_dir:
                # User entered a value but it's not an absolute path — warn and fallback
                msg = (
                    f'[Backup] BACKUP_DIR "{custom_dir}" is not an absolute path. '
                    f'Falling back to default: {backup_dir}'
                )
                self.stdout.write(self.style.WARNING(msg))
                logger.warning(msg)
            else:
                logger.info('[Backup] No custom dir set. Using default: %s', backup_dir)

        os.makedirs(backup_dir, exist_ok=True)

        # ── Rotate: keep only last 30 backups ─────────────────
        existing = sorted(
            [f for f in os.listdir(backup_dir) if f.endswith('.sqlite3')]
        )
        while len(existing) >= 30:
            oldest = os.path.join(backup_dir, existing.pop(0))
            os.remove(oldest)
            logger.info('[Backup] Rotated out old backup: %s', oldest)

        # ── Copy DB ───────────────────────────────────────────
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(backup_dir, f'daybook_{timestamp}.sqlite3')
        shutil.copy2(db_path, dest)

        msg = f'[Backup] Saved: {dest}'
        self.stdout.write(self.style.SUCCESS(msg))
        logger.info(msg)
```

---

# Step 6 — Update `run_server.py` to Run Auto Backup on Start

Update `run_server.py` to call `auto_backup` before Waitress starts. This ensures a backup is taken every time the Windows service starts or restarts.

**Location:** `C:\dbk\daybook_lite\daybook_lite\run_server.py`

```python
import os
import sys
import logging

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "daybook_lite.settings"
)

import django
django.setup()

logger = logging.getLogger('daybook')

# ── Run auto backup before starting the server ────────────
from django.core.management import call_command

try:
    logger.info('[Startup] Running auto_backup...')
    call_command('auto_backup')
    logger.info('[Startup] auto_backup completed.')
except Exception as e:
    # Backup failure must NEVER stop the server from starting
    logger.error('[Startup] auto_backup failed: %s', str(e), exc_info=True)

# ── Start Waitress ────────────────────────────────────────
from waitress import serve
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

if __name__ == "__main__":
    logger.info('[Startup] Starting Daybook Lite on http://localhost:8000')
    print("Starting Daybook Lite on http://localhost:8000")

    serve(
        application,
        host="127.0.0.1",
        port=8000
    )
```

> **Note:** `exc_info=True` on the error log prints the full Python traceback into `daybook.log` — useful for diagnosing backup failures without crashing the service.

---

## Install Waitress

```cmd
C:\dbk\daybook_lite\venv\Scripts\pip install waitress
```

---

## Test the Server Manually

Before installing the Windows service, run manually and confirm all three:

```cmd
C:\dbk\daybook_lite\venv\Scripts\python.exe C:\dbk\daybook_lite\daybook_lite\run_server.py
```

1. A `.sqlite3` file appears in `data\backups\` (or your configured path)
2. Backup log lines appear in `logs\daybook.log`
3. Browser loads at `http://localhost:8000`

---

# Step 7 — Download and Place NSSM

Download NSSM:

```text
https://nssm.cc/download
```

Extract and copy `nssm.exe` to:

```text
C:\dbk\daybook_lite\nssm.exe
```

Or place in `C:\Windows\System32\` for system-wide access.

---

# Step 8 — Open Command Prompt as Administrator

1. Press **Windows Key**, type `cmd`
2. Right-click **Command Prompt** → **Run as administrator**

---

# Step 9 — Install the Service Using NSSM GUI

```cmd
C:\dbk\daybook_lite\nssm.exe install DaybookLite
```

## Application Tab

| Field             | Value                                         |
| ----------------- | --------------------------------------------- |
| Path              | `C:\dbk\daybook_lite\venv\Scripts\python.exe` |
| Startup Directory | `C:\dbk\daybook_lite\daybook_lite`            |
| Arguments         | `run_server.py`                               |

## Details Tab

| Field        | Value                             |
| ------------ | --------------------------------- |
| Display Name | Daybook Lite Server               |
| Description  | Daybook Lite Financial Management |
| Startup Type | Automatic                         |

## I/O Tab (Logging)

```cmd
mkdir C:\dbk\daybook_lite\logs
```

| Field           | Value                                      |
| --------------- | ------------------------------------------ |
| Output (stdout) | `C:\dbk\daybook_lite\logs\service_out.log` |
| Error (stderr)  | `C:\dbk\daybook_lite\logs\service_err.log` |

Click **Install Service**.

---

# Step 10 — Install the Service Using Command Line (Alternative)

```cmd
C:\dbk\daybook_lite\nssm.exe install DaybookLite "C:\dbk\daybook_lite\venv\Scripts\python.exe"

C:\dbk\daybook_lite\nssm.exe set DaybookLite AppDirectory "C:\dbk\daybook_lite\daybook_lite"

C:\dbk\daybook_lite\nssm.exe set DaybookLite AppParameters "run_server.py"

C:\dbk\daybook_lite\nssm.exe set DaybookLite DisplayName "Daybook Lite Server"

C:\dbk\daybook_lite\nssm.exe set DaybookLite Description "Daybook Lite Financial Management"

C:\dbk\daybook_lite\nssm.exe set DaybookLite Start SERVICE_AUTO_START

C:\dbk\daybook_lite\nssm.exe set DaybookLite AppStdout "C:\dbk\daybook_lite\logs\service_out.log"

C:\dbk\daybook_lite\nssm.exe set DaybookLite AppStderr "C:\dbk\daybook_lite\logs\service_err.log"

C:\dbk\daybook_lite\nssm.exe set DaybookLite AppRotateFiles 1

C:\dbk\daybook_lite\nssm.exe set DaybookLite AppRotateBytes 10485760
```

NSSM rotates `service_out.log` and `service_err.log` at 10 MB. Django's own log files (`daybook.log`, etc.) are rotated independently by `TimedRotatingFileHandler` at midnight.

---

# Step 11 — Start the Service

```cmd
C:\dbk\daybook_lite\nssm.exe start DaybookLite
```

Check status:

```cmd
C:\dbk\daybook_lite\nssm.exe status DaybookLite
```

Expected:

```text
SERVICE_RUNNING
```

---

# Step 12 — Verify Everything

```text
http://localhost:8000
```

**Backup created:**
```cmd
dir C:\dbk\daybook_lite\data\backups\
```
Expected: `daybook_YYYYMMDD_HHMMSS.sqlite3`

**Django logs written:**
```cmd
type C:\dbk\daybook_lite\logs\daybook.log
```
Expected: `[Startup] Running auto_backup...` and `[Backup] Saved: ...`

---

## Check Error Logs

Inspect in this order when something goes wrong:

```cmd
rem 1. NSSM service-level crash
type C:\dbk\daybook_lite\logs\service_err.log

rem 2. Django application errors
type C:\dbk\daybook_lite\logs\daybook_errors.log

rem 3. Full Django log with traceback
type C:\dbk\daybook_lite\logs\daybook.log
```

---

# Log File Reference

| File                    | Contents                                              | Rotated by              | Rotation trigger     |
| ----------------------- | ----------------------------------------------------- | ----------------------- | -------------------- |
| `logs\service_out.log`  | NSSM stdout (`print()`, `self.stdout.write()`)        | NSSM                    | 10 MB                |
| `logs\service_err.log`  | NSSM stderr (unhandled Python crashes)                | NSSM                    | 10 MB                |
| `logs\daybook.log`      | All INFO+ — Django, entries, accounts, root, waitress | `TimedRotatingFileHandler` | Midnight, 10 copies |
| `logs\daybook_errors.log` | ERROR+ from `django.request` only                   | `TimedRotatingFileHandler` | Midnight, 10 copies |
| `logs\security.log`     | Security + accounts events                            | `TimedRotatingFileHandler` | Midnight, 5 copies  |
| `logs\transactions.log` | Transaction-specific INFO+ from `entries`             | `TimedRotatingFileHandler` | Midnight, 10 copies |

---

# Common NSSM Management Commands

## Stop the Service

```cmd
nssm stop DaybookLite
```

## Restart the Service

Use after deploying code changes. Also triggers a fresh `auto_backup`:

```cmd
nssm restart DaybookLite
```

## Edit Service Settings

```cmd
nssm edit DaybookLite
```

## Remove the Service

```cmd
nssm stop DaybookLite
nssm remove DaybookLite confirm
```

## Open Windows Services Console

```cmd
services.msc
```

---

# Verify Service Persistence After Reboot

1. Restart the machine.
2. Open a browser and go to `http://localhost:8000`.
3. Check `logs\daybook.log` for the `[Startup]` and `[Backup]` lines to confirm the backup ran on boot.

---

# Summary

You have now configured:

* Django running through Waitress
* NSSM-managed Windows Service with automatic startup
* **Auto backup on every service start — directory read from `Configuration` model**
* **`BACKUP_DIR` config key with data migration for existing machines**
* **Config migration patterns for add / rename / delete / update-default**
* Existing Django logging unchanged — `waitress` and `django.db.backends` loggers added
* Log rotation for all log files (NSSM + TimedRotatingFileHandler)
* Service management commands
