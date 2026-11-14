# TokoOps

Offline ops toolkit for TikTok Shop sellers: daily "resi merah" packing lists and PERKIRAAN production-queue reports, generated from CSV files you export yourself from TikTok Seller Center.

## Why it exists

A small TikTok Shop lives or dies by two daily questions:

1. What has to ship today?
2. What has to be made next, and by when?

Seller Center can answer both, but only while you are online, logged in, and
clicking through screens. TokoOps was originally built for a small Indonesian
TikTok Shop that needed those answers on paper, on a phone, and in a chat
message — fast, repeatable, and identical every time the same export is used.

So TokoOps works the other way round: you export the CSV, TokoOps does the
arithmetic locally, and you get a printable packing list and a production
report. It never logs into Seller Center.

## Features

- **CSV import with safeguards** — SHA-256 duplicate rejection, plus
  row-count classification: a small filtered file is treated as a resi list,
  a file with >= 1000 rows is treated as a queue snapshot.
- **Snapshot chain with shipped-quantity differ** — successive snapshots are
  compared to split shipped quantity into Sudah RTS and Belum RTS, based on
  the substatus a row had in the earlier snapshot.
- **Deadline engine** — three modes (Model / Flag / Hybrid) and two
  confidence labels (PASTI vs PERKIRAAN). See `docs/CONFIGURATION.md`.
- **Resi merah report, in 4 parts** — (1) main per-SKU table, (2) RESI 1
  BARANG, (3) ISI RESI >1 BARANG, (4) combo list. Cross-check invariant:
  main table = single table + multi table, per SKU. Output as a printable
  80 x 150 mm thermal PDF plus a WhatsApp-ready text version.
- **Production report** — full, new-products-only, and Shanghai-only
  variants. Past-deadline rows are excluded from the printed report only
  (they stay in the data). Includes per-SKU bars, a per-deadline summary,
  and a SKU x deadline colour matrix.
- **Per-SKU dashboard** — totals and deadlines per SKU at a glance.
- **Catalogue tab** — alias table and a new-SKU inbox. Unknown SKUs are
  flagged for one-time human confirmation; they are never silently merged
  into an existing SKU.
- **Books** — returns book (kinds: RTS tidak sampai / Non-RTS / Isi Tidak
  Jelas) and a tailor deposits book.
- **Stock opname screen** — physical count vs system count, with a
  difference list, mirroring a paper recap.
- **Presentation mode** — daily / weekly / monthly slides built from the
  same numbers.
- **Multi-shop profiles** — each profile keeps its own catalogue, settings,
  and data, separate from the others.
- **Optional text phrasing only** — an optional bring-your-own-AI-key layer
  (OpenAI-compatible endpoint, key stored only in the browser, empty by
  default) may phrase text. It never computes numbers.

## Two forms

1. **Single-file web app** — `app/tokoops.html`. One self-contained HTML
   file that runs fully offline in a browser. Data lives in `localStorage`,
   with JSON backup export / import.
2. **Windows program** — `TokoOps.exe`. A small std-only Rust host that
   embeds CPython and the real Python report generators, serves the same
   app on `127.0.0.1`, and adds a "PDF Python Asli" page that produces the
   genuine Python-generated PDFs.

Design rule: **numbers by code**. Everything numeric is deterministic code.
The optional AI layer described above may only phrase text, never compute
numbers.

## Quick start (users)

1. Download `TokoOps.exe` from the GitHub Releases page of
   `m-ardanmaulana19/tokoops`.
2. Run `TokoOps.exe`. No install step is needed.
3. If Windows SmartScreen appears, choose **More info -> Run anyway**.
   The executable is unsigned; see the limitations in `docs/BUILDING.md`.
4. Your default browser opens automatically on a local `127.0.0.1` address.
   Keep the console window open while you use the app; closing it stops
   the local server.

Alternative, with no executable at all:

- Open `app/tokoops.html` in any up-to-date browser. It runs fully offline.
  The browser form cannot call the Python generators, so use the `.exe`
  form when you need the genuine Python PDFs from the "PDF Python Asli"
  page.

## Quick start with examples

Synthetic sample files live in `examples/`:

1. Import `examples/sample-orders.csv` as a queue snapshot.
2. Import `examples/sample-resi.csv` for the resi merah demo.
3. Use **2026-11-13** as the demo "today" date.

With those two files and that date, the dashboard, the resi merah report,
and the production report all populate, so you can see the full flow
without using any real order data.

## Build from source

Summary: assemble the embedded CPython bundle with
`tools/assemble_bundle.sh`, then cross-compile the Rust host with
`cargo zigbuild --release --target x86_64-pc-windows-gnu`.

