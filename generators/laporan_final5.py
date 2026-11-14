import sys, re, textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.colors import to_rgb, to_hex, LinearSegmentedColormap, PowerNorm

CSV, TODAY_S, STAMP, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
RED = sys.argv[5] if len(sys.argv) > 5 else None
MASTER = sys.argv[6] if len(sys.argv) > 6 else None
T = pd.Timestamp
TODAY = T(TODAY_S)

# ------------------------------------------------------------------ MODEL BATAS (lihat docs/CONFIGURATION.md)
def lead_A(ct, sku):
    if ct < T('2026-10-04 19:36'): return 17, 'pasti'
    if ct < T('2026-10-05 00:00'): return 18, 'perkiraan'
    if ct.normalize() == T('2026-10-05') and sku == 'SG-JMB' and ct < T('2026-10-05 13:00'): return 10, 'pasti'
    if ct < T('2026-10-05 05:17:49'): return 17, 'perkiraan'
    if ct <= T('2026-10-08 05:16:58'): return 17, 'pasti'
    if ct < T('2026-10-08 08:07:43'): return (17 if ct < T('2026-10-08 06:40') else 13), 'perkiraan'
    if ct <= T('2026-10-13 21:22:42'): return 13, 'pasti'
    if ct < T('2026-10-14 01:11:36'): return (13 if ct < T('2026-10-14 00:00') else 12), 'perkiraan'
    if ct <= T('2026-10-15 15:59:59'): return 12, 'pasti'
    if ct < T('2026-10-15 18:30:01'): return (12 if ct < T('2026-10-15 17:15') else 16), 'perkiraan'
    if ct <= T('2026-10-16 22:03:02'): return 16, 'pasti'
    if ct < T('2026-10-16 22:46:27'): return (16 if ct < T('2026-10-16 22:25') else 14), 'perkiraan'
    if sku == 'YEL-SPJ' and ct < T('2026-10-17 12:00'): return 5, 'perkiraan'
    if ct <= T('2026-10-21 07:00:54'): return 14, 'pasti'
    return 14, 'perkiraan'

def lead(ct, sku, listing='A'):
    n, conf = lead_A(ct, sku)
    if listing == 'B':
        conf = 'perkiraan'
        if ct >= T('2026-10-17 00:00'): n = 16
    elif listing == 'C':
        conf = 'perkiraan'; n = 17 if ct < T('2026-10-17 00:00') else 16
    return n, conf

# ------------------------------------------------------------------ KONFIGURASI TOKO
# Sesuaikan dengan toko Anda (lihat docs/CONFIGURATION.md). Katalog di bawah
# adalah KATALOG CONTOH — ganti dengan SKU toko Anda sendiri.
# Awalan nama listing "model baru" (grup B): batas selalu 16 hari.
LISTING_BARU_PREFIXES = []
# Awalan nama listing khusus (grup C): 17 hari sebelum 17/10, lalu 16 hari.
LISTING_KEYWORD_LEAD16 = []
# Kode warna keluarga Kerah Shanghai (selalu 16 hari, pasti).
SHG_CODES = {'SYEL', 'SHTM'}

def listing_of(name):
    if any(name.startswith(p) for p in LISTING_BARU_PREFIXES): return 'B'
    if any(name.startswith(k) for k in LISTING_KEYWORD_LEAD16): return 'C'
    return 'A'


# EXAMPLE CATALOGUE — replace with your own SKUs (docs/CONFIGURATION.md).
# Pengaturan waktu kirim per SKU: 0 = Reguler, 7/12/14 = hari PO.
# SKU di luar daftar dianggap 12 hari; keluarga Shanghai selalu 16 hari.
SETTING = {}
for _s in ["YEL-JMB","HTM-STD"]: SETTING[_s] = 0
for _s in ["HTM-SPJ"]: SETTING[_s] = 7
for _s in ["JTL-STD","JTL-JMB","JTL-SPJ"]: SETTING[_s] = 14

def lead_new(ct, sku, name):
    if sku.split('-')[0] in SHG_CODES: return 16, 'pasti'
    if 'Shanghai' in name: return 16, 'pasti'
    if any(name.startswith(p) for p in LISTING_BARU_PREFIXES): return 16, 'pasti'
    if any(name.startswith(k) for k in LISTING_KEYWORD_LEAD16): return 16, 'perkiraan'
    st = SETTING.get(sku, 12)
    if st == 0: return 1, ('pasti' if ct >= T('2026-11-08') else 'perkiraan')
    if st == 7: return 9, ('pasti' if ct >= T('2026-11-08') else 'perkiraan')
    if st == 14: return 16, 'pasti'
    return 14, 'pasti'

