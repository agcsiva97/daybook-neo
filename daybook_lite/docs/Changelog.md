# Changelog

All notable changes to Daybook Neo are documented in this file.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Versioning follows semantic versioning:

- **MAJOR** (**N**.0.0) — breaking or destructive schema changes
- **MINOR** (x.**N**.0) — new features, backward-compatible (safe/additive migrations)
- **PATCH** (x.x.**N**) — bug fixes, no schema change
---
## Open Issues
-
## Upcoming Release
- Account level print
- Multiple delete for transactions
---
# Version History
## [2.2.2] - 2026-06-23
- Added **Add account** button in transaction form for admin group users
- Loan Form will fetch latest date from loan model
- Financial year filter is added in Transactions list page
- If only one account is selected then, Transaction print page will not account name column in table instead it will printed in header
- UI fixes and enhancements
- Added account search in shop info page

## [2.2.1] - 2026-06-22
- Added transactions filter in account info page.
- Added Docs section
- Transactions Print page:
  - Checkbox added for header and footer inclusions/exclusions.
  - If multiple account is selected then transactions sorted by account tamil name along with based on sort by selection, else based on sort by selection.
- Shop meta top navbar.
- UI fixes and enhancements.
---

## [2.2.0] - 2026-06-21
- Implement Close PL accounts
- Export & Import issue in transactions and loans
- Multiple BT accounts is added	
---

## [2.1.0] - 2026-06-08
- Added Default shop selection in navbar
- Included Loan models in Import and Export functionality
- UX Improvements

## [2.0.0] - 2026-06-06
- Implemented Accounts, Types for Transactions
- Improved Dashboard
- Improved Transaction search filter
- Added Import and Export functionality
- Default shop functionality added
- Fixed minor bubgs