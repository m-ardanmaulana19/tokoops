# Configuring TokoOps for Your Shop

TokoOps ships with a worked example catalogue. Your shop adapts it in
four places: the SKU catalogue, the per-SKU shipping-time settings, the
listing / family overrides and aliases, and the report colours. This
document explains the model, gives the full example, and says exactly
where each setting lives.

## 1. SKU catalogue model

SKUs are codes of the form:

```text
COLOUR-SIZE
```

For example `YEL-JMB` is colour `YEL`, size `JMB`.

There are two families:

- **Main family** — the plain `COLOUR-SIZE` codes.
- **Shanghai family** — the same colours and sizes with an `S` prefix on
  the colour code: `SYEL-STD`, `SHTM-JMB`, and so on. The Shanghai family
  is a separate listing family with its own deadline rule (see section 4).

Sizes used in the example:

| Size code | Meaning |
| --- | --- |
| STD | L |
| JMB | XXL |
| SPJ | 5L |

Colours used in the example:

| Colour code | Colour name |
| --- | --- |
| YEL | Kuning |
| HTM | Hitam |
| SG | Sage |
| JTL | Hijau Botol |

## 2. Example catalogue (18 SKUs)

Main family: YEL, HTM, SG, and JTL, each in STD, JMB, and SPJ = 12 SKUs.
Shanghai family: SYEL and SHTM, each in STD, JMB, and SPJ = 6 SKUs.

| SKU | Family | Shipping-time setting |
| --- | --- | --- |
| YEL-STD | main | 12 hari |
| YEL-JMB | main | Reguler |
| YEL-SPJ | main | 12 hari |
| HTM-STD | main | Reguler |
| HTM-JMB | main | 12 hari |
| HTM-SPJ | main | 7 hari |
| SG-STD | main | 12 hari |
| SG-JMB | main | 12 hari |
| SG-SPJ | main | 12 hari |
| JTL-STD | main | 14 hari |
| JTL-JMB | main | 14 hari |
| JTL-SPJ | main | 14 hari |
| SYEL-STD | shanghai | listing override (+16) |
| SYEL-JMB | shanghai | listing override (+16) |
| SYEL-SPJ | shanghai | listing override (+16) |
| SHTM-STD | shanghai | listing override (+16) |
| SHTM-JMB | shanghai | listing override (+16) |
| SHTM-SPJ | shanghai | listing override (+16) |

In words: YEL-JMB and HTM-STD are Reguler; HTM-SPJ is 7 hari; all JTL
SKUs are 14 hari; the Shanghai family uses the listing-level +16 rule;
everything else is 12 hari.

Replace these codes, colours, and settings with your own shop's. Keep
the `COLOUR-SIZE` shape so the reports, the colour matrix, and the alias
handling keep working.

## 3. Per-SKU shipping-time settings

The deadline model is called "Kirim pesanan sebelum" (ship order before).
Each SKU has a shipping-time setting, and the setting decides how many
days are added:

| Setting | Lead (days added) | Deadline |
| --- | --- | --- |
| Reguler | +1 | created + 1 day |
| 7 hari | +9 | created + 9 days |
| 12 hari | +14 | created + 14 days |
| 14 hari | +16 | created + 16 days |
| Listing / family override | +16 | created + 16 days |

Note that the lead is not the same number as the setting name: a 7 hari
setting means +9 days in this calibrated model, 12 hari means +14, and
14 hari means +16.

### Clock-start rule

The clock does not always start at the same timestamp:

- **Non-COD orders:** the clock starts at **Paid Time**.
- **COD orders:** the clock starts at **Created Time**.

"Created" in the table above means that clock-start timestamp for the
order in question.

## 4. Listing / family overrides (+16)

Some listings and families override the per-SKU setting and always use
+16 days. The Shanghai family is the example in this catalogue: every
`SYEL-*` and `SHTM-*` SKU uses +16, whatever its per-SKU setting says.

In the production generators this is expressed with two constants at the
top of the `laporan_*.py` files:

| Constant | Role |
| --- | --- |
| `LISTING_BARU_PREFIXES` | Listing / family prefixes that take the +16-day lead |
| `LISTING_KEYWORD_LEAD16` | Listing-name keyword that takes the +16-day lead; the Shanghai rule matches correctly spelled "Shanghai" listing names |