Full instructions, versions, the Linux smoke-test procedure, and known
limitations are in [docs/BUILDING.md](docs/BUILDING.md).

## Configuration

Each shop adapts TokoOps through its SKU catalogue, per-SKU shipping-time
settings, listing / family overrides, aliases, and report colours.

Summary and the full worked example (an 18-SKU catalogue) are in
[docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## How it works

```text
TikTok Seller Center  --(CSV export, by you)-->  CSV file
                                                      |
                              +-----------------------+-----------------------+
                              |                                               |
                     app/tokoops.html                            TokoOps.exe (Rust host)
                     offline, in browser                         embeds CPython + generators
                     localStorage + JSON backup                  serves the same app on 127.0.0.1
                                                                         |
                                                              generators/*.py (Python)
                                                              resi + production PDFs
```

- The **Rust host** is std-only (zero crates): a hand-written HTTP/1.1
  server and a hand-written ZIP / DEFLATE reader. On first run it extracts
  its bundle locally, serves the app, and opens the default browser.
- The **Python generators** in `generators/` are the source of truth for
  the printed PDFs. Their command-line signatures are documented in
  `docs/BUILDING.md`.
- The **web app** holds the day-to-day workflow: import, snapshots,
  dashboard, books, opname, and presentation mode.

Numbers by code, end to end: the same CSV and the same date always produce
the same numbers, in the browser, in the executable, and from the
generators run directly.

## Project layout

```text
app/                        single-file web app (app/tokoops.html)
generators/                 4 Python report generators + requirements.txt
exe/                        Rust crate for TokoOps.exe
tools/assemble_bundle.sh    builds the embedded CPython bundle
examples/                   synthetic sample CSVs
docs/                       BUILDING.md, CONFIGURATION.md
```

Generator files:

```text
generators/resi_merah3.py       resi merah report
generators/laporan_final5.py    production report (full)
generators/laporan_baru.py      production report (new products only)
generators/laporan_shanghai.py  production report (Shanghai only)
generators/requirements.txt
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: synthetic sample data
only, deterministic numbers only, and report generator page counts
before / after when you touch the generators.

## Roadmap

- **MCP bridge process** — so an external AI can drive the app through the
  exposed `window.TOKOOPS` API, still without computing numbers itself.
- **Richer styled HTML reports** — a styled HTML rendering alongside the
  current thermal PDF, WhatsApp text, and Python PDF outputs.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

TokoOps is an unofficial community tool. It is **not affiliated with
TikTok or ByteDance**.

It works only from CSV files that you export yourself. It never logs into
Seller Center and never scrapes Seller Center.

No warranty. Use at your own risk. Check the generated lists and reports
against your own records before acting on them.

---

## Panduan Singkat (Bahasa Indonesia)

TokoOps adalah perangkat bantu offline untuk penjual TikTok Shop: daftar
packing harian "resi merah" dan laporan antrean produksi PERKIRAAN, dibuat
dari berkas CSV yang Anda ekspor sendiri dari TikTok Seller Center.
TokoOps tidak pernah masuk (login) ke Seller Center.

Cara pakai singkat:

1. Unduh `TokoOps.exe` dari halaman GitHub Releases proyek ini, lalu
   jalankan. Jika muncul SmartScreen, pilih **More info -> Run anyway**.
   Browser akan terbuka otomatis di alamat lokal `127.0.0.1`.
2. Atau, tanpa program Windows: buka `app/tokoops.html` di browser.
   Aplikasi ini berjalan sepenuhnya offline.
3. Untuk mencoba tanpa data asli, impor `examples/sample-orders.csv`
   sebagai snapshot antrean dan `examples/sample-resi.csv` untuk demo
   resi merah, dengan tanggal "hari ini" contoh **2026-11-13**.
4. Ekspor CSV dari Seller Center, impor ke TokoOps, lalu cetak daftar
   resi merah (format thermal 80 x 150 mm atau teks WhatsApp) dan laporan
   produksinya.

Prinsipnya: **angka dihitung oleh kode**, selalu dengan cara yang sama.
Lapisan AI opsional (kunci milik sendiri, kosong secara bawaan, hanya
tersimpan di browser) hanya boleh merangkai kalimat, tidak pernah
menghitung angka.

Lisensi MIT. Alat komunitas tidak resmi; bukan afiliasi TikTok atau
ByteDance. Tanpa jaminan apa pun; gunakan dengan risiko sendiri, dan
periksa kembali hasil laporan terhadap catatan Anda sebelum dipakai.
