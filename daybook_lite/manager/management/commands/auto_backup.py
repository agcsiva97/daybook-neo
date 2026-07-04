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
        while len(existing) >= 7:
            oldest = os.path.join(backup_dir, existing.pop(0))
            os.remove(oldest)
            logger.info('[Backup] Rotated out old backup: %s', oldest)

        # ── Copy DB ───────────────────────────────────────────
        timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
        dest = os.path.join(backup_dir, f'daybook_{timestamp}.sqlite3')
        shutil.copy2(db_path, dest)

        msg = f'[Backup] Saved: {dest}'
        self.stdout.write(self.style.SUCCESS(msg))
        logger.info(msg)