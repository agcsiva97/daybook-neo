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
        └── nssm.exe
```

---

# Step 1 — Create `run_server.py`

Create a file named `run_server.py` in your project root:

**Location:**

```text
C:\dbk\daybook_lite\daybook_lite\
```

**Contents:**

```python
import os
import sys

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "daybook_lite.settings"
)

import django

django.setup()

from waitress import serve
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

if __name__ == "__main__":
    print("Starting Daybook Lite on http://localhost:8000")

    serve(
        application,
        host="127.0.0.1",
        port=8000
    )
```

---

## Install Waitress

Install Waitress inside your virtual environment:

```cmd
C:\dbk\daybook_lite\venv\Scripts\pip install waitress
```

---

## Test the Server Manually

Before creating the Windows service, verify that the application starts successfully.

```cmd
C:\dbk\daybook_lite\venv\Scripts\python.exe C:\dbk\daybook_lite\daybook_lite\run_server.py
```

Open a browser and navigate to:

```text
http://localhost:8000
```

Confirm the application loads correctly before proceeding.

---

# Step 2 — Download and Place NSSM

Download NSSM:

```text
https://nssm.cc/download
```

Extract the archive and copy `nssm.exe` to:

```text
C:\dbk\daybook_lite\nssm.exe
```

Alternatively, place it in:

```text
C:\Windows\System32\
```

to make it accessible system-wide.

---

# Step 3 — Open Command Prompt as Administrator

1. Press **Windows Key**
2. Type:

```text
cmd
```

3. Right-click **Command Prompt**
4. Select **Run as administrator**

> Administrator privileges are required because NSSM installs Windows services.

---

# Step 4 — Install the Service Using NSSM GUI

Run:

```cmd
C:\dbk\daybook_lite\nssm.exe install DaybookLite
```

The NSSM configuration window will open.

---

## Application Tab

Configure the following values:

| Field             | Value                                         |
| ----------------- | --------------------------------------------- |
| Path              | `C:\dbk\daybook_lite\venv\Scripts\python.exe` |
| Startup Directory | `C:\dbk\daybook_lite\daybook_lite`            |
| Arguments         | `run_server.py`                               |

---

## Details Tab

| Field        | Value                             |
| ------------ | --------------------------------- |
| Display Name | Daybook Lite Server               |
| Description  | Daybook Lite Financial Management |
| Startup Type | Automatic                         |

---

## I/O Tab (Logging)

Create the logs directory first:

```cmd
mkdir C:\dbk\daybook_lite\logs
```

Configure:

| Field           | Value                                      |
| --------------- | ------------------------------------------ |
| Output (stdout) | `C:\dbk\daybook_lite\logs\service_out.log` |
| Error (stderr)  | `C:\dbk\daybook_lite\logs\service_err.log` |

Click **Install Service**.

---

# Step 5 — Install the Service Using Command Line (Alternative)

If you prefer not to use the GUI, run the following commands:

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

### Log Rotation

The last two commands enable log rotation:

```text
AppRotateFiles = 1
AppRotateBytes = 10485760
```

This rotates log files once they reach approximately **10 MB**.

---

# Step 6 — Start the Service

Start the service:

```cmd
C:\dbk\daybook_lite\nssm.exe start DaybookLite
```

Check the service status:

```cmd
C:\dbk\daybook_lite\nssm.exe status DaybookLite
```

Expected output:

```text
SERVICE_RUNNING
```

---

# Step 7 — Verify the Application

Open a browser and navigate to:

```text
http://localhost:8000
```

The Daybook Lite application should load successfully.

---

## Check Error Logs

If the application fails to start, inspect the error log:

```cmd
type C:\dbk\daybook_lite\logs\service_err.log
```

---

# Common NSSM Management Commands

## Stop the Service

```cmd
nssm stop DaybookLite
```

---

## Restart the Service

Use after deploying code changes:

```cmd
nssm restart DaybookLite
```

---

## Edit Service Settings

```cmd
nssm edit DaybookLite
```

---

## Remove the Service

Stop the service first:

```cmd
nssm stop DaybookLite
```

Remove it completely:

```cmd
nssm remove DaybookLite confirm
```

---

## Open Windows Services Console

```cmd
services.msc
```

This allows you to:

* View service status
* Start/stop services
* Configure startup behavior
* Review service properties

---

# Verify Service Persistence After Reboot

1. Restart the machine.
2. Log in as any Windows user.
3. Open a browser.
4. Navigate to:

```text
http://localhost:8000
```

The application should be available immediately without any manual startup.

---

# Summary

You have now configured:

* Django running through Waitress
* NSSM-managed Windows Service
* Automatic startup after reboot
* Persistent logging
* Log rotation
* Service management commands

The application will continue running in the background and automatically start whenever Windows boots.
