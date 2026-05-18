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

# pp. 5638 — 65 municipalities active in 1986. The first column is
# the INE 1986 administrative (Castilian) form, preserved verbatim
# from the printed table. The third column is the current official
# Catalan form, as fixed by Decret 36/1988 / 2/2004 and verified
# against the Viquipèdia article "Llista de municipis de les Illes
# Balears". Definite articles use the lowercase Balearic salat form
# ("es Mercadal", "ses Salines", "sa Pobla") per the official decree.
CURRENT_MUNICIPALITIES = [
    (1,  "ALARO",                    "Alaró"),
    (2,  "ALAYOR",                   "Alaior"),
    (3,  "ALCUDIA",                  "Alcúdia"),
    (4,  "ALGAIDA",                  "Algaida"),
    (5,  "ANDRAITX",                 "Andratx"),
    (6,  "ARTA",                     "Artà"),
    (7,  "BAÑALBUFAR",               "Banyalbufar"),
    (8,  "BINISALEM",                "Binissalem"),
    (9,  "BUGER",                    "Búger"),
    (10, "BUÑOLA",                   "Bunyola"),
    (11, "CALVIA",                   "Calvià"),
    (12, "CAMPANET",                 "Campanet"),
    (13, "CAMPOS DEL PUERTO",        "Campos"),
    (14, "CAPDEPERA",                "Capdepera"),
    (15, "CIUDADELA",                "Ciutadella de Menorca"),
    (16, "CONSELL",                  "Consell"),
    (17, "COSTITX",                  "Costitx"),
    (18, "DEYA",                     "Deià"),
    (19, "ESCORCA",                  "Escorca"),
    (20, "ESPORLAS",                 "Esporles"),
    (21, "ESTELLENCHS",              "Estellencs"),
    (22, "FELANITX",                 "Felanitx"),
    (23, "FERRERIAS",                "Ferreries"),
    (24, "FORMENTERA",               "Formentera"),
    (25, "FORNALUTX",                "Fornalutx"),
    (26, "IBIZA",                    "Eivissa"),
    (27, "INCA",                     "Inca"),
    (28, "LLORET DE VISTA ALEGRE",   "Lloret de Vistalegre"),
    (29, "LLOSETA",                  "Lloseta"),
    (30, "LLUBI",                    "Llubí"),
    (31, "LLUCHMAYOR",               "Llucmajor"),
    (32, "MAHON",                    "Maó"),
    (33, "MANACOR",                  "Manacor"),
    (34, "MANCOR DEL VALLE",         "Mancor de la Vall"),
    (35, "MARIA DE LA SALUD",        "Maria de la Salut"),
    (36, "MARRATXI",                 "Marratxí"),
    (37, "MERCADAL",                 "es Mercadal"),
    (38, "MONTUIRI",                 "Montuïri"),
    (39, "MURO",                     "Muro"),
    (40, "PALMA DE MALLORCA",        "Palma"),
    (41, "PETRA",                    "Petra"),
    (42, "POLLENSA",                 "Pollença"),
    (43, "PORRERAS",                 "Porreres"),
    (44, "PUEBLA, LA",               "sa Pobla"),
    (45, "PUIGPUÑENT",               "Puigpunyent"),
    (46, "SAN ANTONIO ABAD",         "Sant Antoni de Portmany"),
    (47, "SANCELLAS",                "Sencelles"),
    (48, "SAN JOSE",                 "Sant Josep de sa Talaia"),
    (49, "SAN JUAN",                 "Sant Joan"),
    (50, "SAN JUAN BAUTISTA",        "Sant Joan de Labritja"),
    (51, "SAN LORENZO DEL CARDESSAR","Sant Llorenç des Cardassar"),
    (52, "SAN LUIS",                 "Sant Lluís"),
    (53, "SANTA EUGENIA",            "Santa Eugènia"),
    (54, "SANTA EULALIA DEL RIO",    "Santa Eulària des Riu"),
    (55, "SANTA MARGARITA",          "Santa Margalida"),
    (56, "SANTA MARIA DEL CAMI",     "Santa Maria del Camí"),
    (57, "SANTAÑY",                  "Santanyí"),
    (58, "SELVA",                    "Selva"),
    (59, "SES SALINES",              "ses Salines"),
    (60, "SINEU",                    "Sineu"),
    (61, "SOLLER",                   "Sóller"),
    (62, "SON SERVERA",              "Son Servera"),
    (63, "VALLDEMOSA",               "Valldemossa"),
    (64, "VILLACARLOS",              "es Castell"),
    (65, "VILLAFRANCA DE BONANY",    "Vilafranca de Bonany"),
    # Two municipalities segregated AFTER the INE 1986 facsimile went
    # to press, so they don't appear in the printed Códigos de los
    # Municipios Actuales table. We add them as extra codes here and
    # reroute the affected pueblos in load_all.py:
    #   - Ariany was part of Petra in the printed list; it had been
    #     segregated in 1982 already but the INE table used outdated
    #     1981 census data.
    #   - Sant Cristòfol (cat. San Cristóbal) on Menorca was part of
    #     Mercadal; segregated as es Migjorn Gran in 1989.
    (66, "ARIANY",                   "Ariany"),
    (67, "ES MIGJORN GRAN",          "es Migjorn Gran"),
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
    con.executemany(
        "INSERT INTO current_municipalities (code, name, name_official) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT (code) DO UPDATE SET "
        "  name = excluded.name, name_official = excluded.name_official",
        CURRENT_MUNICIPALITIES,
    )
    print(f"  current_municipalities: {len(CURRENT_MUNICIPALITIES)} rows")
    con.close()


if __name__ == "__main__":
    main()
