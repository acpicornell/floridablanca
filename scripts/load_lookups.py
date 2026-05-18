"""Load the printed-glossary lookup tables.

Source: p. 5637 (abbreviations) of the INE 1986 facsimile of the
Floridablanca census, Tomo VI.

Re-running is safe: the script truncates each lookup table before
re-inserting so the printed glossary is the single source of truth.

Usage:
    python scripts/load_lookups.py
"""

from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "floridablanca.duckdb"


CATEGORIES = [
    ("A",  "Aldea"),
    ("Ar", "Arrabal"),
    ("C",  "Ciudad"),
    ("CR", "Coto Redondo"),
    ("D",  "Despoblado"),
    ("L",  "Lugar"),
    ("Pq", "Parroquia"),
    ("V",  "Villa"),
]

AUTHORITIES = [
    ("A",    "Alcalde"),
    ("AMR",  "Alcalde Mayor de Realengo"),
    ("AO",   "Alcalde Ordinario"),
    ("AOR",  "Alcalde Ordinario de Realengo"),
    ("AOS",  "Alcalde Ordinario de Señorío"),
    ("AP",   "Alcalde Pedáneo"),
    ("APR",  "Alcalde Pedáneo de Realengo"),
    ("APS",  "Alcalde Pedáneo de Señorío"),
    ("C.AM", "Corregidor y Alcalde Mayor"),
    ("G.AL", "Gobernador y Alguacil"),
    ("G.JO", "Gobernador y Justicia Ordinario"),
    ("JO",   "Justicia Ordinario"),
    ("S/A",  "Sin Alcalde"),
]

JURISDICTIONS = [
    ("R",  "Realengo"),
    ("S",  "Señorío"),
    ("SE", "Señorío Eclesiástico"),
    ("SS", "Señorío Secular"),
]

DISTRICTS = [
    ("IBI", "Ibiza"),
    ("MAL", "Mallorca"),
    ("MEN", "Menorca"),
]

def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    # UPSERT so this script is safe to re-run after pueblos rows
    # (which reference the lookups via FK) are already loaded.
    for table, rows in (
        ("category_codes",     CATEGORIES),
        ("authority_codes",    AUTHORITIES),
        ("jurisdiction_codes", JURISDICTIONS),
        ("district_codes",     DISTRICTS),
    ):
        con.executemany(
            f"INSERT INTO {table} (code, label) VALUES (?, ?) "
            f"ON CONFLICT (code) DO UPDATE SET label = excluded.label",
            rows,
        )
        print(f"  {table}: {len(rows)} rows")
    con.close()


if __name__ == "__main__":
    main()
