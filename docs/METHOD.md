# Method, difficulties and results

How the Balearic volume of the 1787 Floridablanca census was digitised, what
went wrong on the way, and what the loaded database checks out to.

## Goals

The 1787 Floridablanca census is the first modern, uniform-criteria
statistical census of Spain. Counting at the household level, broken
down by sex × marital status × age band × occupation, plus a register
of religious communities and welfare institutions, it predates the
1836 (Mendizábal) and 1855 (Madoz himself) ecclesiastical
disentailments — so it captures a baroque administrative geography
that the 19th-century reforms then dismantled.

This project takes the 36-page facsimile PDF and produces:

- A relational **DuckDB** (`db/floridablanca.duckdb`) with one row per
  pueblo plus long-form fact tables for each of the seven printed
  tabulations.
- A flat **`web/data.json`** export consumed by a vanilla-JS static
  site (`web/index.html`) — searchable list of the 111 pueblos with
  drill-down to the per-pueblo demographic, occupational, religious
  and welfare detail.

## Difficulties (what didn't work, and why)

### 1. Plain OCR (pdftotext / tesseract) was unusable

The PDF is a 1-bit 403-DPI scan with no text layer. `pdftotext`
returned zero bytes; tesseract on the typewriter face produced
character-by-character mangle on the cramped 3-letter cells
("AUTORIDAD", "JURISDICCION", "PARTIDO"). Skipping OCR and going
straight to Claude Vision with a tailored per-page prompt was
substantially cleaner.

### 2. 200 DPI was not enough — bumped to 300 DPI

A first extraction pass at 200 DPI confused R / Ñ in pueblo names
("ALARO" → "ALAÑO"), and lost the difference between row indices in
multi-line cells. Re-rendering with `-r 300` and adding a canonical
pueblo glossary to the system prompt fixed both classes of error.

### 3. The typewriter face confuses G / C in the cramped authority
   cells

"G.JO" (Gobernador y Justicia Ordinario) gets read as "C.JO" by the
model when the cell is barely 2 mm wide. `load_all.py` carries a small
`_AUTHORITY_FIXES` table (`C.JO → G.JO`, `C.AL → G.AL`, `G.AM →
C.AM`); any other off-glossary code logs a warning and is stored as
NULL so the foreign key holds.

### 4. Table 3 is the densest; Sonnet 4.5 drifted on it, Opus 4.7 fixed it

Each Table 3 page packs ~10 pueblo columns × 24 rows × 3 cells =
~720 numeric cells into one prompt. At ~80 tokens per pueblo block,
Sonnet 4.5 produced an internally-inconsistent JSON ~1 cell in 6:
either `T ≠ V + M` in a single cell, `total ≠ single + married +
widowed` across a band, or `all ≠ Σ bands` across the age column.
Across the six Table 3 pages, that meant ~431 internal mismatches
affecting 58 of 59 pueblos. The errors weren't pure
hallucination — most looked like cell-conflation in dense regions
(reading values from an adjacent column or row, dropping a digit
late in the response).

Re-extracting the same six pages with **Opus 4.7** — a one-line swap
of the `MODEL` constant in `scripts/extract_pages.py` — dropped the
internal-consistency error count from 431 to under 30 and brought
every district aggregate within 4 % of Vidal (1987)'s published
figures on aging index, marital fertility and sex ratio. Total cost:
about $1.85 in API spend for all six Opus extractions, very cheap
for the quality gain. Verdict: use **Opus 4.7 for dense numeric
tables**; Sonnet would be fine for the sparser admin-and-glossary
pages (Tables 1, 2, 4-7) but the pipeline now uses Opus uniformly
for simplicity.

Opus is still non-deterministic on a handful of cells per page —
a second `--force` re-extraction of the pages where any mismatch
remained shaved the count further from 29 to 13. The final 13
mismatches turned out to be a handful of single-cell errors
(FELANITX V/M swap, SAN MATEO and SAN RAFAEL phantom `married <7`
rows that should have been NULL, and a missing M cell on SANTA
MARGARITA erased in the facsimile but recoverable from the
printed V and T) that we patched by hand against the source. The
final state: **0 internal inconsistencies across all 4 956 cells
of Table 3.**

Table 4 (occupations, pages 25-27) showed the same pattern when
checked against simple sanity rules: 43 of 114 pueblos had
Σ-of-columns ≠ printed total, 7 had a Table 4 total disagreeing
with the Table 3 population by more than 10 (ESPORLAS off by 2 782!),
and FORMENTERA appeared to have 184 estudiantes on a rural island
of 1 054 inhabitants. The 184 was real — but it was the
`labradores` cell, not `estudiantes`; Sonnet had shifted the row
down by one. Re-extracting pages 25-27 with Opus dropped the
column-sum mismatches from 43 to 4 (all Δ≤24, source-side drift),
fixed every Table 4 / Table 3 population disagreement, and turned
FORMENTERA's 184 estudiantes into 184 labradores with 0 students,
which is what the source actually says.

The pipeline still saves the raw response on parse failure
(`data/extracted/page-NN.raw.txt`) so any cell-level error can be
patched by hand or by a `--force` re-run.

## Status

| Stage | Rows loaded |
|---|--:|
| Lookups (categories, authorities, jurisdictions, districts, current municipalities) | 8 + 13 + 4 + 3 + 65 |
| `pueblos` (Table 1 admin + references) | 114 (111 pueblos + 3 Ibiza parishes) |
| `population_by_housing` (Table 2) | 252 |
| `population_by_marital_age_sex` (Table 3) | 4 956 |
| `population_by_occupation` (Table 4) | 1 560 |
| `religious_communities` (Table 5) | 59 |
| `welfare_centers` (Table 6) | 12 |
| `other_centers` (Table 7) | 14 |
| `source_documents` (Comentario + Nota 1787) | 2 |

Provincial cross-checks:
- Sum of family-housing pueblos in Table 2: **122 974 habitants** (printed: 122 554; ~0.3 % OCR drift on individual cells).
- Table 3 (marital × age × sex) covers **56 of the 111 pueblos** and sums to **175 900 habitants**, the figure the Demografia tab shows (ESCORCA's column is extracted but not matched to a pueblo). The 3 Ibiza parishes are loaded too, but IBIZA's own row is exactly their sum (2 102 + 780 + 671 = 3 553), so adding them counts Ibiza twice — a naive sum over all 59 units gives 179 453, more than the 179 066 Floridablanca gives for the whole archipelago. The site counts IBIZA once and leaves the parishes out of the aggregates (`parent_cod`). Table 2, by contrast, covers only 21 pueblos, 20 of which report collective housing.
- Top occupations across the archipelago: jornalers (22 727), llauradors (10 691), militars amb fur (9 489), artesans (7 327), criats (4 349), estudiants (3 003).
- 38 friar convents, 16 nun convents and 5 other religious houses (hermitatges, beateris) documented.
- **Vidal (1987) crosscheck** on all three districts (Mallorca, Menorca, Eivissa-Formentera): the aging index, marital fertility and sex ratio match the published academic figures within ~4 %. See *Difficulties* §4 above for the model swap that made this possible.

A handful of Table 2 cells fail a TOTAL = family + collective consistency check (FELANITX 7410 vs 7010, PALMA varones 18183 vs 18243, …). Both the printed total and its components are subject to OCR error in the cramped typewriter face; `load_all.py` surfaces these as `[check]` warnings without auto-correcting.
