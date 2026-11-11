# Floridablanca · Balearic volume

[![Deploy](https://github.com/acpicornell/floridablanca/actions/workflows/deploy.yml/badge.svg)](https://github.com/acpicornell/floridablanca/actions/workflows/deploy.yml)

A re-digitisation of the **Balearic volume (Tomo VI)** of the
[Floridablanca Census of 1787](https://en.wikipedia.org/wiki/Census_of_Floridablanca),
the first modern, uniform-criteria census of Spain, as published in facsimile
by the Instituto Nacional de Estadística (Madrid, 1986). This edition turns the
36-page facsimile into a relational database and a searchable website.

**Live site: <https://floridablanca.corpusbalear.org>** — part of
[Corpus Balear](https://corpusbalear.org), digital editions of Balearic
historical sources. Sister project of [`madoz`](../madoz).

## What's in it

- **111 pueblos** plus 3 supplemental Ibiza parishes, with the administrative
  metadata of Table 1 (categoría, autoridad, jurisdicción, intendencia, partido).
- All seven printed tabulations as long-form fact tables: housing (252 rows),
  sex × marital status × age (4 956 cells, 0 internal inconsistencies),
  occupations (1 560), 59 religious communities, 12 welfare centres, 14 other
  centres.
- District aggregates (aging index, marital fertility, sex ratio) within ~4 %
  of Vidal (1987).
- The narrative Comentario and the embedded 1787 NOTA.

## How it was made

The facsimile is a 1-bit scan with no text layer, and plain OCR was unusable on
its typewriter face. Each page was rendered at 300 DPI and converted to
structured JSON by Claude Opus 4.7 with a tailored per-page prompt, then loaded
into DuckDB and checked against the printed totals; the remaining single-cell
errors were patched by hand against the source. A flat JSON export feeds a
vanilla-JS static site in Catalan.

## Run locally

```bash
uv venv
uv pip install duckdb anthropic python-dotenv Pillow
python scripts/init_db.py && python scripts/load_lookups.py
python scripts/load_all.py && python scripts/export_web_data.py
python -m http.server -d web 8000
```

Re-extracting pages needs `ANTHROPIC_API_KEY` in `.env`; the extracted JSON is
versioned in `data/extracted/`, so building the database does not.

## Documentation

- [docs/METHOD.md](docs/METHOD.md) — goals, what didn't work and why (OCR,
  resolution, model choice), and the loaded row counts and cross-checks.
- [docs/PIPELINE.md](docs/PIPELINE.md) — repository layout, DuckDB schema, the
  three pipeline stages, day-to-day commands, deployment and language
  convention.
- [docs/SOURCES.md](docs/SOURCES.md) — the INE facsimile volumes and companion
  materials.

## Licence and citation

Code: **AGPL-3.0-or-later** (see `LICENSE`). Underlying data: the 1787
Floridablanca census is public domain; the 1986 INE facsimile typesetting is
the editorial work referenced as source.

The site cites itself as: Picornell Company, A. C. *Cens de Floridablanca*
(1787), edició digital. Corpus Balear · floridablanca.corpusbalear.org
