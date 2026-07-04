# Data Sync Guide — Exporting & Importing Shop Data Between Machines

This guide explains how to move shop data (Types, Accounts, Transactions, Loans, and Linked Accounts) from one machine to another using the **Sync** page's Export and Import tools.

---

## When to Use This

Use Export/Import when you need to:
- Move a shop's data from one machine/branch to another (e.g., local machine → head office server)
- Keep two machines in sync by periodically pushing only new changes
- Restore or transfer historical data for a specific date range

---

## Where to Find It

1. Log in as an **Admin**.
2. Go to **Manager → Sync** (top navigation bar).
3. You'll see the **Export & Import History** table, plus three action buttons at the top right:
   - **Download Backup**
   - **Export**
   - **Import**

---

## Part 1: Exporting Data (On the Source Machine)

Exporting creates a `.json` file containing the shop's data, which you'll then transfer (via USB, email, cloud drive, etc.) to the destination machine.

### Steps

1. Click the **Export** button. An "Export Data" popup will open.
2. **Select Shop** — choose the shop whose data you want to export.
3. **Choose an Export Type:**

   | Option | What it exports | When to use it |
   |---|---|---|
   | **All** | Every Type, Account, Transaction, Loan, and Linked Account for the shop, including internal record IDs | First-time sync, or a full refresh/backup of a shop |
   | **Export From** | Only records **created, updated, or deleted** on or after a date you pick | You know roughly when the last sync happened and want everything since then |
   | **After Last Export** | Only records changed since the **last time you exported this shop** (tracked automatically by the system) | Routine, repeated syncing — the safest way to avoid re-sending old data |

4. If you chose **Export From**, pick the **Export From Date**.
5. Click **Export**.
   - The button will show **Processing...** and the popup will stay open and locked (Cancel and the X button are disabled) until the file is ready — this prevents accidentally closing the dialog mid-export.
   - Once ready, the `.json` file downloads automatically to your browser's downloads folder, and the popup closes on its own.
6. The exported file is named like:
   ```
   transactions_<ShopCode>_<mode>_<timestamp>.json
   ```
   Example: `transactions_SGF_all_2026_07_03_14_30_00.json`

### What Happens Behind the Scenes

- For **All**, the system pulls the shop's complete Types, Accounts, Transactions, Loans, and Linked Accounts as-is, with their database IDs — useful for a full transfer or backup.
- For **After Last Export** and **Export From**, the system checks the shop's **activity log** and separately groups changes into **Created**, **Updated**, and **Deleted** for each data type (Types, Accounts, Transactions, Loans), so the destination machine knows exactly what to do with each record.
- Every export is recorded in the **Export & Import History** table on the Sync page, and the shop's "last exported" timestamp is updated — so your next **After Last Export** will correctly pick up only what's new.
- Linked Accounts (ledger-to-account mappings) are always exported in their current, complete state, regardless of which export type you chose.

---

## Part 2: Importing Data (On the Destination Machine)

Importing takes an exported `.json` file and applies its contents to the matching shop on this machine.

### Before You Import

- Make sure the shop referenced in the file already exists on the destination machine (the file must contain a valid `shop_id`; if the shop isn't found, the import will fail with an error).
- Make sure you're importing the correct file — the tool doesn't ask which shop to import into, it reads that directly from the file.

### Steps

1. Click the **Import** button. An "Import Data" popup will open.
2. Click **Select JSON File** and choose the file you exported (accepts a **full ("All")** export or an **incremental ("After Last Export" / "Export From")** export — both formats are supported automatically).
3. Click **Import**.
   - The button will show **Processing...** and the popup will stay open and locked (Cancel and the X button are disabled) until the import finishes — don't close the browser tab or navigate away during this time.
4. When finished, a summary popup appears showing how many records were **Created**, **Updated**, and **Deleted** for each of: Types, Accounts, Transactions, and Loans.
5. Click OK — the page will refresh and the import will appear at the top of the **Export & Import History** table.

### Import Rules (How Conflicts Are Resolved)

| Situation | Result |
|---|---|
| Record ID in the file **already exists** in the destination database | The existing record is **updated** with the incoming data |
| Record ID is **missing or doesn't exist** yet | A **new** record is **created** (with an auto-generated ID if none was provided) |
| File is from an incremental export and includes a "deleted" list | Matching records are **deleted** on the destination |
| A Transaction's linked Account can't be found | If it's an update to an existing transaction, the transaction keeps its current account and a warning is logged; if it's a brand-new transaction, the import for that record fails and is skipped (with the reason recorded) |
| A Loan or Linked Account references a Ledger that doesn't exist locally | That specific record is skipped and marked failed — the rest of the import continues |

- All records created or updated through Import are automatically attributed to a **System** user — this is how you can tell which records came from a sync versus manual entry.
- If a single record fails (e.g., a missing reference), it does **not** stop the whole import — every other record is still processed, and the failure is listed in that import's detail log (accessible from the History table).

---

## Part 3: Viewing Sync History

On the **Sync** page, the **Export & Import History** table lists every export and import ever performed, showing:
- **Type** — Export or Import
- **Shop**
- **Data Type** — e.g. "All Data Export", "Changes Since Last Export", "Changes Since Specified Date"
- **Timestamp**

Click any row to open its **details page**, which lists exactly which records were affected (and, for imports, whether each one succeeded or failed and why).

---

## Recommended Sync Workflow

For routine, ongoing syncing between two machines (e.g., a shop's local computer and a central server):

1. **First sync only:** Export with **All** on the source machine, then Import that file on the destination machine.
2. **Every sync after that:** Export with **After Last Export** on the source machine — this automatically grabs only what changed since the last export, keeping files small and imports fast.
3. Transfer the file (USB drive, shared folder, email, etc.) and Import it on the destination machine.
4. Repeat step 2–3 on your regular schedule (e.g., daily or weekly).

If you ever miss a sync window or aren't sure what's covered by "After Last Export," use **Export From** and manually pick a safe starting date — it's slightly less precise but lets you control the range yourself.

---

## Troubleshooting

| Problem | Likely Cause / Fix |
|---|---|
| "Shop ID not found in import file" | The `.json` file doesn't match any shop on this machine, or the file is corrupted/not a valid export. Re-export or check the file. |
| Import summary shows fewer "Created/Updated" than expected | Check that shop's import details page — some records may have failed due to missing references (e.g., an Account or Ledger that doesn't exist yet on this machine). Import any prerequisite data first. |
| "Invalid JSON file" error | The selected file isn't valid JSON — make sure you selected the actual exported `.json` file, not something else. |
| Export/Import popup won't close during processing | This is expected — the popup is intentionally locked while the operation is in progress to prevent data loss or confusion. Wait for it to finish. |