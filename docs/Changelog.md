# Changelog

All notable changes to Daybook Lite are documented in this file.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Versioning follows semantic versioning:
- **PATCH** (x.x.N) — bug fixes, no schema change
- **MINOR** (x.N.0) — new features, backward-compatible (safe/additive migrations)
- **MAJOR** (N.0.0) — breaking or destructive schema changes

---

## [Unreleased]
### Issues
Sl.No	Issue							Status
1. 		Export issue in transaction		Fixed
2. 		Import issue in transaction		Fixed
3. 		Multiple BT accounts is added	Fixed
4.      Implement Close PL accounts     Completed
5.      Account level print             Not Started
### Fixed
-

### Changed
-

---

## [1.4.2] - 2026-06-22
### Fixed
- Pawn number remark formatting on partial release was appending duplicate ranges.

## [1.4.1] - 2026-06-10
### Fixed
- `NOT NULL constraint` error on `loan_tr_type` when creating a loan via bulk entry.

## [1.4.0] - 2026-06-01
### Added
- Bulk loan creation screen with dynamic add/remove form rows.

### Changed
- `Configuration` model gained a new field (data migration included — safe/additive).

---

<!--
COPY THIS BLOCK ABOVE [Unreleased] WHEN CUTTING A NEW RELEASE:

## [X.Y.Z] - YYYY-MM-DD
### Added
-
### Fixed
-
### Changed
-

Tips:
- Write entries as you fix/build things, not at release time — you'll forget details otherwise.
- One line per change, plain language, no jargon you wouldn't remember in 3 months.
- If a release includes a migration, say so explicitly under Changed, even if it's additive.
-->