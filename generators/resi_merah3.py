import sys
import pandas as pd
from collections import OrderedDict
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth

CSV, TGL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

# EXAMPLE CATALOGUE — replace with your own SKUs (docs/CONFIGURATION.md).
COLOR = OrderedDict([('YEL', 'Kuning'), ('HTM', 'Hitam'), ('SG', 'Sage'), ('JTL', 'Hijau Botol')])
SIZE = {'STD': 'L', 'JMB': 'XXL', 'SPJ': '5L'}
CORDER = {k: i for i, k in enumerate(COLOR)}

df = pd.read_csv(CSV, encoding='utf-8-sig', dtype=str, keep_default_na=False)
for c in df.columns: df[c] = df[c].astype(str).str.strip()
df['qty'] = df['Quantity'].astype(int)

def sku_key(r):
    if r['Seller SKU']: return r['Seller SKU']
    return f"{r['Product Name'].split()[0].upper()} {r['Variation'].replace(', ', ' ').replace('LD ', 'LD')}"
df['key'] = df.apply(sku_key, axis=1)

def human(key):
    if '-' in key and key.split('-')[0] in COLOR:
        c, s = key.split('-'); return f"{COLOR[c]} {SIZE[s]}"
    return key

def sortkey(key):
    if '-' in key and key.split('-')[0] in COLOR:
        c, s = key.split('-'); return (0, CORDER[c], list(SIZE).index(s))
    return (1, 99, 0)

tab = df.groupby('key').qty.sum()
coded = set(df['Seller SKU'])
rows = sorted(tab.items(), key=lambda kv: (0, kv[0]) if kv[0] in coded else (1, kv[0]))
N_ORD, N_PCS, N_SKU = df['Order ID'].nunique(), int(df.qty.sum()), len(rows)
assert sum(q for _, q in rows) == N_PCS

combos = {}
for oid, g in df.groupby('Order ID'):
    if g.qty.sum() > 1:
        it = g.groupby('key').qty.sum()
        txt = ' + '.join(f"{int(q)} {human(k)}" for k, q in sorted(it.items(), key=lambda kv: sortkey(kv[0])))
        combos[txt] = combos.get(txt, 0) + 1
MULTI = sorted(combos.items())

single = {}
for oid, g in df.groupby('Order ID'):
    if g.qty.sum() == 1:
        k = g['key'].iloc[0]; single[k] = single.get(k, 0) + 1
N_SINGLE = sum(single.values())
single_rows = sorted(single.items(), key=lambda kv: (0, kv[0]) if kv[0] in coded else (1, kv[0]))
assert N_SINGLE + sum(n for _, n in MULTI) == N_ORD

multi_tab = {}
for oid, g in df.groupby('Order ID'):
    if g.qty.sum() > 1:
        for k, q in g.groupby('key').qty.sum().items(): multi_tab[k] = multi_tab.get(k, 0) + int(q)
N_MULTI_PCS = sum(multi_tab.values())
multi_rows = sorted(multi_tab.items(), key=lambda kv: (0, kv[0]) if kv[0] in coded else (1, kv[0]))
assert sum(q for _, q in single_rows) == N_SINGLE

W, H = 80 * mm, 150 * mm
B, R = 'Helvetica-Bold', 'Helvetica'
M = 4 * mm
L, Rr = M, W - M
CW = Rr - L
BOT = 4 * mm
c = canvas.Canvas(OUT, pagesize=(W, H))
c.setTitle(f'RESI MERAH {TGL} - Rekap Pesanan')
state = {'y': H - M, 'page': 1}