def lead_mix(ct, sku, listing, name):
    if ct >= T('2026-11-03'):
        return lead_new(ct, sku, name)
    return lead(ct, sku, listing)

def load(csv):
    df = pd.read_csv(csv, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    for c in df.columns: df[c] = df[c].astype(str).str.strip()
    df['Seller SKU'] = df['Seller SKU'].str.replace(r'^SHG-([A-Z]+)-([A-Z]+)$', r'S\1-\2', regex=True)
    df['qty'] = df['Quantity'].astype(int)
    df['ct'] = pd.to_datetime(df['Created Time'], format='%d/%m/%Y %H:%M:%S')
    df['rts'] = df['Order Substatus'].eq('Menunggu pengambilan')
    df['listing'] = df['Product Name'].map(listing_of)
    paid = pd.to_datetime(df['Paid Time'].replace('', pd.NA), format='%d/%m/%Y %H:%M:%S', errors='coerce')
    start = paid.where(paid.notna() & (paid >= df['ct']), df['ct'])            # hitung dari tanggal dibayar (non-COD)
    r = [lead_mix(t, s, l, n) for t, s, l, n in zip(df['ct'], df['Seller SKU'], df['listing'], df['Product Name'])]   # N per-SKU (kalibrasi 08/11) utk >= 03/11
    df['lead'] = [x[0] for x in r]; df['conf'] = [x[1] for x in r]
    df['batas'] = start.dt.normalize() + pd.to_timedelta(df['lead'], unit='D')
    df['batas_clip'] = df['batas'].where(df['batas'] >= TODAY, T('1970-01-01'))
    sk = df['Seller SKU'].str.split('-', expand=True)
    df['color'] = sk[0]; df['size'] = sk[1]
    return df

# uji ke contoh asli (dari berkas contoh kalibrasi opsional)
if MASTER:
    txt = open(MASTER, encoding='utf-8').read()
    blk = txt[txt.index('Contoh asli listing A'):txt.index('Update tabel:')]
    ok = bad = 0
    for dd, mm, hh, mi, sku, bd, bm in re.findall(r'(\d\d)/(\d\d) (\d\d):(\d\d) ([A-Z]+-[A-Z]+) (\d\d)/(\d\d)', blk):
        if (dd, mm, hh, mi, sku) == ('02', '10', '15', '55'): continue   # dibayar hari berikutnya
        ct = T(f'2026-{mm}-{dd} {hh}:{mi}:30')
        n, _ = lead(ct, sku)
        got = ct.normalize() + pd.Timedelta(days=n)
        exp = T(f'2026-{bm if int(bm) >= int(mm) or True else mm}-{bd}')
        # bulan batas: cari tanggal bd terdekat setelah ct
        cand = [T(f'2026-{m2}-{bd}') for m2 in ('10', '11') if T(f'2026-{m2}-{bd}') >= ct.normalize()]
        exp = cand[0]
        if got == exp: ok += 1
        else: bad += 1
    print('uji contoh (toleransi detik):', ok, 'cocok,', bad, 'beda')

# ------------------------------------------------------------------ TAMPILAN
plt.rcParams.update({'font.family': 'DejaVu Sans', 'pdf.fonttype': 42, 'hatch.linewidth': 0.55})
HARI = ['SENIN', 'SELASA', 'RABU', 'KAMIS', 'JUMAT', 'SABTU', 'MINGGU']
HARI3 = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']
# EXAMPLE CATALOGUE — replace with your own SKUs (docs/CONFIGURATION.md).
COL = [('YEL', 'KUNING', '#DBA514'), ('HTM', 'HITAM', '#1F1F1F'), ('SG', 'SAGE', '#9CAF88'),
       ('JTL', 'HIJAU BOTOL', '#3E7C43'),
       ('SYEL', 'SHG KUNING', '#DBA514'), ('SHTM', 'SHG HITAM', '#1F1F1F')]
CODES = [c for c, _, _ in COL]; CN = {c: n for c, n, _ in COL}; CH = {c: h for c, _, h in COL}
SHG = {c for c in CODES if c.startswith('S') and c not in ('SG', 'SLM')}  # kode Kerah Shanghai
FIRST_SHG = next((c for c in CODES if c in SHG), None)
SZ = [('STD', 'L', 'Standar'), ('JMB', 'XXL', 'Jumbo'), ('SPJ', '5L', 'SuperJumbo')]
NAVY, GREY, LINE = '#1F2A44', '#6B7280', '#D1D5DB'
f = lambda n: f"{int(n):,}".replace(',', '.')
def sku_label(c, s):
    _, code, name = [x for x in SZ if x[0] == s][0]; return f"{code} {CN[c]} {name}"
def lum(h):
    r, g, b = to_rgb(h); return 0.299 * r + 0.587 * g + 0.114 * b
def light(h, k=0.6):
    r, g, b = to_rgb(h); return to_hex((r + (1 - r) * k, g + (1 - g) * k, b + (1 - b) * k))

df = load(CSV)
df = df[df.batas >= TODAY].copy()  # lewat batas dikeluarkan dari PDF
if RED:
    rr = pd.read_csv(RED, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    df.loc[df['Order ID'].isin(set(rr['Order ID'].str.strip())), 'conf'] = 'pasti'
LEWAT = T('1970-01-01')
DAYS = [T(d) for d in sorted(df['batas_clip'].unique())]
def sub(d): return df if d is None else df[df.batas_clip == d]
def est_of(fr): return int(fr[fr.conf == 'perkiraan'].qty.sum())
def sku_series(fr):
    p = fr.groupby(['color', 'size', 'conf']).qty.sum()
    return {(c, s): (int(p.get((c, s, 'pasti'), 0)), int(p.get((c, s, 'perkiraan'), 0))) for c in CODES for s, _, _ in SZ}
def color_series(fr):
    p = fr.groupby(['color', 'conf']).qty.sum()
    return {c: (int(p.get((c, 'pasti'), 0)), int(p.get((c, 'perkiraan'), 0))) for c in CODES}
def size_totals(fr):
    p = fr.groupby('size').qty.sum(); return {s: int(p.get(s, 0)) for s, _, _ in SZ}
def chip_for(d):
    if d == LEWAT: return 'LEWAT BATAS', '#7A0000', '#FFFFFF'
    n = (d - TODAY).days
    txt = 'HARI INI' if n == 0 else ('BESOK' if n == 1 else f'{n} HARI LAGI')
    if n <= 1: return txt, '#D32F2F', '#FFFFFF'
    if n <= 3: return txt, '#F57C00', '#FFFFFF'
    if n <= 5: return txt, '#F9C100', '#222222'
    return txt, '#2E7D32', '#FFFFFF'

def header(fig, kicker, big, chip):
    ax0 = fig.add_axes([0, 0, 1, 1]); ax0.set_xlim(0, 1); ax0.set_ylim(0, 1); ax0.axis('off')
    ax0.add_patch(Rectangle((0, 0.905), 1, 0.095, color=NAVY, lw=0))
    ax0.text(0.05, 0.968, kicker, color='#FBBF24', fontsize=7.5, va='center', fontweight='bold')
    ax0.text(0.05, 0.931, big, color='white', fontsize=17, fontweight='bold', va='center')
    if chip:
        ct_, cbg, cfg = chip
        ax0.add_patch(FancyBboxPatch((0.66, 0.918), 0.30, 0.028, boxstyle='round,pad=0,rounding_size=0.012', fc=cbg, ec='none'))
        ax0.text(0.81, 0.932, ct_, color=cfg, fontsize=8.5, fontweight='bold', ha='center', va='center')
    ax0.text(0.5, 0.028, 'PERKIRAAN, tidak 100% akurat', fontsize=7, color='#B45309', fontweight='bold', ha='center', va='center')
    ax0.text(0.5, 0.013, f'TokoOps  ·  {STAMP}', fontsize=6.3, color=GREY, ha='center', va='center')
    return ax0

def base_page(kicker, big, chip, fr, total_label='TOTAL'):
    fig = plt.figure(figsize=(5.4, 9.6)); ax0 = header(fig, kicker, big, chip)
    tot = int(fr.qty.sum()); est = est_of(fr)
    ax0.text(0.05, 0.878, total_label, fontsize=8, color=GREY, va='center')
    ax0.text(0.05, 0.842, f(tot), fontsize=32, fontweight='bold', va='center')
    ax0.text(0.05, 0.806, 'set', fontsize=9, color=GREY, va='center')
    if est > 0: ax0.text(0.115, 0.806, f'·  {f(est)} perkiraan', fontsize=7.5, color='#B45309', va='center', fontweight='bold')
    st = size_totals(fr)
    for i, (s, code, name) in enumerate(SZ):
        x = 0.43 + i * 0.185
        ax0.add_patch(FancyBboxPatch((x, 0.80), 0.17, 0.09, boxstyle='round,pad=0,rounding_size=0.01', fc='#F3F4F6', ec=LINE, lw=0.8))
        ax0.text(x + 0.085, 0.866, f"{code} {name}", fontsize=6.6, color=GREY, ha='center', va='center')
        ax0.text(x + 0.085, 0.830, f(st[s]), fontsize=15, fontweight='bold', ha='center', va='center')
    ax0.plot([0.04, 0.96], [0.793, 0.793], color=LINE, lw=0.8)
    return fig, ax0

def legend_est(ax0, y=0.068):
    ax0.add_patch(Rectangle((0.22, y - 0.007), 0.04, 0.014, fc='#9CA3AF', ec='#222', lw=0.6)); ax0.text(0.27, y, 'batas pasti', fontsize=6.8, va='center')
    ax0.add_patch(Rectangle((0.50, y - 0.007), 0.04, 0.014, fc='#E5E7EB', ec='#222', lw=0.6, hatch='////')); ax0.text(0.55, y, 'perkiraan', fontsize=6.8, va='center')

def draw_bar(ax, y, vp, ve, c, h=0.74, left=0):
    hx = CH[c]; lw = 0.9 if c == 'PTH' else 0.5
    if vp > 0: ax.barh(y, vp, left=left, height=h, color=hx, edgecolor='#222222', linewidth=lw)
    if ve > 0: ax.barh(y, ve, left=left + vp, height=h, color=light(hx), edgecolor='#222222', linewidth=lw, hatch='////')

def sku_page(pdf, kicker, big, chip, fr, note=None, total_label='TOTAL SET'):
    fig, ax0 = base_page(kicker, big, chip, fr, total_label)
    ser = sku_series(fr); rows, groups, y = [], [], 0; headings = []; shg_done = False
    for c in CODES:
        items = [(s, ser[(c, s)]) for s, _, _ in SZ if sum(ser[(c, s)]) > 0]
        if not items: continue
        if c in SHG and not shg_done:
            y -= 1.05; headings.append(y + 0.62); shg_done = True
        y0 = y
        for s, (vp, ve) in items: rows.append((y, c, s, vp, ve)); y -= 1
        groups.append((c, y0, y + 1, sum(vp + ve for _, (vp, ve) in items))); y -= 0.55
    top, bot = 0.5, y + 0.55 - 0.5
    vmax = max(r[3] + r[4] for r in rows); units = top - bot + 0.4
    h_in = min(0.70 * 9.6, units * 0.36)
    ax = fig.add_axes([0.375, 0.78 - h_in / 9.6, 0.545, h_in / 9.6])
    ax.set_xlim(0, vmax * 1.55); ax.set_ylim(bot - 0.2, top + 0.2); ax.axis('off')
    pitch_in = h_in / units
    fs_lab = max(6.6, min(7.6, pitch_in * 72 * 0.46)); fs_val = max(7.5, min(10.5, pitch_in * 72 * 0.52))
    for hy in headings:
        ax.plot([0, vmax * 1.02], [hy + 0.40, hy + 0.40], color=NAVY, lw=0.9, clip_on=False)
        ax.text(-vmax * 0.03, hy - 0.14, 'KERAH SHANGHAI', fontsize=fs_lab + 0.9, fontweight='bold', color=NAVY, va='center', ha='right')
    for (yy, c, s, vp, ve) in rows:
        draw_bar(ax, yy, vp, ve, c)
        ax.text(vp + ve + vmax * 0.02, yy, f(vp + ve), fontsize=fs_val, fontweight='bold', va='center', ha='left')
        ax.text(-vmax * 0.03, yy, (sku_label(c, s).replace('SHG ', '') if c in SHG else sku_label(c, s)), fontsize=fs_lab, fontweight='bold', va='center', ha='right')
    xb = vmax * 1.22
    for c, ya, yb, tot in groups:
        ax.plot([xb, xb + vmax * 0.02, xb + vmax * 0.02, xb], [ya + 0.32, ya + 0.32, yb - 0.32, yb - 0.32], color='#9CA3AF', lw=1, clip_on=False)
        ax.text(xb + vmax * 0.05, (ya + yb) / 2, f'Σ {f(tot)}', fontsize=fs_val - 1, fontweight='bold', color='#374151', va='center', ha='left', clip_on=False)
    if est_of(fr) > 0: legend_est(ax0)
    if note: ax0.text(0.5, 0.046, note, fontsize=6.3, color=GREY, ha='center', va='center')
    pdf.savefig(fig); plt.close(fig)

def day_label(d):
    s = sub(d); share = est_of(s) / max(1, int(s.qty.sum()))
    return ('~' if share >= 0.5 else '') + f'{HARI3[d.weekday()]} {d.strftime("%d/%m")}'

def total_page(pdf):
    W, H = 5.4, 10.8
    fig = plt.figure(figsize=(W, H)); a0 = fig.add_axes([0, 0, 1, 1]); a0.set_xlim(0, 1); a0.set_ylim(0, 1); a0.axis('off')
    a0.add_patch(Rectangle((0, 1 - 1.0 / H), 1, 1.0 / H, color=NAVY, lw=0))
    a0.text(0.05, 1 - 0.30 / H, 'PERKIRAAN  ·  RENCANA PRODUKSI  ·  TOTAL  ·  ' + TODAY.strftime('%d/%m/%Y'), color='#FBBF24', fontsize=8, va='center', fontweight='bold')
    a0.text(0.05, 1 - 0.68 / H, 'PERKIRAAN TOTAL SKU', color='white', fontsize=19, fontweight='bold', va='center')
    a0.text(0.05, 0.883, 'TOTAL SEMUA', fontsize=8.5, color=GREY, va='center')
    a0.text(0.05, 0.848, f(df.qty.sum()), fontsize=34, fontweight='bold', va='center')
    a0.text(0.05, 0.815, 'set', fontsize=9.5, color=GREY, va='center')
    stt = df.groupby('size').qty.sum()
    for i, (s_, code, name) in enumerate(SZ):
        x = 0.43 + i * 0.185
        a0.add_patch(FancyBboxPatch((x, 0.808), 0.17, 0.082, boxstyle='round,pad=0,rounding_size=0.01', fc='#F3F4F6', ec=LINE, lw=0.8))
        a0.text(x + 0.085, 0.873, f"{code} {name}", fontsize=7, color=GREY, ha='center', va='center')
        a0.text(x + 0.085, 0.840, f(stt.get(s_, 0)), fontsize=16, fontweight='bold', ha='center', va='center')
    a0.plot([0.04, 0.96], [0.800, 0.800], color=LINE, lw=0.8)
    a0.text(0.5, 0.016, 'TokoOps  ·  semua set belum terkirim  ·  ' + STAMP, fontsize=6.4, color=GREY, ha='center', va='center')
    a0.text(0.5, 0.036, 'PERKIRAAN, tidak 100% akurat  ·  Σ = total 1 warna', fontsize=7.2, color='#B45309', fontweight='bold', ha='center', va='center')
    tt = df.groupby(['color', 'size']).qty.sum(); rows, groups, y = [], [], 0
    for c, name, hx in COL:
        if c == FIRST_SHG:
            rows.append((y, 'HEAD', 'KERAH SHANGHAI', '', '', 0)); y -= 1
        y0 = y
        for s_, code, nm in SZ:
            v = int(tt.get((c, s_), 0)); rows.append((y, c, name, code, nm, v)); y -= 1
        groups.append((c, y0, y + 1, sum(r[5] for r in rows if r[1] == c))); y -= 0.5
    top, bot = 0.5, y + 0.5 - 0.5; vmax = max(r[5] for r in rows); LEFT = 0.455
    ax = fig.add_axes([LEFT, 0.055, 0.93 - LEFT, 0.735]); ax.axis('off'); ax.set_xlim(0, vmax * 1.62); ax.set_ylim(bot - 0.2, top + 0.2)
    rend = fig.canvas.get_renderer(); fs_lab = 10.5
    while True:
        t = a0.text(0, 0, '5L HIJAU BOTOL SuperJumbo', fontsize=fs_lab, fontweight='bold')
        wpx = t.get_window_extent(rend).width; t.remove()
        if wpx / fig.dpi <= (LEFT - 0.03) * W or fs_lab <= 7: break
        fs_lab -= 0.2
    for (yy, c, name, code, nm, v) in rows:
        if c == 'HEAD':
            ax.plot([0, vmax * 1.05], [yy + 0.45, yy + 0.45], color=NAVY, lw=1.1, clip_on=False)
            ax.text(-vmax * 0.04, yy - 0.05, 'KERAH SHANGHAI', fontsize=fs_lab + 1.5, fontweight='bold', color=NAVY, va='center', ha='right')
            continue
        ax.barh(yy, v, height=0.74, color=CH[c], edgecolor='#222', linewidth=0.9 if c == 'PTH' else 0.5)
        ax.text(v + vmax * 0.025, yy, f(v), fontsize=11.5, fontweight='bold', va='center', ha='left')
        ax.text(-vmax * 0.04, yy, f"{code} {name.replace('SHG ', '') if c in SHG else name} {nm}", fontsize=fs_lab, fontweight='bold', va='center', ha='right')
    xb = vmax * 1.24
    for c, ya, yb, tv in groups:
        ax.plot([xb, xb + vmax * 0.025, xb + vmax * 0.025, xb], [ya + 0.32, ya + 0.32, yb - 0.32, yb - 0.32], color='#9CA3AF', lw=1.1, clip_on=False)
        ax.text(xb + vmax * 0.06, (ya + yb) / 2, f'Σ {f(tv)}', fontsize=10.5, fontweight='bold', color='#374151', va='center', ha='left', clip_on=False)
    pdf.savefig(fig); plt.close(fig)

def summary_page(pdf):
    fig, ax0 = base_page('PERKIRAAN  ·  RENCANA PRODUKSI  ·  RINGKASAN', 'KEBUTUHAN PER BATAS', ('SEMUA HARI', '#475569', '#FFFFFF'), df, 'TOTAL SEMUA')
    for i, (c, name, hx) in enumerate(COL):
        x = 0.06 + (i % 3) * 0.31; yy = 0.772 - (i // 3) * 0.026
        ax0.add_patch(Rectangle((x, yy - 0.008), 0.028, 0.016, fc=hx, ec='#222222', lw=0.6)); ax0.text(x + 0.036, yy, name, fontsize=7.5, fontweight='bold', va='center')
    n = len(DAYS); h_in = min(0.56 * 9.6, n * 0.62)
    ax = fig.add_axes([0.20, 0.69 - h_in / 9.6, 0.70, h_in / 9.6]); ax.axis('off')
    vmax = max(int(sub(d).qty.sum()) for d in DAYS); ax.set_xlim(0, vmax * 1.16); ax.set_ylim(-n + 0.4, 0.6)
    for i, d in enumerate(DAYS):
        y = -i; cs = color_series(sub(d)); left = 0
        for c in CODES:
            vp, ve = cs[c]; v = vp + ve
            if v <= 0: continue
            draw_bar(ax, y, vp, ve, c, h=0.78, left=left)
            if v / vmax > 0.075: ax.text(left + v / 2, y, f(v), fontsize=6.6, ha='center', va='center', color='white' if (lum(CH[c]) < 0.5 and ve == 0) else 'black', fontweight='bold')
            left += v
        ax.text(left + vmax * 0.012, y, f(left), fontsize=10.5, fontweight='bold', va='center')
        col = chip_for(d)[1] if chip_for(d)[1] != '#F9C100' else '#B38600'
        ax.text(-vmax * 0.02, y, 'LEWAT' if d == LEWAT else day_label(d), fontsize=9, fontweight='bold', color=col, ha='right', va='center')
    legend_est(ax0, 0.068)
    ax0.text(0.5, 0.046, 'Batas = "Kirim pesanan sebelum" TikTok  ·  ~ = sebagian besar perkiraan', fontsize=6.3, color=GREY, ha='center', va='center')
    pdf.savefig(fig); plt.close(fig)

def heat_page(pdf):
    fig, ax0 = base_page('PERKIRAAN  ·  RENCANA PRODUKSI  ·  PETA KEBUTUHAN', 'SKU × BATAS', ('SKU × HARI', '#475569', '#FFFFFF'), df, 'TOTAL SEMUA')
    skus = [(c, s) for c in CODES for s, _, _ in SZ]
    mi = 12  # baris pemisah: 4 warna utama di atas, Kerah Shanghai di bawah
    skus = skus[:mi] + [None] + skus[mi:]
    M = np.array([[0] * len(DAYS) if cs is None else [int(df[(df.batas_clip == d) & (df.color == cs[0]) & (df['size'] == cs[1])].qty.sum()) for d in DAYS] for cs in skus])
    tot_col, tot_row = M.sum(axis=1), M.sum(axis=0)
    ax = fig.add_axes([0.355, 0.085, 0.545, 0.585])
    ax.imshow(M, cmap=LinearSegmentedColormap.from_list('r', ['#FFFFFF', '#F4B6B6', '#D32F2F']), norm=PowerNorm(0.55, vmin=0, vmax=M.max()), aspect='auto')
    nr, nc = M.shape
    for i in range(nr):
        for j in range(nc):
            v = M[i, j]
            if v: ax.text(j, i, f(v), ha='center', va='center', fontsize=6.3, color='white' if v > M.max() * 0.55 else 'black', fontweight='bold')
    ax.set_xticks(range(nc)); ax.set_xticklabels(['LEWAT' if d == LEWAT else day_label(d) for d in DAYS], rotation=90, fontsize=6.8, fontweight='bold')
    ylabs = ['KERAH SHANGHAI' if cs is None else (sku_label(cs[0], cs[1]).replace('SHG ', '') if cs[0] in SHG else sku_label(cs[0], cs[1])) for cs in skus]
    ax.xaxis.tick_top(); ax.set_yticks(range(nr)); ax.set_yticklabels(ylabs, fontsize=6.4, fontweight='bold'); ax.tick_params(length=0)
    ax.get_yticklabels()[mi].set_color(NAVY)
    for k in list(range(3, mi + 1, 3)) + list(range(mi + 4, nr, 3)): ax.axhline(k - 0.5, color='#6B7280', lw=0.7)
    ax.axhline(mi - 0.5, color=NAVY, lw=1.3); ax.axhline(mi + 0.5, color=NAVY, lw=1.3)
    for k in range(nc + 1): ax.axvline(k - 0.5, color='#E5E7EB', lw=0.4)
    for sp in ax.spines.values(): sp.set_visible(False)
    for i in range(nr):
        if skus[i] is None: continue
        ax.text(nc - 0.35, i, f(tot_col[i]), fontsize=6.4, fontweight='bold', va='center', ha='left', clip_on=False)
    ax.text(nc - 0.35, -1.9, 'TOTAL', fontsize=6.4, fontweight='bold', va='bottom', ha='left', rotation=90, clip_on=False)
    for j in range(nc): ax.text(j, nr + 0.15, f(tot_row[j]), fontsize=6.4, fontweight='bold', va='top', ha='center', clip_on=False)
    ax.text(-0.9, nr + 0.15, 'TOTAL/HARI', fontsize=6.4, fontweight='bold', va='top', ha='right', clip_on=False)
    ax0.text(0.5, 0.046, '~ = sebagian besar perkiraan (belum ada contoh pesanan tanggal itu)', fontsize=6.3, color=GREY, ha='center', va='center')
    pdf.savefig(fig); plt.close(fig)

def wrap(t, w): return '\n'.join(textwrap.wrap(t, w))

def explain_page(pdf):
    fig = plt.figure(figsize=(5.4, 9.6)); ax0 = header(fig, 'PERKIRAAN  ·  RENCANA PRODUKSI', 'CARA BACA LAPORAN', ('TIM PRODUKSI', '#475569', '#FFFFFF'))
    blocks = [
        ('1', 'APA ITU BATAS MENTOK?', 'Tanggal terakhir pesanan harus sudah dikirim ke kurir (di TikTok tertulis "Kirim pesanan sebelum", sampai jam 23:59). Lewat dari itu, pesanan bisa dibatalkan otomatis oleh TikTok.'),
        ('2', 'KENAPA TIAP PESANAN BEDA?', 'Batas = tanggal pesanan dibuat (non-COD: tanggal dibayar) + jumlah hari PO + 2 hari. PO diatur per SKU dan sering berubah, jadi jumlah hari tiap pesanan bisa beda.\nContoh: dibuat 16/10 dengan PO 14 hari = batas kirim 01/11 (14 + 2 = 16 hari).\nSemua halaman ini PERKIRAAN, tidak 100% akurat.'),
        ('3', 'ISI SETIAP HALAMAN', '1 halaman = 1 tanggal batas. Angka besar = total set hari itu. Tiga kotak = total per ukuran (L Standar, XXL Jumbo, 5L SuperJumbo). Setiap batang = jumlah set 1 SKU (warna + ukuran). Σ = total 1 warna.'),
        ('4', 'BATANG PENUH vs BERGARIS', 'Penuh = batas sudah pasti (dicocokkan dengan contoh pesanan dari TikTok). Bergaris = perkiraan, karena belum ada contoh pesanan di tanggal itu. Bisa bergeser beberapa hari.'),
        ('5', 'URUTAN KERJA', 'Kerjakan dari tanggal paling dekat. HARI INI = resi merah, paling mentok. Yang dihitung adalah semua set yang belum diambil kurir, termasuk yang resinya sudah dicetak (resi sudah dicetak belum tentu barang sudah siap).'),
        ('6', 'UPDATE', 'Laporan diperbarui dari data TikTok. Angka dan tanggal bisa berubah, selalu pakai laporan terbaru.')]
    y = 0.875
    for num, title, body in blocks:
        ax0.add_patch(plt.Circle((0.075, y - 0.003), 0.017, color=NAVY, transform=ax0.transAxes))
        ax0.text(0.075, y - 0.0045, num, color='white', fontsize=9, fontweight='bold', ha='center', va='center')
        ax0.text(0.12, y, title, fontsize=9.5, fontweight='bold', va='center', color=NAVY)
        t = '\n'.join(wrap(p, 62) for p in body.split('\n')); nl = t.count('\n') + 1
        ax0.text(0.12, y - 0.016, t, fontsize=8.8, va='top', linespacing=1.45, color='#222222')
        y -= 0.016 + nl * 0.0195 + 0.035
    pdf.savefig(fig); plt.close(fig)

def basis_page(pdf):
    fig = plt.figure(figsize=(5.4, 9.6)); ax0 = header(fig, 'PERKIRAAN  ·  UNTUK PEMILIK', 'DASAR TANGGAL BATAS', ('CEK DATA', '#475569', '#FFFFFF'))
    d2 = df.assign(cdt=df['ct'].dt.normalize())
    g = d2.groupby(['cdt', 'lead', 'conf']).agg(n=('qty', 'sum'), tmin=('ct', 'min'), tmax=('ct', 'max')).reset_index()
    cols = [0.05, 0.36, 0.47, 0.64, 0.76]; y = 0.875
    for x, h in zip(cols, ['DIBUAT', '+ HARI', 'BATAS', 'SET', 'STATUS']): ax0.text(x, y, h, fontsize=7, fontweight='bold', color=GREY, va='center')
    ax0.plot([0.04, 0.96], [y - 0.01, y - 0.01], color=LINE, lw=0.8)
    step = min(0.029, 0.54 / max(1, len(g))); y -= step * 1.1; fs = 7.8 if step > 0.024 else 6.6
    for _, r in g.iterrows():
        batas = r.cdt + pd.Timedelta(days=int(r.lead)); pasti = r.conf == 'pasti'
        whole = r.tmin.hour < 3 and r.tmax.hour >= 20
        label = r.cdt.strftime('%d/%m') + ('' if whole else f"  {r.tmin:%H:%M}-{r.tmax:%H:%M}")
        ax0.text(cols[0], y, label, fontsize=fs, va='center', fontweight='bold')
        ax0.text(cols[1], y, f'{int(r.lead)}', fontsize=fs + 0.5, va='center', fontweight='bold')
        ax0.text(cols[2], y, f'{HARI3[batas.weekday()]} {batas.strftime("%d/%m")}', fontsize=fs + 0.5, va='center', fontweight='bold')
        ax0.text(cols[3], y, f(r.n), fontsize=fs + 0.5, va='center')
        ax0.add_patch(FancyBboxPatch((cols[4], y - step * 0.33), 0.19, step * 0.66, boxstyle='round,pad=0,rounding_size=0.006', fc='#DCFCE7' if pasti else '#FEF3C7', ec='none'))
        ax0.text(cols[4] + 0.095, y, 'ada contoh' if pasti else 'perkiraan', fontsize=6.4, va='center', ha='center', color='#166534' if pasti else '#92400E', fontweight='bold')
        y -= step
    ax0.plot([0.04, 0.96], [y + step * 0.6, y + step * 0.6], color=LINE, lw=0.8)
    txt = ('Batas = PO + 2 hari. Jumlah hari (PO) mengikuti WAKTU pesanan dibuat; hitungannya mulai dari tanggal DIBAYAR untuk non-COD dan tanggal dibuat untuk COD. Pesanan belum RTS: batal otomatis = batas kirim - 2 hari.\n\n'
           'Model cocok dengan RESI MERAH asli 20/10 (30), 21/10 (11), 22/10 (192) dan 78 pesanan asli dari Seller Center. Pesanan dibuat setelah 21/10 07:00 BELUM ADA contoh: dianggap PO 12 + 2 = 14 hari (perkiraan).\n\n'
           'PO diatur per SKU dan berubah-ubah. Listing khusus (grup C) 17 hari (sampai 16/10) lalu 16; listing model baru (grup B) ikut listing utama lalu 16 hari mulai 17/10.\n\n'
           'Jendela pergantian yang tersisa: 04/10 19:36-23:59; 08/10 05:17-08:07; 13/10 21:22 - 14/10 01:11; 15/10 15:59-18:30; 16/10 22:03-22:46. Pesanan di sela itu bisa selisih beberapa hari.')
    ax0.text(0.05, y - step * 0.2, '\n'.join(wrap(p, 66) if p else '' for p in txt.split('\n')), fontsize=7, va='top', linespacing=1.4, color='#222222')
    pdf.savefig(fig); plt.close(fig)

with PdfPages(OUT) as pdf:
    total_page(pdf); explain_page(pdf); summary_page(pdf); heat_page(pdf)
    for d in DAYS:
        fr = sub(d)
        if d == LEWAT: big, kick = 'LEWAT BATAS', 'PERKIRAAN  ·  RENCANA PRODUKSI  ·  PRIORITAS 1'
        else:
            big = f'{HARI[d.weekday()]} {d.strftime("%d/%m/%Y")}'
            kick = 'PERKIRAAN  ·  RENCANA PRODUKSI  ·  BATAS MENTOK' + ('  ·  RESI MERAH' if d == TODAY else '')
        sku_page(pdf, kick, big, chip_for(d), fr, note='SKU yang tidak tampil = 0  ·  Σ = total set per warna')
    basis_page(pdf)
print('OK', OUT, 'halaman:', 4 + len(DAYS) + 1)
print('hari:', [(('LEWAT' if d == LEWAT else d.strftime('%d/%m')), int(sub(d).qty.sum()), est_of(sub(d))) for d in DAYS])
print('total', int(df.qty.sum()), 'pesanan', df['Order ID'].nunique(), 'perkiraan', est_of(df))
print('ukuran', size_totals(df), '| listing', df.groupby('listing').qty.sum().to_dict())