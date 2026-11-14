# Changelog

All notable changes to TokoOps are recorded here.

## v1.0.0 — 2026-11-14

Initial public release (generic TokoOps edition).

### Added

- Single-file offline web app (`app/tokoops.html`) with CSV import
  (SHA-256 duplicate rejection and row-count classification), snapshot
  chain with shipped-quantity differ (Sudah RTS / Belum RTS), deadline
  engine (Model / Flag / Hybrid, PASTI vs PERKIRAAN), per-SKU dashboard,
  catalogue tab with alias table and new-SKU inbox, returns and tailor
  deposits books, stock opname screen, presentation mode, and multi-shop
  profiles. Data in `localStorage` with JSON backup export / import.
- Windows program `TokoOps.exe`: a std-only Rust host embedding CPython
  and the real Python generators, serving the same app on `127.0.0.1`,
  with a "PDF Python Asli" page for the genuine Python-generated PDFs.
- Four Python report generators in `generators/`:
  `resi_merah3.py` (resi merah, 4-part report with the cross-check
  invariant main table = single table + multi table per SKU, 80 x 150 mm
  thermal PDF plus WhatsApp text), `laporan_final5.py` (production
  report, full), `laporan_baru.py` (production report, new products
  only), and `laporan_shanghai.py` (production report, Shanghai only).
- Synthetic sample data in `examples/` (`sample-orders.csv`,
  `sample-resi.csv`) and build / configuration documentation in `docs/`.

### Fixed (deliberate generic-edition fix)

- The production generators' +16-day listing rule now keys off the SKU
  family and correctly spelled "Shanghai" listing names, instead of a
  misspelled substring match. Shops using the Shanghai family get the
  +16-day lead from the family rule itself; see `docs/CONFIGURATION.md`
  for `LISTING_BARU_PREFIXES` and `LISTING_KEYWORD_LEAD16`.