def blackbar(h, txt, size, ytop=None):
    y0 = state['y'] if ytop is None else ytop
    c.setFillColorRGB(0, 0, 0); c.rect(L, y0 - h, CW, h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont(B, size)
    c.drawCentredString(W / 2, y0 - h / 2 - size * 0.35, txt)
    c.setFillColorRGB(0, 0, 0)

def new_page():
    c.showPage(); state['page'] += 1; state['y'] = H - M
    c.setFont(B, 8); c.drawCentredString(W / 2, state['y'] - 3 * mm, f'RESI MERAH {TGL} (lanjutan)')
    state['y'] -= 6 * mm

def need(h):
    if state['y'] - h < BOT: new_page(); return True
    return False

y = state['y']
c.setFont(R, 7); c.drawCentredString(W / 2, y - 3 * mm, 'TOKOOPS  •  REKAP PESANAN'); y -= 5 * mm
blackbar(11 * mm, 'RESI MERAH', 22, y); y -= 11 * mm
c.setFont(B, 10); c.drawCentredString(W / 2, y - 6 * mm, f'HARI INI  {TGL}'); y -= 8.5 * mm
bh = 13 * mm
c.setLineWidth(0.8); c.rect(L, y - bh, CW, bh)
for i in (1, 2): c.line(L + CW * i / 3, y, L + CW * i / 3, y - bh)
for i, (v, lab) in enumerate([(N_ORD, 'PESANAN'), (N_PCS, 'BARANG (PCS)'), (N_SKU, 'JUMLAH SKU')]):
    cx = L + CW * (i + .5) / 3
    c.setFont(B, 17); c.drawCentredString(cx, y - 8 * mm, str(v))
    c.setFont(R, 6); c.drawCentredString(cx, y - 11.5 * mm, lab)
y -= bh + 3 * mm
state['y'] = y

c1, c2 = L + 9 * mm, L + 52 * mm
HH, RH, TH = 5.5 * mm, 6.4 * mm, 7.5 * mm

def table_header():
    y = state['y']
    c.setFillColorRGB(0, 0, 0); c.rect(L, y - HH, CW, HH, fill=1, stroke=0); c.setFillColorRGB(1, 1, 1)
    c.setFont(B, 7)
    c.drawCentredString((L + c1) / 2, y - 3.9 * mm, 'NO.'); c.drawString(c1 + 2 * mm, y - 3.9 * mm, 'SKU')
    c.drawCentredString((c2 + Rr) / 2, y - 3.9 * mm, 'JUMLAH'); c.setFillColorRGB(0, 0, 0)
    state['y'] = y - HH

def row_borders(y, h, w=0.4):
    c.setLineWidth(w); c.line(L, y - h, Rr, y - h); c.line(L, y, L, y - h); c.line(Rr, y, Rr, y - h)
    c.line(c1, y, c1, y - h); c.line(c2, y, c2, y - h)

def draw_table(rows_list, total, unit):
    table_header()
    for i, (key, q) in enumerate(rows_list, 1):
        if need(RH + TH + 2 * mm): table_header()
        y = state['y']; row_borders(y, RH)
        c.setFont(R, 9); c.drawCentredString((L + c1) / 2, y - RH + 2.1 * mm, str(i))
        fs = 12
        while stringWidth(key, B, fs) > (c2 - c1 - 4 * mm) and fs > 6: fs -= 0.5
        c.setFont(B, fs); c.drawString(c1 + 2 * mm, y - RH + 2.0 * mm, key)
        c.setFont(B, 12); c.drawRightString(Rr - 9 * mm, y - RH + 2.0 * mm, str(int(q)))
        c.setFont(R, 7); c.drawString(Rr - 8 * mm, y - RH + 2.2 * mm, unit)
        state['y'] = y - RH
    y = state['y']; row_borders(y, TH, 0.8)
    c.setLineWidth(0.8); c.line(L, y, Rr, y)
    c.line(c1, y, c1, y - TH); c.line(c2, y, c2, y - TH)
    c.setFont(B, 10); c.drawString(c1 + 2 * mm, y - 5.3 * mm, 'TOTAL')
    c.setFont(B, 13); c.drawRightString(Rr - 9 * mm, y - 5.4 * mm, str(total))
    c.setFont(B, 7); c.drawString(Rr - 8 * mm, y - 5.2 * mm, unit.upper())
    state['y'] = y - TH - 3 * mm

draw_table(rows, N_PCS, 'pcs')
if single_rows:
    need(5.5 * mm + HH + RH + 2 * mm)
    blackbar(5.5 * mm, f'RESI 1 BARANG  ({N_SINGLE} resi)', 8)
    state['y'] -= 5.5 * mm + 1.5 * mm
    draw_table(single_rows, N_SINGLE, 'resi')

if multi_rows:
    need(5.5 * mm + HH + RH + 2 * mm)
    blackbar(5.5 * mm, f'ISI RESI > 1 BARANG  ({N_MULTI_PCS} pcs)', 8)
    state['y'] -= 5.5 * mm + 1.5 * mm
    draw_table(multi_rows, N_MULTI_PCS, 'pcs')

LS = 4.0 * mm
if MULTI:
    need(5.5 * mm + 12 * mm)
    total_resi = sum(n for _, n in MULTI)
    blackbar(5.5 * mm, f'RESI > 1 BARANG  ({total_resi} resi)', 8)
    state['y'] -= 5.5 * mm + 1.5 * mm
    fs, indent = 9, 3.2 * mm
    for txt, n in MULTI:
        label = txt + (f'   ({n} resi)' if n > 1 else '')
        lines = simpleSplit(label, B, fs, CW - indent)
        need(len(lines) * LS + 2 * mm)
        y = state['y']
        c.setFont(B, fs); c.drawString(L, y - 3.2 * mm, '•')
        for j, ln in enumerate(lines):
            c.drawString(L + indent, y - 3.2 * mm - j * LS, ln)
        state['y'] = y - len(lines) * LS - 1.6 * mm
        c.setLineWidth(0.25); c.setDash(1, 1.5); c.line(L, state['y'] + 0.6 * mm, Rr, state['y'] + 0.6 * mm); c.setDash()
else:
    c.setFont(R, 8); c.drawCentredString(W / 2, state['y'] - 3 * mm, 'Tidak ada resi dengan lebih dari 1 barang')
c.showPage(); c.save()
print('pages', state['page'], '| pesanan', N_ORD, 'pcs', N_PCS, 'sku', N_SKU)
for i, (k, q) in enumerate(rows, 1): print(f'{i}. {k} = {int(q)} pcs')
print('MULTI', len(MULTI), 'kombinasi,', sum(n for _, n in MULTI), 'resi')
for t, n in MULTI: print('-', t + (f' ({n} resi)' if n > 1 else ''))
print('MULTITAB', N_MULTI_PCS, 'pcs')
for i, (k, q) in enumerate(multi_rows, 1): print(f'M{i}. {k} = {q} pcs')
print('SINGLE', N_SINGLE, 'resi')
for i, (k, q) in enumerate(single_rows, 1): print(f'S{i}. {k} = {q} resi')