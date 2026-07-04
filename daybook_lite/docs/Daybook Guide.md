# Daybook Neo — Entries App User Guide

## Overview

The **Entries** app is the daily working screen of Daybook Neo. This is where you log financial transactions, record cash denominations, and generate the daily report. It's designed for fast, keyboard-friendly data entry during business hours.

This guide covers:

1. [Navigating the Entries App](#1-navigating-the-entries-app)
2. [Add Transaction](#2-add-transaction)
3. [View Transactions](#3-view-transactions)
4. [Daily Report](#4-daily-report)
5. [Denomination](#5-denomination)

---

## 1. Navigating the Entries App

The top navigation bar is available on every page and gives you quick access to:

| Menu | Purpose |
|---|---|
| **Home** | The main data-entry screen — Shops overview + Add Transaction form + Today's Transactions list |
| **Transactions** | Full, filterable list of all transactions |
| **Denomination** | List of cash-count (denomination) records |
| **Report** | Daily transaction, loan/release, and denomination report |
| **Shop selector** (top right) | Switches your default shop across the app |
| **About / Help** | System info and this documentation |
| **User menu** (top right) | User Settings and Logout |

> **Tip:** The current section is always highlighted in the navbar so you always know where you are.

---

## 2. Add Transaction

**Path:** Home (`/`)

The Home page is your primary workspace. It has three parts:

### 2.1 Shops Overview
A horizontally scrollable strip of shop cards showing each shop's **Opening Balance** and **Closing Balance** for the day. Click a card to open that shop's detail page *(Admins only)*. Admins also get a quick **⋮ menu** on each card to Edit or Delete the shop.

### 2.2 Add Transaction Form
Use this form to log a Debit or Credit entry.

**Steps:**
1. **Date** — defaults to today; change if backdating an entry.
2. **Time** *(optional)* — defaults to the current time if left blank.
3. **Shop** — auto-filled with your default shop (shown as read-only text).
4. **Account** — select the ledger account this transaction applies to. The list refreshes automatically based on the selected shop.
5. **Remarks** — a short note describing the transaction (required).
6. **Debit** and/or **Credit** amount — enter a value in one or both fields:
   - If you enter **only Debit**, one DEBIT transaction is created.
   - If you enter **only Credit**, one CREDIT transaction is created.
   - If you enter **both**, two separate transactions (DEBIT then CREDIT) are created for the same account/remarks.
7. Click **Submit**. Use **Reset** to clear the form and start over.

The system validates that Date, Shop, Account, Remarks, and at least one amount are filled before submitting — you'll get an on-screen prompt if something's missing.

> **Keyboard Shortcuts:** Speed up data entry with `Alt` + a letter:
> - `Alt+S` → focus Shop
> - `Alt+A` → focus Account
> - `Alt+M` → focus Remarks
> - `Alt+E` → focus Debit amount
> - `Alt+C` → focus Credit amount
> - `Alt+2` → jump to the Add Loan/Release Entries screen

### 2.3 Today's Transactions
On the right side, see every transaction logged today in real time.

- Each row shows the **Shop code**, **Account name**, **time + remarks**, and **amount** (green `+` for Credit, red `−` for Debit).
- **Click any row** to open a detail panel (slides in from the right) showing full transaction info: ID, Shop, Date, Remarks, Tally status, Created/Updated by & when.
- From the detail panel or row-hover actions you can:
  - **Edit** — jump to the edit screen for that transaction.
  - **History** — view the full audit trail of changes to that transaction.
  - **Delete** *(Admins only)* — remove the transaction after confirmation.

If nothing's been logged yet today, you'll see an "Add new transactions" placeholder message.

---

## 3. View Transactions

**Path:** Transactions

This is the full, searchable ledger of every transaction, with pagination, filters, printing, and export.

### 3.1 Filtering
Use the filter bar at the top to narrow results:

| Filter | Description |
|---|---|
| **Financial Year** | Step year-by-year using the `−` / `+` buttons (follows the Indian FY: April–March) |
| **From Date / To Date** | Restrict to a custom date range |
| **Transaction Type** | All / DEBIT / CREDIT |
| **Shop** | All Shops or a specific shop |
| **Account Type** | Filters the Account list below it (loads automatically once a shop is chosen) |
| **Account** | Multi-select searchable dropdown — pick one or more specific accounts, or use **Select All / Deselect All** |
| **Search Remarks** | Free-text search within the Remarks field |
| **Amount** | Combine an operator (`=`, `>`, `<`) with a value to filter by amount |
| **Sort By** | Date (Newest First) or Date (Oldest First) |

Click **Filter** to apply. Use **Clear Filters** to reset everything back to defaults.

### 3.2 Financial Summary
Above the table, three summary cards show the **Total Debits**, **Total Credits**, and running totals for whatever filter is currently applied.

### 3.3 Transaction Table
Lists every matching transaction with Date, Shop, Account, Remarks, Debit, and Credit columns. The list loads more rows automatically as you scroll (with a loading indicator), so you don't need to click through numbered pages.

- **Click any row** to open the same detail panel described in [Add Transaction](#23-todays-transactions), with Edit / History / Delete actions (History and Delete are Admin-only).

### 3.4 Export & Print
Using the currently applied filters, you can:
- **CSV** — download a CSV file of the filtered transactions.
- **Excel** — download a formatted Excel workbook.
- **Print** — open a print-optimized view (paper size/orientation follows the Transaction print configuration set by your Admin).

---

## 4. Daily Report

**Path:** Report

A single-day, per-shop snapshot combining transactions, loans/releases, and cash denominations — ideal for closing out the day or handing over a shift.

### 4.1 Choosing the Date & Shop
- Use the **◀ / ▶** navigation arrows to move to the previous/next day, or use the **Date** and **Shop** filters and click **Filter**.
- Click **Print** to generate a print-ready version of the whole report (paper size/orientation follows the Daily Report print configuration).

### 4.2 Shop Balances Summary
A table showing, for the selected date and shop(s):
- **Opening Balance**
- **Day's Debit** and **Day's Credit**
- **Expected (Closing) Balance** — calculated from transactions
- **Actual Balance (From Denomination)** — the physically counted cash total submitted via the Denomination page
- **Balance** — the difference between expected and actual; shown in **red** if there's a shortfall and **green** if it matches or is in surplus

### 4.3 Denominations
Displays every denomination (cash count) submission for the selected date, grouped by time period (Morning/Afternoon/Evening/Night) and the user who submitted it, with each note/coin/bundle type, count, and amount, plus a total per submission.

### 4.4 Loan & Release Summary
Two side-by-side tables listing every **Loan** and **Release** entry for the day (Pawn No., Shop, Principal, Interest) with totals at the bottom.

### 4.5 Other Transactions
A full list of the day's non-loan transactions (Time, Shop, Created By, Account, Remarks, Debit, Credit) with Debit/Credit totals at the bottom, and a footer noting who generated the report.

---

## 5. Denomination

Denomination entries record your **physical cash count** at a point in time (Morning, Afternoon, Evening, or Night), broken down by note/coin denomination. This is compared against system-calculated balances in the [Daily Report](#4-daily-report) to catch discrepancies early.

### 5.1 Denominations List
**Path:** Denomination

Shows every submitted denomination record with Date, Period, User, Shop, and Total.

- **View** (eye icon) — open a read-only view of that submission.
- **Edit** (pencil icon) — only visible on your own submissions.
- **Delete** (trash icon) *(Admin group / Super Admin only)* — opens a confirmation modal summarizing the record before deleting.

Click **Add Denomination** to create a new entry.

### 5.2 Adding a Denomination

**Path:** Denomination → Add Denomination

1. Select the **Shop** and **Time Period** (Morning/Afternoon/Evening/Night).
2. Select the **Date**.
3. Fill in counts for each denomination as applicable: ₹500, ₹200, ₹100, ₹50, ₹20, ₹10 notes, **Coins**, **Damage** (damaged notes set aside), and **Inside** (cash kept inside/not in hand). Each note field automatically calculates its subtotal (Count × Value) live as you type.
4. If you deal in bundles (100 notes of a denomination), fill in the **Bundle** fields for 500/200/100/50/20/10 — each bundle is automatically valued as 100 × denomination.
5. The **Total** at the bottom of the form updates live as you fill in values.
6. Click **Submit**.

> **Duplicate protection:** Only one denomination record is allowed per Shop + Date + Time Period + User combination. If one already exists, you'll be prompted to edit the existing record instead.

**Customizing which fields you see:** Click **Hide Fields** (top-right of the form) to open a checklist and toggle off any denomination types you never use (e.g., if you don't handle ₹200 bundles). Your preference is remembered for future visits.

### 5.3 Viewing / Editing a Denomination
- **View mode** shows all fields read-only, along with the record's Key, Created By, Created At, and Updated At.
- **Edit mode** lets you update counts, date, time period, or shop. If you change the Date, Time Period, or Shop such that it would create a new Key, the old record set is replaced by the new one (with a duplicate check applied, same as adding).

---

*This guide covers the day-to-day Entries app workflow: logging transactions, reviewing the transaction ledger, generating the daily report, and recording cash denominations. For shop/account setup, financial summaries, and audit tools, refer to the separate Manager App guide.*