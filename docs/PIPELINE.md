# Pipeline, schema and deployment

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
`district_codes` (decode the printed glossary at p. 5637).

Core entity: `pueblos` (one row per 1787 pueblo, 111 numbered rows
plus 3 supplemental Ibiza parishes). Carries the administrative
metadata from **Table 1a** (categoría, autoridad, jurisdicción,
intendencia, partido) and the bibliographic references from
**Table 1b** (página manuscrito 1787, fotograma INE, presence-flags
for tables 2-7, observaciones).

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

`scripts/extract_pages.py` walks the 36 pages and asks **Claude Opus
4.7** to convert each table image into structured JSON. Each page has
a tailored prompt (`PAGES` map at the top of the script) that names
the table, lists the column / row schema, and lists the canonical
pueblo / municipality glossary so the model can self-correct OCR
ambiguities (R/Ñ, C/G, V/Y) at the source. See [§4 of *Difficulties*](METHOD.md#4-table-3-is-the-densest-sonnet-45-drifted-on-it-opus-47-fixed-it)
in METHOD.md for why the model choice matters — Sonnet 4.5 is a third the
cost but produced too much drift on the densest Table 3 pages.

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

## Deployment

The web layer is a fully static SPA (vanilla JS, no framework, no
backend), served as a static-assets-only **Cloudflare Worker**
(`wrangler.jsonc`, assets directory `web`).

`.github/workflows/deploy.yml` deploys on every push to `main`: it runs
`scripts/check_site.py web` against the site's own security policy and
then deploys with wrangler. It needs a `CLOUDFLARE_API_TOKEN` repository
secret and skips the deploy (green) while that is missing.

`web/_headers` sets `Cache-Control: no-store` on every HTML, JSON, JS
and CSS file, so a reload always fetches the live deploy, plus a strict
Content-Security-Policy (no external resources).

Re-running the pipeline locally and pushing is enough:

```bash
python scripts/load_all.py
python scripts/export_web_data.py
git add web/data.json && git commit -m 'data refresh' && git push
```

## Language convention

Code, scripts, schema and the documentation (README and `docs/`) are in English so the project
stays navigable. The website is in Catalan, as a cultural choice for
the published artefact (the Balearic Islands' co-official language).
