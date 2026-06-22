# Running the Shell and Executing the Cleanup Script

## Step 1 — Open the Django Shell

Run this command from your project directory (where `manage.py` is located):

```bash
python manage.py shell
```

This opens an interactive Python shell with your Django project already configured, including settings, models, and database connections.

---

## Step 2 — Run the Cleanup Script

Paste the following script into the Django shell.

> **Note:** Adjust the import path to match the location of your model.

```python
from manager.models import BT_Ledger_Accounts  # Adjust import path as needed
from django.db.models import Count

duplicates = (
    BT_Ledger_Accounts.objects.values("ledger", "rel_type")
    .annotate(count=Count("id"))
    .filter(count__gt=1)
)

print(f"Found {duplicates.count()} duplicate ledger+rel_type combinations")

for dup in duplicates:
    records = BT_Ledger_Accounts.objects.filter(
        ledger=dup["ledger"],
        rel_type=dup["rel_type"]
    ).order_by("-updated_at")  # Keep the most recently updated record

    keep = records.first()
    to_delete = records.exclude(id=keep.id)

    print(
        f"Ledger {dup['ledger']} / {dup['rel_type']}: "
        f"keeping {keep.id}, deleting {[r.id for r in to_delete]}"
    )

    to_delete.delete()

print("Cleanup complete.")
```

### Recommended: Perform a Dry Run First

Before deleting any records, review what would be removed by commenting out the `delete()` call.

```python
for dup in duplicates:
    records = BT_Ledger_Accounts.objects.filter(
        ledger=dup["ledger"],
        rel_type=dup["rel_type"]
    ).order_by("-updated_at")

    keep = records.first()
    to_delete = records.exclude(id=keep.id)

    print(
        f"Ledger {dup['ledger']} / {dup['rel_type']}: "
        f"keeping {keep.id}, would delete {[r.id for r in to_delete]}"
    )

    # to_delete.delete()  # Commented out for dry run
```

Review the output carefully to ensure the correct records are being retained.

Once you're satisfied, uncomment the `to_delete.delete()` line and execute the cleanup script again.

---

## Step 3 — Verify No Duplicates Remain

Run the following code to confirm that all duplicate `ledger + rel_type` combinations have been removed:

```python
remaining = (
    BT_Ledger_Accounts.objects.values("ledger", "rel_type")
    .annotate(count=Count("id"))
    .filter(count__gt=1)
)

print(f"Remaining duplicates: {remaining.count()}")
```

Expected output:

```text
Remaining duplicates: 0
```

If the count is `0`, the cleanup was successful and it is safe to proceed with the migration.

---

## Step 4 — Exit the Shell

```python
exit()
```

---

## Step 5 — Create and Apply the Migration

After confirming the data is clean, generate and apply the migration that adds the uniqueness constraint.

```bash
python manage.py makemigrations
python manage.py migrate
```

This ensures that future duplicate `ledger + rel_type` combinations cannot be inserted into the database.