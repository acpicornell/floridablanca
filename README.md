# Floridablanca · Balearic volume

A re-digitisation of the **Balearic volume (Tomo VI)** of the
[Floridablanca Census of 1787](https://en.wikipedia.org/wiki/Census_of_Floridablanca),
as published in facsimile by the Instituto Nacional de Estadística
(Madrid, 1986).

Sister project of [`madoz`](../madoz). Same conventions: code, scripts
and English-language docs in English; the published website is in
Catalan as a deliberate cultural choice for the artefact.

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

## What lives where

```
data/
  pdfs/                # source facsimile (1 PDF, 36 pp.)
  pages/               # one JPG per PDF page at 300 DPI (gitignored)
  extracted/           # per-page LLM extraction artefacts (JSON), versioned
db/
  schema.sql           # DuckDB schema (versioned)
  floridablanca.duckdb # built DB (gitignored, regenerable)
scripts/               # init, load, export pipeline
web/
  index.html           # static SPA (Catalan UI)
  app.js
  style.css
  data.json            # flat export consumed by the site
```

## Schema

Lookups: `category_codes`, `authority_codes`, `jurisdiction_codes`,
`district_codes`, `current_municipalities` (decode the printed
glossary at pp. 5637-5638).

Core entity: `pueblos` (one row per 1787 pueblo, 111 numbered rows
plus 3 supplemental Ibiza parishes). Carries the administrative
metadata from **Table 1a** (categoría, autoridad, jurisdicción,
intendencia, partido, municipio actual) and the bibliographic
references from **Table 1b** (página manuscrito 1787, fotograma INE,
presence-flags for tables 2-7, observaciones).

Long-form facts (one fact per row):
- `population_by_housing`        (Table 2 — pueblo × housing type × sex)
- `population_by_marital_age_sex` (Table 3 — pueblo × marital status × age × sex)
- `population_by_occupation`      (Table 4 — pueblo × occupation)
- `religious_communities`         (Table 5 — one row per convent / casa)
- `welfare_centers`               (Table 6 — one row per hospital / hospicio)
- `other_centers`                 (Table 7 — colegios, seminarios…)

Plus `source_documents` for the narrative Comentario and the embedded
1787 NOTA.

## Pipeline

Three stages — all idempotent.

### 1. PDF → page images

```bash
pdftoppm -jpeg -r 300 data/pdfs/floridablanca_tomo6_baleares.pdf data/pages/page
```

The source PDF has no text layer (it's a 403-DPI scan), so every
extraction step is image-based.

### 2. Per-page LLM extraction

`scripts/extract_pages.py` walks the 36 pages and asks Claude Sonnet
4.6 to convert each table image into structured JSON. Each page has a
tailored prompt (`PAGES` map at the top of the script) that names the
table, lists the column / row schema, and lists the canonical pueblo /
municipality glossary so the model can self-correct OCR ambiguities
(R/Ñ, C/G, V/Y) at the source.

```bash
python scripts/extract_pages.py            # all configured pages
python scripts/extract_pages.py --force 12 # re-extract a single page
```

Each successful call writes `data/extracted/page-NN.json`; failed
calls write `page-NN.raw.txt` for forensic inspection. Output is
versioned (small, ~5-30 KB per page) so re-runs are free.

### 3. Load into DuckDB

```bash
python scripts/init_db.py        # creates schema (idempotent)
python scripts/load_lookups.py   # loads the printed glossary
python scripts/load_all.py       # flattens data/extracted/*.json
python scripts/export_web_data.py
```

`load_all.py` is tolerant of partial extraction: missing per-page
JSONs simply skip that table block, so the DB and the web export stay
consistent at every stage of the pipeline.

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

### 4. Table 3 is the densest; the JSON output occasionally clips

Each Table 3 page packs ~10 pueblo columns × 24 rows × 3 cells =
~720 numeric cells into one prompt. At ~80 tokens per pueblo block,
the model occasionally produces a malformed array late in the
response. The pipeline saves the raw response on parse failure
(`data/extracted/page-NN.raw.txt`) so the cell-level error can be
patched by hand or by a follow-up prompt. Re-running the same page
under `--force` usually succeeds — the failure is non-deterministic.

## Status

| Stage | Rows loaded |
|---|--:|
| Lookups (categories, authorities, jurisdictions, districts, current municipalities) | 8 + 13 + 4 + 3 + 65 |
| `pueblos` (Table 1 admin + references) | 114 (111 pueblos + 3 Ibiza parishes) |
| `population_by_housing` (Table 2) | 252 |
| `population_by_marital_age_sex` (Table 3) | 4 953 |
| `population_by_occupation` (Table 4) | 1 560 |
| `religious_communities` (Table 5) | 59 |
| `welfare_centers` (Table 6) | 12 |
| `other_centers` (Table 7) | 14 |
| `source_documents` (Comentario + Nota 1787) | 2 |

Provincial cross-checks:
- Sum of family-housing pueblos in Table 2: **122 974 habitants** (printed: 122 554; ~0.3 % OCR drift on individual cells).
- Sum of family-housing pueblos in Table 3 (marital × age × sex): **181 650 habitants** — includes all 111 pueblos, not just the 21 with collective housing.
- Top occupations across the archipelago: jornalers (22 727), llauradors (10 691), militars amb fur (9 489), artesans (7 327), criats (4 349), estudiants (3 003).
- 38 friar convents, 16 nun convents and 5 other religious houses (hermitatges, beateris) documented.

A handful of Table 2 cells fail a TOTAL = family + collective consistency check (FELANITX 7410 vs 7010, PALMA varones 18183 vs 18243, …). Both the printed total and its components are subject to OCR error in the cramped typewriter face; `load_all.py` surfaces these as `[check]` warnings without auto-correcting.

## Setup

```bash
uv venv
uv pip install duckdb anthropic python-dotenv Pillow
cp .env.example .env  # then add ANTHROPIC_API_KEY
```

## Day-to-day

```bash
# After tweaking a prompt, re-extract one page
python scripts/extract_pages.py --force 19

# Refresh the DB
python scripts/load_all.py

# Refresh the web data
python scripts/export_web_data.py

# Serve the site locally
python -m http.server -d web 8000
```

## Language convention

Code, scripts, schema and this README are in English so the project
stays navigable. The website is in Catalan, as a cultural choice for
the published artefact (the Balearic Islands' co-official language).

## License

Code: **AGPL-3.0-or-later** (see `LICENSE`). Underlying data: the 1787
Floridablanca census is public domain; the 1986 INE facsimile
typesetting is the editorial work referenced as source.
