# Building TokoOps

This guide builds `TokoOps.exe` from source: first the embedded CPython
bundle, then the Rust host cross-compiled for Windows. It also documents
the Linux smoke test used to validate the result, and the known
limitations of the current build.

There are two parts to the shipped program:

- `exe/` — a std-only Rust crate (zero crates). It contains a hand-written
  HTTP/1.1 server and a hand-written ZIP / DEFLATE reader, and it embeds
  the app HTML, the 4 Python generators, and the bundle zip.
- The **bundle** — CPython plus the Python libraries the generators need,
  zipped and embedded in the executable.

## Prerequisites

| Tool | Version / notes |
| --- | --- |
| rustup | stable toolchain |
| rustc | 1.100.0 (stable) |
| Rust target | `x86_64-pc-windows-gnu` |
| zig | 0.13.0, used as the cross linker |
| cargo-zigbuild | 0.24.1 |
| Python (build host, for bundle assembly) | 3.12 series tooling as used by `tools/assemble_bundle.sh` |
| CPython embeddable package | 3.12.7, amd64 |

Install the target once:

```sh
rustup target add x86_64-pc-windows-gnu
cargo install cargo-zigbuild --version 0.24.1
```

Zig 0.13.0 must be on `PATH` so `cargo zigbuild` can use it as the linker
for the Windows GNU target.

## 1. Assemble the Python bundle

Run:

```sh
tools/assemble_bundle.sh
```

The script:

1. Takes the CPython 3.12.7 embeddable (amd64) package.
2. Unzips the `win_amd64` wheels into `Lib/site-packages`.
3. Patches `python312._pth`:
   - add `Lib\site-packages`
   - uncomment `import site`
4. Packs the result as the bundle zip.

Where the bundle zip lands:

```text
exe/assets/python-bundle.zip
```

The Rust build embeds that file, so this step must be done before
compiling the executable.

### Bundled Python packages

| Package | Version |
| --- | --- |
| CPython (embeddable, amd64) | 3.12.7 |
| numpy | 2.5.4 |
| pandas | 3.1.1 |
| matplotlib | 3.11.2 |
| reportlab | 5.1.0 |
| pillow | 13.0.0 |
| contourpy | 1.4.0 |
| cycler | 0.12.1 |
| fonttools | 4.68.0 |
| kiwisolver | 1.5.1 |
| packaging | 26.3 |
| pyparsing | 3.3.3 |
| python-dateutil | 4.0.0 |
| pytz | 2026.6 |
| tzdata | 2026.6 |
| six | 1.17.0 |
| charset_normalizer | 3.5.2 |

The generators' own Python requirements are also listed in
`generators/requirements.txt` for anyone running them directly with a
normal Python install.

## 2. Cross-compile the executable

From the `exe/` crate:

```sh
cargo zigbuild --release --target x86_64-pc-windows-gnu
```

The resulting binary is `TokoOps.exe`. It embeds:

- the app HTML (`app/tokoops.html`)
- the 4 generators from `generators/`
- `exe/assets/python-bundle.zip`

### Runtime behaviour (for reference while testing)

- First run extracts the bundle to:

  ```text
  %LOCALAPPDATA%\TokoOps\bundle-v1
  ```

- It serves the app on `127.0.0.1`, trying ports **17654-17664**.
- It opens the default browser at the served address.
- The console window stays open while the program runs.

Development overrides (environment variables):

| Variable | Meaning |
| --- | --- |
| `TOKOOPS_PYTHON` | Path to a Python executable to use instead of the bundled one |
| `TOKOOPS_SCRIPTS` | Directory holding the generator scripts |
| `TOKOOPS_DATA` | Data directory for the local run |

## 3. Generator command-line signatures

The same generators embedded in the executable can be run directly:

```text
resi_merah3.py      <CSV> <"14 Nov 2026"> <OUT.pdf>
laporan_final5.py   <CSV> <TODAY YYYY-MM-DD> <STAMP> <OUT.pdf>
laporan_baru.py     <CSV> <TODAY YYYY-MM-DD> <STAMP> <OUT.pdf>
laporan_shanghai.py <CSV> <TODAY YYYY-MM-DD> <STAMP> <OUT.pdf>
```

- `resi_merah3.py` takes the report date as a display string such as
  `"14 Nov 2026"`.
- The three `laporan_*.py` generators take today as `YYYY-MM-DD`, plus a
  stamp string used in the report, plus the output PDF path.

## 4. Linux smoke test

The Windows executable is validated by construction plus a native Linux
smoke test of the same source. The procedure:

1. Build the same Rust source natively on Linux (the host target, not the
   Windows target).
2. Run the server with the system `python3`, using the development
   overrides (`TOKOOPS_PYTHON`, `TOKOOPS_SCRIPTS`, `TOKOOPS_DATA`) to
   point it at the local Python and the repo generators.
3. POST the example CSVs to the PDF endpoints:

   ```text
   POST /api/pdf/resi
   POST /api/pdf/produksi
   ```

   using `examples/sample-resi.csv` and `examples/sample-orders.csv`.
4. Run the generators directly on the same CSVs (the oracle).
5. Compare the server PDFs against the oracle PDFs:
   - page count must match
   - page size must match

A pass means the HTTP layer, the bundle layout, the generator invocation,
and the PDF output all agree with the generators run on their own.

## Known limitations

State these plainly; do not work around them in documentation:

- **Windows run validated by construction + Linux smoke test.** The
  cross-compiled Windows binary is validated by its construction and by
  the native Linux smoke test described above.
- **The executable is unsigned.** Windows SmartScreen will warn on first
  run: choose **More info -> Run anyway**.
- **The console window stays open** while the program is running. Closing
  it stops the local server.
- **Production PDFs are slow:** about **10-45 s** per report, because of
  matplotlib rendering. The resi report is much faster.
