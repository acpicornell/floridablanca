"""Load the printed-glossary lookup tables.

Source: pp. 5637 (abbreviations) and 5638 (current municipalities) of
the INE 1986 facsimile of the Floridablanca census, Tomo VI.

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

# pp. 5638 — 65 municipalities active in 1986. Verbatim from the
# printed table; preserve original orthography (e.g. "SANTAÑY" with
# tilde, "BAÑALBUFAR" with eñe, "BINISALEM" without).
CURRENT_MUNICIPALITIES = [
    (1,  "ALARO"),
    (2,  "ALAYOR"),
    (3,  "ALCUDIA"),
    (4,  "ALGAIDA"),
    (5,  "ANDRAITX"),
    (6,  "ARTA"),
    (7,  "BAÑALBUFAR"),
    (8,  "BINISALEM"),
    (9,  "BUGER"),
    (10, "BUÑOLA"),
    (11, "CALVIA"),
    (12, "CAMPANET"),
    (13, "CAMPOS DEL PUERTO"),
    (14, "CAPDEPERA"),
    (15, "CIUDADELA"),
    (16, "CONSELL"),
    (17, "COSTITX"),
    (18, "DEYA"),
    (19, "ESCORCA"),
    (20, "ESPORLAS"),
    (21, "ESTELLENCHS"),
    (22, "FELANITX"),
    (23, "FERRERIAS"),
    (24, "FORMENTERA"),
    (25, "FORNALUTX"),
    (26, "IBIZA"),
    (27, "INCA"),
    (28, "LLORET DE VISTA ALEGRE"),
    (29, "LLOSETA"),
    (30, "LLUBI"),
    (31, "LLUCHMAYOR"),
    (32, "MAHON"),
    (33, "MANACOR"),
    (34, "MANCOR DEL VALLE"),
    (35, "MARIA DE LA SALUD"),
    (36, "MARRATXI"),
    (37, "MERCADAL"),
    (38, "MONTUIRI"),
    (39, "MURO"),
    (40, "PALMA DE MALLORCA"),
    (41, "PETRA"),
    (42, "POLLENSA"),
    (43, "PORRERAS"),
    (44, "PUEBLA, LA"),
    (45, "PUIGPUÑENT"),
    (46, "SAN ANTONIO ABAD"),
    (47, "SANCELLAS"),
    (48, "SAN JOSE"),
    (49, "SAN JUAN"),
    (50, "SAN JUAN BAUTISTA"),
    (51, "SAN LORENZO DEL CARDESSAR"),
    (52, "SAN LUIS"),
    (53, "SANTA EUGENIA"),
    (54, "SANTA EULALIA DEL RIO"),
    (55, "SANTA MARGARITA"),
    (56, "SANTA MARIA DEL CAMI"),
    (57, "SANTAÑY"),
    (58, "SELVA"),
    (59, "SES SALINES"),
    (60, "SINEU"),
    (61, "SOLLER"),
    (62, "SON SERVERA"),
    (63, "VALLDEMOSA"),
    (64, "VILLACARLOS"),
    (65, "VILLAFRANCA DE BONANY"),
]


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    for table, rows in (
        ("category_codes",     CATEGORIES),
        ("authority_codes",    AUTHORITIES),
        ("jurisdiction_codes", JURISDICTIONS),
        ("district_codes",     DISTRICTS),
    ):
        con.execute(f"DELETE FROM {table}")
        con.executemany(f"INSERT INTO {table} VALUES (?, ?)", rows)
        print(f"  {table}: {len(rows)} rows")
    con.execute("DELETE FROM current_municipalities")
    con.executemany(
        "INSERT INTO current_municipalities VALUES (?, ?)",
        CURRENT_MUNICIPALITIES,
    )
    print(f"  current_municipalities: {len(CURRENT_MUNICIPALITIES)} rows")
    con.close()


if __name__ == "__main__":
    main()
