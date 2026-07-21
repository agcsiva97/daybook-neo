import os
import sys
import logging
import django

from waitress import serve
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "daybook_lite.settings"
)

django.setup()

logger = logging.getLogger('daybook')
# ── Run auto backup before starting the server ────────────
try:
    logger.info('[Startup] Running auto_backup...')
    call_command('auto_backup')
    logger.info('[Startup] auto_backup completed.')
except Exception as e:
    # Backup failure must NEVER stop the server from starting
    logger.error('[Startup] auto_backup failed: %s', str(e), exc_info=True)

try:
    from entries.update_check import perform_update_check

    logger.info('[Startup] Checking for updates...')
    perform_update_check()
    logger.info('[Startup] Update check completed.')
except Exception as e:
    logger.error('[Startup] Update check failed: %s', str(e), exc_info=True)

# ── Start Waitress ────────────────────────────────────────
application = get_wsgi_application()

if __name__ == "__main__":
    logger.info('[Startup] Starting Daybook Lite on http://localhost:8000')
    print("Starting Daybook Lite on http://localhost:8000")

    serve(
        application,
        host="0.0.0.0",
        port=8000
    )