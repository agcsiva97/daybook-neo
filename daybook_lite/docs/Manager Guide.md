# Daybook Neo — Manager App User Guide

## Overview

The **Manager** app is the administrative side of Daybook Neo. While the **Entries** app is where day-to-day transactions, loans, and daily reports are logged, the Manager app is where admins configure shops, ledgers, and accounts, and review financial summaries and audit trails to make quick, informed decisions.

Most Manager app pages are restricted to **Admin** or **Super Admin** users. If you don't have access to a page, you'll see a "permission denied" (403) message.

---

## Table of Contents

- [Daybook Neo — Manager App User Guide](#daybook-neo--manager-app-user-guide)
  - [Overview](#overview)
  - [Table of Contents](#table-of-contents)
  - [1. Dashboard](#1-dashboard)
  - [2. Shops](#2-shops)
    - [2.1 Shops List](#21-shops-list)
    - [2.2 Add a Shop](#22-add-a-shop)
    - [2.3 Shop Details Page](#23-shop-details-page)
  - [3. Ledgers](#3-ledgers)
    - [3.1 Add a Ledger](#31-add-a-ledger)
    - [3.2 Ledger Info](#32-ledger-info)
    - [3.3 Edit / Delete a Ledger](#33-edit--delete-a-ledger)
  - [4. Accounts](#4-accounts)
    - [4.1 Add an Account](#41-add-an-account)
    - [4.2 Account Info](#42-account-info)
    - [4.3 Edit / Delete an Account](#43-edit--delete-an-account)
  - [5. Linked Accounts (Loan/Release Mapping)](#5-linked-accounts-loanrelease-mapping)
  - [6. Balance Sheet](#6-balance-sheet)
  - [7. Shop-Level Reports](#7-shop-level-reports)
  - [8. Closing P\&L Accounts](#8-closing-pl-accounts)
  - [9. Moving \& Tallying Transactions](#9-moving--tallying-transactions)
    - [9.1 Move Transactions](#91-move-transactions)
    - [9.2 Update Tally Status](#92-update-tally-status)
  - [10. Configurations](#10-configurations)
  - [11. Activity Logs](#11-activity-logs)
  - [12. Roles \& Permissions](#12-roles--permissions)

---

## 1. Dashboard

**Path:** Manager → Dashboard

The Dashboard is the landing page of the Manager app. It gives you a quick, visual snapshot of your business:

- **Shop list overview** — all shops registered in the system.
- **Charts** (rendered from live data):
  - Loan vs. Release counts over a selectable date range and shop.
  - Debit vs. Credit transaction totals for the selected range.
  - Net worth trend across financial years.
  - Monthly principal/interest movement per linked (loan/release) account.
  - Average daily loan gauge for the selected period.

Use the date range and shop filters at the top of each chart to narrow down what you're looking at — for example, comparing last week's loan activity for a single shop versus all shops.

---

## 2. Shops

A **Shop** is the top-level business unit in Daybook Neo — each physical branch/outlet is set up as a Shop.

### 2.1 Shops List
**Path:** Manager → Shops

Shows every shop with:
- Short name and full name
- Door number and address
- Associated ledgers
- Current balance (calculated live from transactions)

### 2.2 Add a Shop
**Path:** Shops → Add Shop *(Super Admin only)*

Fill in:
- Short Name (used as a prefix in generated IDs, e.g. transaction/loan IDs)
- Name, Proprietor
- GOD/GST Number, PAN Number
- Door No., Address Line 1 & 2, Place, Pincode

When a shop is created, Daybook Neo automatically:
- Creates a default ledger for the shop.
- Syncs the standard account **Types** (Assets, Liabilities, P&L groups, etc.) for the shop.

### 2.3 Shop Details Page
**Path:** Shops → (select a shop)

Displays:
- Shop's ledgers
- All accounts under the shop, grouped and sorted by group order, priority, and name, each with a live balance
- Current overall shop balance

From here you can:
- **Edit Shop** — update shop details.
- **Delete Shop** — only allowed if the shop has **no** ledgers, transactions, or loans linked to it. Otherwise deletion is blocked with an explanatory message. *(Super Admin only)*
- **Add Account** — see [Accounts](#4-accounts).
- **Add Ledger** — see [Ledgers](#3-ledgers).
- **Shop Meta** — hierarchical breakdown of Groups → Types → Accounts with balances, plus summary counts (total groups, types, accounts, and combined shop balance).
- **Sync Account Types** — re-syncs the standard chart-of-account Types for the shop (useful after Daybook Neo introduces new standard types).

---

## 3. Ledgers

A **Ledger** represents a licensed pawnbroking ledger under a shop (each shop can have one or more).

### 3.1 Add a Ledger
**Path:** Shop Details → Add Ledger

Fields:
- Ledger Name
- License Number

### 3.2 Ledger Info
**Path:** Shops → (shop) → Ledgers → (select ledger)

Shows:
- All loan and release transactions recorded under this ledger, paginated
- Loan count vs. Release count
- Linked accounts (see below)

### 3.3 Edit / Delete a Ledger
- **Edit** updates the ledger name/license number.
- **Delete** is blocked if the shop already has associated transactions, to protect data integrity.

---

## 4. Accounts

**Accounts** are the individual ledger heads (e.g., Cash, Gold Loan, Interest Income) that transactions post against. Every account belongs to a **Type** (which itself belongs to a **Group** — Assets, Liabilities, Income, Expenses, P&L, etc.).

### 4.1 Add an Account
**Path:** Shop Details → Add Account

Fields:
- English Name / Local (Tamil) Name
- Account Type (choose from the shop's synced Types)
- Optional **Opening Balance** — if entered, a `CREDIT` "Opening Balance" transaction is automatically created for the account.
- **Admin Only** flag — when checked, this account and its transactions are hidden from non-admin (Staff) users throughout both the Entries and Manager apps.

### 4.2 Account Info
**Path:** Accounts → (select account)

Shows:
- Current balance
- All transactions for the account for the selected Financial Year, with filters:
  - Date range
  - Debit / Credit type
  - Amount (equals / greater than / less than)
  - Remarks search
  - Sort order (date ascending/descending)
- Opening, Closing, and Net balances for the selected period
- A **Move Transactions** tool to reassign selected transactions to a different account (see [Section 9](#9-moving--tallying-transactions))

### 4.3 Edit / Delete an Account
- **Edit** — update name, type, priority, or admin-only flag.
- **Delete** — blocked if the account has any transactions linked to it.

---

## 5. Linked Accounts (Loan/Release Mapping)

To automatically post the right ledger entries whenever a Loan or Release is recorded in the Entries app, each Ledger must be linked to four specific accounts:

| Mapping | Purpose |
|---|---|
| Loan Principal Account | Where loan principal amounts are debited |
| Loan Interest Account | Where loan interest is credited |
| Release Principal Account | Where release principal amounts are credited |
| Release Interest Account | Where release interest is credited |

**Path:** Ledger Info → Link Accounts

Select the appropriate account for each of the four mappings and save. Until this is configured, the Loan/Release entry screens in the Entries app cannot post transactions for that ledger.

---

## 6. Balance Sheet

**Path:** Manager → Balance Sheet

A consolidated, group-wise summary (Assets, Liabilities, Income, Expenses, P&L, etc.) across **all shops** for a selected Financial Year, showing:
- Opening balance per group
- Closing balance per group
- **Net Worth** (sum of specific groups representing owned equity)
- **Cash in Hand** (a broader combination including liquid/cash-equivalent groups)

Use the Financial Year selector at the top to switch years — Daybook Neo follows the Indian financial year convention (April–March).

---

## 7. Shop-Level Reports

These reports are available per shop and can be viewed on-screen (PDF-style print view) or exported. *(Export formats covered here are Excel/CSV — see note below.)*

**Path:** Shop Details → Reports menu

| Report | What it shows |
|---|---|
| **Trial Balance** | Every account Type's debit/credit closing position for the FY. |
| **Trial Balance (W/O P&L)** | Same as above, excluding Profit & Loss group accounts. |
| **Balance Sheet** | Full group → type → account hierarchy with opening/closing balances for the shop. P&L opening balances are always shown as zero. |
| **Balance Sheet (W/O P&L)** | Same as above, excluding the P&L group entirely. |
| **Group & Type Summary** | A more condensed view — Group and Type level totals only (accounts with zero closing are hidden). |
| **Networth Summary (Shops Yearly Summary)** | A pivot table: rows = financial years, columns = each shop's net worth, with row/column totals — useful for tracking growth trends across shops and years. |

Each of the above (except Networth Summary) accepts a `?fy=YYYY` filter to view a specific financial year; it defaults to the current FY.

> **Note:** These reports can be downloaded as PDF, Excel, or CSV. The download/export mechanics themselves are covered in the dedicated Sync/Export guide — this guide only covers viewing/navigating to the reports.

---

## 8. Closing P&L Accounts

**Path:** Shop Details → Close P&L Accounts *(Admin only)*

At the end of a financial year, use this tool to transfer Profit & Loss account balances into Capital accounts:

1. Select the Financial Year to close (defaults to current FY).
2. The system calculates each P&L account's net balance (only non-zero balances are listed) and the combined total.
3. It also suggests an **equal share** of the total across all Capital accounts as a starting point.
4. Enter the amount to be credited/debited to each Capital account. **The sum of amounts you enter must exactly match the calculated total** — if it doesn't, you'll get a validation error showing both figures.
5. On submission, the system:
   - Posts closing (debit/credit) entries for each P&L account to zero them out for the year.
   - Posts the corresponding entries to each Capital account you specified.
   - All entries are dated to the last day of the selected FY (or today's date, if closing the current FY).

This action is wrapped in a database transaction — if anything fails, no partial entries are created.

---

## 9. Moving & Tallying Transactions

These bulk tools are available from the **Account Info** page.

### 9.1 Move Transactions
Select one or more transactions and reassign them to a different account within the same shop — useful for correcting misclassified entries without deleting and re-entering them. Every move is recorded in the Activity Log.

### 9.2 Update Tally Status
Mark selected transactions as **Tallied** or **Not Tallied** — a simple checkbox-style flag admins can use to track reconciliation progress. This status change is also recorded in the Activity Log.

---

## 10. Configurations

**Path:** Manager → Configurations *(Admin only)*

A single screen listing all system-wide settings, grouped by category (**Daybook** settings and **Application** settings):

| Setting | Description |
|---|---|
| Daily Report Paper Size / Orientation | Print layout for the daily Report page (Entries app) |
| Transaction Paper Size / Orientation | Print layout for the Transactions list |
| Loan Paper Size / Orientation | Print layout for Loan Transactions |
| Denomination Purge Days | How many days denomination records are retained before automatic cleanup |
| Session Timeout | Auto-logout duration (in seconds) for inactive sessions |
| Default Shop | The shop pre-selected across the app when no shop filter is applied |
| Backup Directory | Filesystem path used for database backups *(see separate Sync/Backup guide)* |

Edit any value inline and save — all configuration fields are on one page, so you can update several settings in a single submission.

---

## 11. Activity Logs

**Path:** Manager → Activity Logs *(Admin only)*

A full audit trail of actions performed across the system, including:
- Creation, update, and deletion of Transactions, Loans, Types, Accounts, Denominations, and Linked Accounts
- Shop and Ledger changes
- User management actions (creation, promotion, activation/deactivation)

Each entry shows the acting user, action type, affected record, shop, description, and timestamp. Use the **user filter** at the top to see activity from a specific user only. The log is paginated for easy browsing.

For deeper investigation of a single record, open the record itself (e.g. a Transaction or Loan) and use its **History** view, which shows every historical version of that specific record side-by-side, powered by full change tracking.

---

## 12. Roles & Permissions

Daybook Neo enforces three permission levels relevant to the Manager app:

| Role | Access |
|---|---|
| **Staff** | No access to the Manager app; limited to non-admin-only data in the Entries app. |
| **Admin** (Admin group or `Admin`/`Staff` group combo, depending on the action) | Access to most Manager app features — Shops, Ledgers, Accounts, Reports, Configurations, Activity Logs, moving/tallying transactions, closing P&L accounts. |
| **Super Admin** (`is_superuser`) | Full access, including the ability to **Add** or **Delete** Shops — actions restricted from regular Admins. |

If a page or action isn't available to you, check with a Super Admin about your assigned group/role.

---

*This guide covers the Manager app's shop, ledger, account, reporting, configuration, and audit features. For syncing shop data between devices, exporting/importing transactions, and database backups, refer to the separate Sync & Backup guide.*