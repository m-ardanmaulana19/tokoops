# Contributing to TokoOps

Thank you for helping improve TokoOps. This is a small project, so the
rules are short.

## Issues

- Open an issue with a clear description of what happened and what you
  expected.
- Attach sample data only if it has been removed of real data or is fully
  synthetic. Use the files in `examples/` as the model: invented SKUs,
  invented buyers, invented order IDs.
- Never attach a real order export, a real customer name or address, or
  any personal data.

## Pull requests

- Pull requests are welcome: fixes, documentation, and small, focused
  improvements are easiest to review.
- Keep one change per pull request where you can, and describe how you
  tested it.
- If you touch the generators (`generators/*.py`), run them on both
  sample files and report page counts before / after in the pull request:

  ```text
  examples/sample-orders.csv
  examples/sample-resi.csv
  ```

  A change that silently alters page counts or page sizes needs an
  explanation in the pull request.

## Rules that do not bend

- **Numbers must stay deterministic.** No AI in the computation path.
  The optional bring-your-own-key layer may phrase text only; it must
  never compute, round, estimate, or adjust a number.
- **Never commit credentials, real order exports, or personal data.**
  No API keys, no tokens, no cookies, no Seller Center exports with real
  orders, and no names, addresses, or phone numbers of real people.
- **Offline stays offline.** The app and the executable must keep working
  with no network connection, apart from the optional endpoint a user
  configures themselves for text phrasing.
- **Unknown SKUs stay visible.** Do not add code that silently merges an
  unknown SKU into an existing one; the new-SKU inbox and its one-time
  human confirmation are part of the design.

## Local checks

- Open `app/tokoops.html` in a browser and import the two sample CSVs
  (demo "today": 2026-11-13).
- For executable work, follow the smoke-test procedure in
  `docs/BUILDING.md` and compare page count and page size against the
  generators run directly.