The rule keys off the SKU family and the listing name. If your shop adds
another family with a fixed long lead, add its prefix to
`LISTING_BARU_PREFIXES` (and its keyword, if it is listing-name based)
rather than adding a special case inside the deadline code.

## 5. Deadline modes: Model / Flag / Hybrid

The deadline engine has three modes. They differ in how much they trust
the model in section 3 versus the value TikTok recorded on the order
itself.

TikTok freezes each order's `Normal or Pre-order` value at creation
time. Later changes to a SKU's shipping-time setting do not change the
flag on orders that already exist.

| Mode | Rule |
| --- | --- |
| Model | Always use the per-SKU model in sections 3-4. |
| Flag | Use the frozen per-order flag: `Normal` -> due on the creation date; `Pre-order` -> use the model. |
| Hybrid | Pick per order: use the flag where it decides the deadline, and the model where it does not. |

Confidence labels in the reports follow from this:

- **PASTI** — the deadline comes from the frozen flag on the order.
- **PERKIRAAN** — the deadline is estimated from the model.

That is why the production report is titled PERKIRAAN: in Model mode,
and for Pre-order orders in the other modes, its deadlines are model
estimates, not values recorded on the order.

## 6. Alias table

Seller Center exports do not always spell a SKU the same way over time.
The alias table maps spellings found in exports onto the canonical
catalogue code, so the same product is not counted twice.

Example from the shipped catalogue:

| Export spelling | Canonical SKU |
| --- | --- |
| `SHG-YEL-STD` | `SYEL-STD` |
| `SHG-YEL-JMB` | `SYEL-JMB` |
| `SHG-YEL-SPJ` | `SYEL-SPJ` |
| `SHG-HTM-STD` | `SHTM-STD` |
| `SHG-HTM-JMB` | `SHTM-JMB` |
| `SHG-HTM-SPJ` | `SHTM-SPJ` |

In general: old `SHG-XXX-YYY` codes normalize to `SXXX-YYY`.

Aliases are exact, listed mappings. An SKU that appears in an export and
is neither in the catalogue nor in the alias table is **not** guessed
at: it goes to the new-SKU inbox in the app's catalogue tab, where a
person confirms it once. It is never silently merged into an existing
SKU.

## 7. Report colour palette

Reports colour rows, bars, and the SKU x deadline matrix by colour code:

| Colour code | Colour name | Hex |
| --- | --- | --- |
| YEL | Kuning | `#DBA514` |
| HTM | Hitam | `#1F1F1F` |
| SG | Sage | `#9CAF88` |
| JTL | Hijau Botol | `#3E7C43` |
| SYEL | Kuning (Shanghai) | `#DBA514` |
| SHTM | Hitam (Shanghai) | `#1F1F1F` |

Shanghai colours reuse their base colour hex: SYEL reuses the YEL hex
and SHTM reuses the HTM hex.

If you add a colour, give it a hex here and in the settings below, so the
thermal report, the production bars, and the matrix stay consistent.

## 8. Where each setting lives

### In the Python generators (`generators/`)

Constants at the top of each generator file:

| Setting | Location |
| --- | --- |
| Per-SKU shipping-time settings | `SETTING` at the top of the `laporan_*.py` files |
| Report colours (production) | `COL` at the top of the `laporan_*.py` files |
| Listing / family +16 prefixes | `LISTING_BARU_PREFIXES` in the `laporan_*.py` files |
| Listing keyword for +16 | `LISTING_KEYWORD_LEAD16` in the `laporan_*.py` files |
| Report colours (resi) | `COLOR` in `resi_merah3.py` |

Files: `laporan_final5.py`, `laporan_baru.py`, `laporan_shanghai.py`,
and `resi_merah3.py`. Keep the three production generators in step: a
setting changed in one usually belongs in the other two as well.

### In the web app (`app/tokoops.html`)

- The **Katalog tab** holds the catalogue for the active shop profile.
- The seed catalogue is in `app/tokoops.html` itself; it is the starting
  point copied into a new profile.
- Per-SKU shipping settings and aliases are editable in-app, per shop
  profile. Each profile keeps its own catalogue, settings, and data.

Rule of thumb: the app is where a shop maintains its day-to-day
catalogue; the generator constants are where the printed Python PDFs get
the same settings. When you change a deadline setting, change it in both
places so the dashboard and the printed report agree.
