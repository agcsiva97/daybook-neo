import requests
from django.conf import settings
from packaging.version import Version, InvalidVersion
from .models import AppUpdateStatus

def perform_update_check():
    record = AppUpdateStatus.get_current()

    try:
        url = "https://api.github.com/repos/agcsiva97/daybook-neo/releases/latest"
        resp = requests.get(url, headers={"Accept": "application/vnd.github+json"}, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        latest_tag = data["tag_name"].lstrip("v")
        current = settings.APP_VERSION.lstrip("v")

        record.status = "available" if Version(latest_tag) > Version(current) else "none"
        record.latest_version = latest_tag
        record.release_notes = data.get("body", "") or "No release notes provided."

    except (requests.RequestException, KeyError, InvalidVersion):
        record.status = "error"
        record.release_notes = None

    record.save()
    return record