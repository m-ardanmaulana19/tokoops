#!/usr/bin/env bash
# assemble_bundle.sh — build the embedded CPython bundle for TokoOps.exe.
#
# Downloads the CPython 3.12.7 embeddable package (Windows amd64) and the
# win_amd64 wheels the report generators need, unpacks the wheels into
# Lib/site-packages, patches python312._pth, and zips the tree to
# exe/assets/python-bundle.zip — the path the Rust build embeds.
#
# Prerequisites: python3 + pip, curl, unzip, zip. Network access required.
# The bundle/ working directory and the resulting zip are git-ignored.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYVER="3.12.7"
WORK="$ROOT/bundle/work"
WHEELS="$ROOT/bundle/wheels"
OUT="$ROOT/exe/assets/python-bundle.zip"

mkdir -p "$WORK" "$WHEELS" "$(dirname "$OUT")"

# 1) Wheels (win_amd64 / cp312 only).
pip download --platform win_amd64 --python-version 3.12 --implementation cp \
  --abi cp312 --only-binary :all: --dest "$WHEELS" \
  numpy pandas matplotlib reportlab pillow contourpy cycler fonttools \
  kiwisolver packaging pyparsing python-dateutil pytz tzdata six

# 2) CPython embeddable.
if [ ! -f "$ROOT/bundle/python-${PYVER}-embed-amd64.zip" ]; then
  curl -fL -o "$ROOT/bundle/python-${PYVER}-embed-amd64.zip" \
    "https://www.python.org/ftp/python/${PYVER}/python-${PYVER}-embed-amd64.zip"
fi
rm -rf "$WORK/python"
mkdir -p "$WORK/python"
unzip -q "$ROOT/bundle/python-${PYVER}-embed-amd64.zip" -d "$WORK/python"

# 3) Unpack wheels into Lib/site-packages.
mkdir -p "$WORK/python/Lib/site-packages"
for whl in "$WHEELS"/*.whl; do
  unzip -qo "$whl" -d "$WORK/python/Lib/site-packages"
done

# 4) Make the embeddable interpreter see site-packages.
PTH="$WORK/python/python312._pth"
grep -qx 'Lib\site-packages' "$PTH" || printf 'Lib\\site-packages\n' >> "$PTH"
sed -i 's/^#import site/import site/' "$PTH"

# 5) Zip the tree where the Rust build expects it.
rm -f "$OUT"
( cd "$WORK/python" && zip -qr "$OUT" . )
echo "Bundle written: $OUT ($(du -h "$OUT" | cut -f1))"
