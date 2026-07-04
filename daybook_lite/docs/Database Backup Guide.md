# Database Backup Guide

Daybook protects your data in two ways:

1. **Automatic Backups** — created every time the application starts, with no action needed from you.
2. **Manual Backup Download** — a one-click backup you trigger yourself, from the Sync page, whenever you want a copy in hand (e.g., before a major import, or to store off-site).

This guide covers both.

---

## Part 1: Automatic Backups (Built-In, No Setup Required)

### How It Works

Every time Daybook is started, it automatically creates a fresh backup of the database **before** the application becomes available to use. This happens silently in the background — you don't need to click anything.

- If, for any reason, the automatic backup fails, it will **not** stop Daybook from starting. The application will still open normally; only the backup step is skipped for that session, and the issue is written to the application log for troubleshooting.

### Where Automatic Backups Are Stored

By default, automatic backups are saved in a `backups` folder located next to the main database file on this machine.

You can change this to a different folder of your choice (e.g., an external drive or a network location) via **Configurations**. Go to:

> **Manager → Configurations**

and set the **Backup Directory** to any full folder path on this machine. Once set, all future automatic backups will be saved there instead of the default location.

> **Note:** The path you enter must be a full ("absolute") folder path — for example `D:\DaybookBackups` or `/home/user/daybook-backups`, not a relative name. If an invalid path is entered, the system will safely fall back to the default backup folder rather than fail to start.

### Checking Where Your Backups Are Currently Saved

You don't need to remember or guess the backup folder — it's always visible on the **About** page:

> **Manager → About**

This page shows the exact folder path where automatic backups are currently being written, whether it's the default location or a custom one you've configured.

### How Many Backups Are Kept

To avoid filling up your disk, Daybook automatically keeps only the **most recent backups** and deletes the oldest ones as new backups are created. You always have a rolling window of recent automatic backups available — you don't need to manually clean these up.

### Backup File Naming

Automatic backups are saved as:
```
daybook_<DD_MM_YYYY_HH_MM_SS>.sqlite3
```
Example: `daybook_03_07_2026_09_15_42.sqlite3`

---

## Part 2: Manual Backup Download

Use this when you want an on-demand copy of the database right now — for example, before performing a large import, before upgrading the application, or to store a copy somewhere outside the automatic backup folder (like a USB drive or cloud storage).

### Steps

1. Go to **Manager → Sync** (the Sync History page).
2. At the top right, click the **Download Backup** button.
3. Your browser will immediately download a `.sqlite3` file — this is a complete, ready-to-use copy of the database at that exact moment.
4. Save or move this file wherever you'd like to keep it (external drive, cloud storage, email to yourself, etc.).

### Backup File Naming

Manual backups are downloaded as:
```
daybook_backup_<YYYY_MM_DD_HH_MM_SS>.sqlite3
```
Example: `daybook_backup_2026_07_03_09_15_42.sqlite3`

### Important Notes

- The manual **Download Backup** button always gives you the database in its exact current state — it does **not** get rotated or deleted automatically like the automatic backups do. It's yours to keep, so store it somewhere safe.
- Manual backups are **not** counted toward or affected by the automatic backup rotation — they're entirely separate.

---

## Which One Should I Use?

| Situation | Recommended Backup |
|---|---|
| General day-to-day protection | Automatic backups (already happening — just confirm the folder on the About page occasionally) |
| Before a risky action (large import, bulk edit, upgrade) | Manual **Download Backup**, so you have a copy in hand before proceeding |
| Want an off-machine or cloud copy | Manual **Download Backup**, then move the file to your external/cloud storage |
| Want backups stored on a specific drive automatically going forward | Set the **Backup Directory** in Configurations, then automatic backups will go there on every startup |

---

## Restoring from a Backup

A `.sqlite3` backup file (from either method) is a full copy of the database. To restore from one, replace the current database file with the backup file while Daybook is closed, then restart the application. If you're not sure how to safely locate or replace the live database file, contact your system administrator or support before proceeding, since replacing the wrong file can result in data loss.

---

## Troubleshooting

| Problem | Likely Cause / Fix |
|---|---|
| Backup folder shown on About page doesn't match what I expected | Check **Configurations → Backup Directory** — if it's blank, backups use the default folder next to the database; if a custom path was entered but wasn't a full/absolute path, the system automatically fell back to the default folder. |
| I don't see recent automatic backups in the folder | Confirm Daybook has actually been restarted recently — automatic backups only run at startup, not while the app is already running. Also check the application log for a backup failure message. |
| Download Backup button doesn't seem to do anything | Check your browser's download settings/permissions, or look in your default Downloads folder — the file downloads directly without a confirmation popup. |