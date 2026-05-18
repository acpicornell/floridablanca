"""Extract structured data from each PDF page using Claude Vision.

The source PDF (data/pdfs/floridablanca_tomo6_baleares.pdf) was rendered
to data/pages/page-NN.jpg by pdftoppm at 200 DPI. The PDF has no text
layer so we send each page image to Claude with a content-specific
system prompt and parse the JSON it returns.

The page → content map is hard-coded below in PAGES; running this
script extracts every productive page once and caches the JSON under
data/extracted/page-NN.json so re-runs are free.

Usage:
    python scripts/extract_pages.py                # all pending pages
    python scripts/extract_pages.py 13 14 15 16    # specific pages
    python scripts/extract_pages.py --force 19     # re-extract page 19
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "data" / "pages"
OUT_DIR = ROOT / "data" / "extracted"

MODEL = "claude-sonnet-4-5"
# Table 3 packs ~720 numeric cells per page; the verbose long-form
# JSON we ask for can run past 30K output tokens. Sonnet 4.6 supports
# up to 64K so this gives us headroom for the densest table.
MAX_TOKENS = 32000


# Per-page extraction recipe. Each entry maps a PDF page number to:
#   kind      — short tag used in filenames and downstream loaders.
#   prompt    — what Claude is told to extract.
# Pages not listed here are skipped (covers, dividers, blanks, the
# handwritten Palma facsimile which is kept as image-only reference).
@dataclass
class Recipe:
    kind: str
    prompt: str


# ---- Shared prompts -------------------------------------------------------

# Table 1a: Características administrativas. Two pages, ~50-60 pueblos each.
T1A_PROMPT = """\
This page is the printed table "1A. CARACTERISTICAS ADMINISTRATIVAS DE
LOS PUEBLOS" from the 1986 INE facsimile of the Floridablanca Census
(Tomo VI, Baleares, 1787). Each row is a pueblo with administrative
metadata.

The page is printed on a low-fidelity dot-matrix-style typewriter face.
Be careful with similar glyph pairs: R/Ñ, V/Y, I/T, S/J, 0/O, 8/B, G/0.
A *single* dot at the end of a name is a typesetting artefact, not
punctuation.

Reference list of 1986 municipality names (column "MUNICIPIO ACTUAL"
decodes to one of these): 001 ALARO, 002 ALAYOR, 003 ALCUDIA,
004 ALGAIDA, 005 ANDRAITX, 006 ARTA, 007 BAÑALBUFAR, 008 BINISALEM,
009 BUGER, 010 BUÑOLA, 011 CALVIA, 012 CAMPANET, 013 CAMPOS DEL PUERTO,
014 CAPDEPERA, 015 CIUDADELA, 016 CONSELL, 017 COSTITX, 018 DEYA,
019 ESCORCA, 020 ESPORLAS, 021 ESTELLENCHS, 022 FELANITX,
023 FERRERIAS, 024 FORMENTERA, 025 FORNALUTX, 026 IBIZA, 027 INCA,
028 LLORET DE VISTA ALEGRE, 029 LLOSETA, 030 LLUBI, 031 LLUCHMAYOR,
032 MAHON, 033 MANACOR, 034 MANCOR DEL VALLE, 035 MARIA DE LA SALUD,
036 MARRATXI, 037 MERCADAL, 038 MONTUIRI, 039 MURO,
040 PALMA DE MALLORCA, 041 PETRA, 042 POLLENSA, 043 PORRERAS,
044 PUEBLA LA, 045 PUIGPUÑENT, 046 SAN ANTONIO ABAD, 047 SANCELLAS,
048 SAN JOSE, 049 SAN JUAN, 050 SAN JUAN BAUTISTA,
051 SAN LORENZO DEL CARDESSAR, 052 SAN LUIS, 053 SANTA EUGENIA,
054 SANTA EULALIA DEL RIO, 055 SANTA MARGARITA, 056 SANTA MARIA DEL CAMI,
057 SANTAÑY, 058 SELVA, 059 SES SALINES, 060 SINEU, 061 SOLLER,
062 SON SERVERA, 063 VALLDEMOSA, 064 VILLACARLOS,
065 VILLAFRANCA DE BONANY.

Reference list of common 1787 pueblo names you will see in the
"DENOMINACION ACTUAL" column (1986 form on the left, 1787 form on the
right) — use these when an OCR glyph is ambiguous:
  ALARO/ALARO, ALAYOR/ALAYOR, ALCUDIA/ALCUDIA, ALCUDIETA/ALCUDIETA,
  ALGAIDA/ALGAYDA, ANDRAITX/ANDRAIG, ARIANY/ARIARY, ARTA/ARTA,
  BALANZAT/BALANZAT, BAÑALBUFAR/BARALBUFAR, BINIAGUAL/BINIAGUAL,
  BINIALI/BIWIALI (BINIALI), BINIAMAR/BINIAMAR, BINIARAIX/BINIARAIX,
  BINIARROIG/BINIARROY, BINIFOUBELL/BINIPAUVELL,
  BINISALEM/BENISALEM, BUGER/BUGER, BUROLA/BUROLA, CAIMARI/CAYMARI,
  CALOBRA LA/LA CALOBRA, CALVIA/CALVIA, CAMPANET/CAMPANET,
  CAMPOS DEL PUERTO/CAMPOS, CAPDELLA/ES CAP DELLA, CAPDEPERA/CAP DE PERA,
  CA'S CANA/CASCANA, CIUDADELA/CIUDADELA, CONSELL/CONSELL,
  COSTITX/COSTIX, DEYA/DEYA, ESGLAYETA LA/ESGLAYETA LA,
  ESPORLAS/ESPORLES, ESTABLIMENTS/ESTABLIMENTS, ESTELLENCHS/ESTELLENCHS,
  FELANITX/FELANITX, FERRERIAS/FERRARIAS, FIGUERA SA/FIGUERA SA,
  FORMENTERA/FORMENTERA, FORNALUTX/FORNALUIG, PORNELLS/PORNELLS
  (=FERRERIAS partido), GALDENT/GALDENT, IBIZA/IVIZA, INCA/INCA,
  JORNETS/JORNETS, LAYA/LAYA, LLANO DE LA CIUDAD/PLA DE LA CIUTAT,
  LLORITO/LLORITO, LLOSETA/LLOSETA, LLUBI/CASTELL LLUBI,
  LLUCH ALCARI/LLUCALCARI, LLUCHMAYOR/LLUCH MAYOR, MAHON/MAHON,
  MANACOR/MANACOR, MANCOR DEL VALLE/MANCOR, MARIA DE LA SALUD/MARIA,
  MARRATXI/MARRATXI, MASANELLA/MASANELLA, MERCADAL/MERCADAL,
  MIRABO/MIRABONA, MONTUIRI/MONTUIRI, MOSCARI/MOSCARI, MURO/MURO,
  NUESTRA SEÑORA DE JESUS/NUESTRA SEÑORA DE JESUS,
  ORIENT/ORIENT, PALMA/PALMA, PETRA/PETRA, PINA/PINA,
  POLLENSA/POLLENZA, PORRERAS/PORRERAS, PORTOL/PORTOL,
  PUEBLA LA/LA POBLA, PUIGPUNENT/PUIG-PUNYENT, RANDA/RANDA,
  RECO EL/SARRECO, RUBERTS/RUBERTS,
  SALINAS LAS/LAS SALINAS O SAN JOSEPH, SAN AGUSTIN/SAN AGUSTIN EN PORMARY,
  SAN ANTONIO ABAD/SAN ANTONIO EN PORMARY,
  SAN CARLOS/SAN CARLOS EN SANTA EULALIA, SAN CLEMENTE/SAN CLEMENTE,
  SAN CRISTOBAL/SAN CHRISTOVAL, SAN JOSE/SAN JOSE EN PORMARY,
  SAN JUAN/SAN JUAN, SAN LORENZO/SAN LORENZO EN SANTA EULALIA,
  SAN LORENZO DEL CARDESSAR/SAN LORENS DES CARDESAR, SAN LUIS/SAN LUIS,
  SAN MATEO/SAN MATEO EN BALANSAR, SAN MIGUEL/SAN MIGUEL EN BALANSAR,
  SAN RAFAEL/LLANO DE LA VILLA, SANCELLAS/SANCELLAS,
  SANTA CATALINA/SANTA CATALINA, SANTA EUGENIA/SANTA EUGENIA,
  SANTA EULALIA DEL RIO/SANTA EULALIA,
  SANTA GERTRUDIS/SANTA GERTRUDIS EN BALANSAR,
  SANTA INES/SANTA INES EN BALANSAR, SANTA MARGARITA/SANTA MARIA,
  SANTA MARIA DEL CAMI/SANTA MARIA, SANTARY/SANTAGNI, SELVA/SELVA,
  SINEU/SINEU, SOLLER/SOLLER, SON GALIANA/SON GALIANA, SON SEGUI/SON SEGUI,
  SON SERVERA/SON SERVERA, SON SURER/SON SURER, ULLARO/HUYERO,
  VALL DEN MARCH/VALL DEN MARCH, VALLDEMOSA/VALL DE MOSA,
  VILAFRANCA DE BONANY/VILA FRANCA, VILLACARLOS/VILLA CARLOS.

Extract one JSON object per row. Output a JSON array under the key
"pueblos". Every row must produce one object even when the printed
cell holds a "..." (data unknown) or a "-" (no data / zero) marker —
in that case use null for the field.

For each pueblo extract:
- cod (int)              the COD column (1..111).
- name_current (str)     "DENOMINACION ACTUAL" column. Verbatim.
- name_1787 (str)        "DENOMINACION EN EL NOMENCLATOR DE 1787". Verbatim.
- category (str|null)    "CATEGORIA" cell. One of A, Ar, C, CR, D, L, Pq, V.
- authority (str|null)   "AUTORIDAD" cell. One of A, AMR, AO, AOR, AOS,
                         AP, APR, APS, C.AM, G.AL, G.JO, JO, S/A.
- jurisdiction (str|null) "JURISDICCION" cell: R, S, SE, SS.
- intendancy (str|null)  "INTENDENCIA" cell, usually "RdM".
- district (str|null)    "PARTIDO" cell: IBI, MAL, MEN.
- current_municipality (int|null)  "MUNICIPIO ACTUAL" code (1..65).
                         "..." means no current municipality assigned →
                         null.

Some name_current cells carry a trailing "(*)" footnote marker — strip
it and add it to a separate "footnote" key, e.g. "footnote": "(*)".
Drop bullet/center dots if any.

The bottom of the second page lists "Detalles de I.IZA" with parish
sub-rows ("Pq. de San Salvador", "Pq. de S. Pedro y S. Cristóbal",
"Pq. de Santa Eulalia"). These rows have no COD; emit them after the
numbered rows with cod=null and a "parent_name": "IBIZA" key.

Output ONLY a JSON object: {"pueblos": [...]}. No commentary."""


# Table 1b: References. Two pages, same rows as 1a.
T1B_PROMPT = """\
This page is the printed table "1B. REFERENCIAS" from the 1986 INE
facsimile of the Floridablanca Census, paired with table 1A on the
facing page. One row per pueblo, keyed by the COD column.

Extract one JSON object per row, output as a JSON array under "refs":
- cod (int)
- manuscript_page (str|null)   "PAGINA M. 1787". "-" → null. "..." → null.
- ine_photogram (str|null)     "FOTOGRAMA INE", e.g. "25-0020". "-" → null.
- in_table_2 (bool)            true iff the cell under column "2" has a dot.
- in_table_3 (bool)            same for column "3".
- in_table_4 (bool)            same for column "4".
- in_table_5 (bool)            same for column "5".
- in_table_6 (bool)            same for column "6".
- in_table_7 (bool)            same for column "7".
- observations (str|null)      free-text "OBSERVACIONES" column. Verbatim.

CRITICAL: the OBSERVACIONES column is SPARSE — most rows have
NO text on them at all. Each printed observation belongs to
EXACTLY ONE COD (the row it visually sits on). Do NOT carry an
observation forward to the blank rows below it. If a row's
OBSERVACIONES cell is empty/blank, emit observations=null.
Repeating the same observation across adjacent rows is wrong;
the source has one observation per cod, or none.

The bottom of the second page may include rows for the three Ibiza
parishes ("Pq. de San Salvador" etc.) with no COD — emit them in
order, cod=null. Output ONLY {"refs": [...]}. No commentary."""


# Table 2: Population by housing.
T2_PROMPT = """\
This page is the printed table "2. POBLACION SEGUN TIPO DE ALOJAMIENTO
Y SEXO (Detalle de los pueblos con habitantes en viviendas
colectivas)". Each row is a pueblo with a COD; each column block is a
sex (T / V / M = total / varones / mujeres) for a housing type.

Column blocks:
  TOTAL (total of the row), VIVIENDAS FAMILIARES, VIVIENDAS COLECTIVAS
  -> COM. RELIGIOSAS, VIVIENDAS COLECTIVAS -> OTRAS.

The last three rows at the bottom are roll-ups (not pueblos): "SUMA",
"PUEBLOS SIN VIV.COLECTIVAS", "TOTAL PROVINCIAL". Extract them with
cod=null and a "label" field carrying the row name verbatim.

Output a JSON object {"rows": [...]} where each item is:
  cod (int|null)
  label (str|null)              row label (the pueblo name for cod-bearing
                                rows; "SUMA"/"TOTAL PROVINCIAL"/... for
                                the roll-up rows)
  total       { "T": int|null, "V": int|null, "M": int|null }
  family      { "T": int|null, "V": int|null, "M": int|null }
  collective_religious { ... }
  collective_other     { ... }

Use null when the printed cell is "-". Output ONLY the JSON. No commentary."""


# Roster of all 111 Floridablanca pueblos (1986 form) — included in
# the Table 3/4 prompts so the model can self-correct OCR drift in
# the column headers (BURCLA → BUROLA, ALCANIZ → ALCUDIA, etc.).
PUEBLO_ROSTER = (
    "ALARO(1) ALAYOR(2) ALCUDIA(3) ALCUDIETA(4) ALGAIDA(5) ANDRAITX(6) "
    "ARIANY(7) ARTA(8) BALANZAT(9) BAÑALBUFAR(10) BINIAGUAL(11) BINIALI(12) "
    "BINIAMAR(13) BINIARAIX(14) BINIARROIG(15) BINIFOUBELL(16) BINISALEM(17) "
    "BUGER(18) BUROLA(19) CAIMARI(20) CALOBRA,LA(21) CALVIA(22) CAMPANET(23) "
    "CAMPOS DEL PUERTO(24) CAPDELLA(25) CAPDEPERA(26) CA'S CANA(27) "
    "CIUDADELA(28) CONSELL(29) COSTITX(30) DEYA(31) ESGLAYETA,LA(32) "
    "ESPORLAS(33) ESTABLIMENTS(34) ESTELLENCHS(35) FELANITX(36) "
    "FERRERIAS(37) FIGUERA,SA(38) FORMENTERA(39) FORNALUTX(40) PORNELLS(41) "
    "GALDENT(42) IBIZA(43) INCA(44) JORNETS(45) LAYA(46) "
    "LLANO DE LA CIUDAD(47) LLORITO(48) LLOSETA(49) LLUBI(50) "
    "LLUCH ALCARI(51) LLUCHMAYOR(52) MAHON(53) MANACOR(54) "
    "MANCOR DEL VALLE(55) MARIA DE LA SALUD(56) MARRATXI(57) "
    "MASANELLA(58) MERCADAL(59) MIRABO(60) MONTUIRI(61) MOSCARI(62) "
    "MURO(63) NUESTRA SEÑORA DE JESUS(64) ORIENT(65) PALMA(66) PETRA(67) "
    "PINA(68) POLLENSA(69) PORRERAS(70) PORTOL(71) PUEBLA,LA(72) "
    "PUIGPUNENT(73) RANDA(74) RECO,EL(75) RUBERTS(76) SALINAS,LAS(77) "
    "SAN AGUSTIN(78) SAN ANTONIO ABAD(79) SAN CARLOS(80) SAN CLEMENTE(81) "
    "SAN CRISTOBAL(82) SAN JOSE(83) SAN JUAN(84) SAN LORENZO(85) "
    "SAN LORENZO DEL CARDESSAR(86) SAN LUIS(87) SAN MATEO(88) "
    "SAN MIGUEL(89) SAN RAFAEL(90) SANCELLAS(91) SANTA CATALINA(92) "
    "SANTA EUGENIA(93) SANTA EULALIA DEL RIO(94) SANTA GERTRUDIS(95) "
    "SANTA INES(96) SANTA MARGARITA(97) SANTA MARIA DEL CAMI(98) "
    "SANTARY(99) SELVA(100) SINEU(101) SOLLER(102) SON GALIANA(103) "
    "SON SEGUI(104) SON SERVERA(105) SON SURER(106) ULLARO(107) "
    "VALL DEN MARCH(108) VALLDEMOSA(109) VILAFRANCA DE BONANY(110) "
    "VILLACARLOS(111)."
)


# Table 3: Marital status × age × sex. One pueblo block per labelled
# column. Each page has TWO grids (upper + lower) of ~5 pueblos each.
T3_PROMPT = f"""\
This page is from table "3. CLASIFICACION POR ESTADO CIVIL, EDAD Y
SEXO". It has TWO grids stacked vertically; each grid has 4-6 pueblo
columns. Each column header carries the pueblo name and its COD; some
columns are flagged "Colec." in the row right above the COD (meaning
this pueblo also has collective housing tabulated in table 2 — the
counts shown here are family-housing only).

When OCR ambiguity makes a header letter unclear, snap the name to
the closest entry in this canonical roster: {PUEBLO_ROSTER}

For each pueblo column, extract a compact numeric block keyed by
marital status. Each marital-status block is an array of seven
3-tuples (one tuple per age band, in the FIXED order shown below).
Each tuple is [T, V, M] (total, varones, mujeres). Use null when a
printed cell is "-".

Marital statuses (keys): "total", "single", "married", "widowed"
  (TOTAL / SOLTEROS / CASADOS / VIUDOS as printed).
Age-band order inside each array (always exactly 7 entries):
  index 0 = "all"   (the row labelled with just the marital status,
                     i.e. TOTAL, SOLTEROS, CASADOS or VIUDOS — this is
                     the rollup row above the seven age-band rows)
  index 1 = "<7"     ("< 7")
  index 2 = "7-16"   ("7 a 16")
  index 3 = "16-25"  ("16 a 25")
  index 4 = "25-40"  ("25 a 40")
  index 5 = "40-50"  ("40 a 50")
  index 6 = ">50"    ("> 50")

If a cell is empty / printed as "-", use null in the tuple. NEVER
omit a tuple — emit 7 tuples per marital-status block even when most
are all-null.

Output schema:
{{
  "pueblos": [
    {{
      "cod":  41,
      "name": "BUROLA",
      "is_colectivo_subset": false,
      "stats": {{
        "total":   [[T,V,M], [T,V,M], ..., [T,V,M]],
        "single":  [[T,V,M], ..., [T,V,M]],
        "married": [[T,V,M], ..., [T,V,M]],
        "widowed": [[T,V,M], ..., [T,V,M]]
      }}
    }}
  ]
}}
cod is the integer printed in small font right under the pueblo
name; ALWAYS extract it — never leave it null when it is visible.

A column may carry a parish name in place of a COD ("Pq. San Salvador",
"Pq. S.Pedro y S.Cristóbal", "Pq. Sta Eulalia") — in that case cod=null
and "name" is the parish label verbatim.

If a column is unreadable or empty in this image, omit it from output.
Output ONLY the JSON object, NO commentary, NO markdown fence."""


# Table 4: Occupations.
T4_PROMPT = f"""\
This page is from table "4. CLASIFICACION POR OCUPACIONES". The page
contains TWO grids stacked vertically; each grid lists ~10 pueblo
columns (column header: pueblo name + COD) crossed with profession
rows.

When OCR ambiguity makes a header letter unclear, snap the name to
the closest entry in this canonical roster: {PUEBLO_ROSTER}

Profession rows in order (one row each):
  CURAS, BENEFICIADOS, TENIENTES DE CURA, SACRISTANES, ACOLITOS,
  ORDEN. T. PATRIMONIO (Ordenados a título de patrimonio),
  ORDEN. DE MENORES, HIDALGOS, ABOGADOS, ESCRIBANOS, ESTUDIANTES,
  LABRADORES, JORNALEROS, COMERCIANTES, FABRICANTES, ARTESANOS,
  CRIADOS, EMPL. SUELDO REAL, FUERO MILITAR, DEP. INQUISICION,
  SINDICOS ORD. RELIG., DEPEND. CRUZADA, DEMANDANTES, OTROS,
  MENORES/SIN PROF. ES., TOTAL.

Some pueblos carry an asterisk footnote at the bottom (e.g. "* 23
Sacerdotes / 1 Tonsurado" for ALCUDIA, "* 3 Vicarios / * 4 Expósitos"
for SAN/CIUDADELA). Attach footnotes to the relevant pueblo as a
single "notes" string.

Some columns carry a "(*)" mark next to the COD; capture this as
"has_footnote": true.

Use these snake_case keys for profession:
  curas, beneficiados, tenientes_de_cura, sacristanes, acolitos,
  ordenados_titulo_patrimonio, ordenados_de_menores, hidalgos,
  abogados, escribanos, estudiantes, labradores, jornaleros,
  comerciantes, fabricantes, artesanos, criados,
  empleados_sueldo_real, fuero_militar, dep_inquisicion,
  sindicos_ord_relig, depend_cruzada, demandantes, otros,
  menores_sin_profesion, total.

Output {{"pueblos": [...]}} where each item is:
  cod (int|null)
  name (str)
  has_footnote (bool)
  notes (str|null)
  counts: {{ profession_key: int|null, ... }}   one entry per profession row

null for cells printed as "-". Output ONLY the JSON, no commentary."""


# Table 5: Religious communities.
T5_PROMPT = """\
This page is from table "5. COMUNIDADES RELIGIOSAS". The top row
holds the PUEBLO names (LLUCHMAYOR, MAHON, MANACOR, MERCADAL, MURO,
…). Each pueblo column is wide enough to host SEVERAL convent
sub-columns side-by-side; a sub-column carries one convent name (e.g.
"S.Buenaventura", "Del Carmen", "S.Vicente Ferrer", "Santa Ana"), its
religious order on the line below (e.g. "Franciscanos Observantes",
"Carmelitas", "Dominicos", "Mínimos"), and a vertical stack of member
counts (profesos / novicios / legos / donados / criados / ninos /
otros).

CRITICAL: every convent / nun house / beaterio sub-column belongs to
the pueblo named at the very top of the page. NEVER emit a top-level
"pueblo" entry whose name is actually a convent or order (e.g.
"S.Buenaventura", "Del Carmen", "De Jesús", "Santa Ana", "Beaterio
Tercera Orden Franciscana", "Beaterio de la Enseñanza"). Those are
sub-columns and MUST be attached to their parent pueblo via the
"friars", "nuns" or "other" arrays.

Three horizontal blocks (top to bottom):
  1) CONVENTOS DE FRAILES — each friar convent has:
      name (e.g. "San Diego", "Real Convento", "Sancti Spiritus")
      order (line below the name, e.g. "Franciscanos", "Agustinos",
        "Carmelitas", "Cistercienses", "Trinitarios")
      counts (rows): profesos, novicios, legos, donados, criados,
        ninos, otros.

  2) CONVENTOS DE MONJAS — each nun convent has:
      name, order, then counts: profesas, novicias, sras_seglares,
      ninas, criadas, donados, criados, otros_var, otros_muj.

  3) OTRAS CASAS DE RELIGION — listed by name (e.g. "Hermita de San
     Honorato", "Beaterio", "Beaterio Tercera Orden Franciscana",
     "Hermita Stma. Trinidad"). Below the box: TITULARES varones /
     mujeres, then OTROS varones / mujeres.

Also extract the TOTAL / VARONES / MUJERES headcount printed at the
very top for each pueblo, when present.

Output a JSON object: {"pueblos": [...]} where each pueblo is:
  name (str)
  total       (int|null)
  males       (int|null)
  females     (int|null)
  friars: [ { name, order, profesos, novicios, legos, donados,
              criados, ninos, otros } ]   -- numbers null when "-"
  nuns:   [ { name, order, profesas, novicias, sras_seglares,
              ninas, criadas, donados, criados, otros_var, otros_muj } ]
  other:  [ { name, titulares_varones, titulares_mujeres,
              otros_varones, otros_mujeres } ]

If a pueblo has "= = = NO CONSTA DATO ALGUNO = = =" written across a
block, return an empty list for that block and set a "notes" key on
the pueblo.

If a pueblo spans more than one page (e.g. PALMA), still emit one
JSON entry; the loader merges. To enable merging, set
"continues": true when the page only shows part of the pueblo's data
(top headcount block missing → counts continue from previous page).

Output ONLY the JSON. No commentary."""


# Table 6: Welfare centres.
T6_PROMPT = """\
This page is table "6. CENTROS BENEFICOS Y ASISTENCIALES". Columns are
pueblos; rows are hospitals / hospicios / casas de expósitos.

For each pueblo, three sub-blocks may appear:
  HOSPITALES — each hospital is a sub-column with a name (e.g. "De la
    Villa", "St María Magdalena", "De Pobres", "Sangre de Jesucristo",
    "General", "Real", "S. Pedro", "De la Virgen") and a role/count
    table: CAPELLANES, EMPLEADOS, FACULTATIVOS, SIRVIENTES,
    ENFERMOS, ENFERMAS, LOCOS, LOCAS, EXPOSITOS, EXPOSITAS,
    OTROS (Muj).

  HOSPICIOS — same shape, name e.g. "De Misericordia" with rows
    CAPELLANES, EMPLEADOS, SIRVIENTES, HOMBRES, MUJERES, NINOS,
    NINAS, OTROS.

  CASAS DE EXPOSITOS — rows EMPLEADOS, NINOS, NINAS, OTROS.

Also the very top of each pueblo block shows TOTAL / VARONES / MUJERES.

Output {"pueblos": [...]} where each pueblo has:
  name (str)
  total, males, females (int|null)
  hospitals: [ { name, capellanes, empleados, facultativos,
                 sirvientes, enfermos, enfermas, locos, locas,
                 expositos, expositas, otros_muj, otras_acogidas,
                 notes } ]
  hospices:  [ { name, capellanes, empleados, sirvientes, hombres,
                 mujeres, ninos, ninas, otros, notes } ]
  foundling_houses: [ { empleados, ninos, ninas, otros, notes } ]

If a block reads "= = = NO CONSTA NINGUN DATO = = =", return an empty
list and set "no_data": true on the pueblo.

null for cells printed as "-". Output ONLY the JSON. No commentary."""


# Table 7: Other centres.
T7_PROMPT = """\
This page is table "7. OTROS CENTROS". It is a two-column listing of
non-religious, non-welfare institutions (colleges, seminaries,
schools, casas de piedad, casas de niñas huérfanas, ...). Each entry:
  COD (int)            pueblo code
  PUEBLOS (str)        pueblo name
  CENTRO (str)         institution name, e.g. "Colegio NSS de Sapiencia"
  DENOMINACION DEL CARGO O EMPLEO  role, e.g. "Rector", "Colegiales",
                                   "Pensionistas", "Criados", "Mujeres"
  N. PERSONAS (int)    count

Some centros span multiple role lines — the centro name and the COD
appear only on the first line; subsequent lines repeat the previous
centro implicitly. At the bottom of the page a "TOTAL / Varones /
Mujeres" tally may appear; capture as a separate "summary" key.

Output {"entries": [...]} with one entry per (centro, role) pair:
  cod (int)
  pueblo (str)
  centro (str)
  role (str)
  count (int|null)
Plus optional "summary": { "total": int, "males": int, "females": int }.

Output ONLY the JSON. No commentary."""


# Comentario: narrative on p3 of the PDF.
COMENTARIO_PROMPT = """\
This page is the "COMENTARIO" prose preamble to the Balearic volume of
the 1787 Floridablanca Census (INE 1986 facsimile, p. 5631). It also
embeds a "NOTA" block reproduced from the original 1787 publication
(typeset in italic with old-style spelling and accents).

Transcribe the main "COMENTARIO" prose paragraphs verbatim into a
"body" field. Transcribe the embedded "NOTA" block verbatim into a
"note_1787" field. Preserve paragraph breaks. Preserve the old-style
typography of the NOTA (`Bayles`, `Tugado`, `Quartones`, etc.) — do
not modernise spelling.

Also extract the bullet list of the eleven "entidades de población
... consideración de Ciudades" as a string list "cities".

Output: {"body": "...", "note_1787": "...", "cities": [...]}. No commentary."""


PAGES: dict[int, Recipe] = {
    3:  Recipe("comentario",        COMENTARIO_PROMPT),
    12: Recipe("table_1a_part1",    T1A_PROMPT),
    13: Recipe("table_1b_part1",    T1B_PROMPT),
    14: Recipe("table_1a_part2",    T1A_PROMPT),
    15: Recipe("table_1b_part2",    T1B_PROMPT),
    17: Recipe("table_2",           T2_PROMPT),
    19: Recipe("table_3_part1",     T3_PROMPT),
    20: Recipe("table_3_part2",     T3_PROMPT),
    21: Recipe("table_3_part3",     T3_PROMPT),
    22: Recipe("table_3_part4",     T3_PROMPT),
    23: Recipe("table_3_part5",     T3_PROMPT),
    24: Recipe("table_3_part6",     T3_PROMPT),
    25: Recipe("table_4_part1",     T4_PROMPT),
    26: Recipe("table_4_part2",     T4_PROMPT),
    27: Recipe("table_4_part3",     T4_PROMPT),
    29: Recipe("table_5_part1",     T5_PROMPT),
    30: Recipe("table_5_part2",     T5_PROMPT),
    31: Recipe("table_5_part3",     T5_PROMPT),
    32: Recipe("table_5_part4",     T5_PROMPT),
    33: Recipe("table_5_part5",     T5_PROMPT),
    34: Recipe("table_5_part6",     T5_PROMPT),
    35: Recipe("table_6",           T6_PROMPT),
    36: Recipe("table_7",           T7_PROMPT),
}


def _b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("ascii")


def _extract_json(text: str) -> dict:
    """Find the first {...} object in the response and parse it."""
    text = text.strip()
    if text.startswith("```"):
        # ```json\n...\n```
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object in response: {text[:200]}...")
    return json.loads(text[start : end + 1])


def extract_page(client: Anthropic, page: int, recipe: Recipe) -> dict:
    path = PAGES_DIR / f"page-{page:02d}.jpg"
    if not path.exists():
        raise FileNotFoundError(path)
    # Streaming is required by the SDK whenever max_tokens is high
    # enough that the response could exceed the 10-minute non-stream
    # ceiling. We always stream so behaviour is consistent.
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=(
            "You are an OCR/extraction assistant specialised in Spanish "
            "historical census tables. Return strict JSON only — no "
            "markdown fences, no commentary. Use snake_case keys and "
            "null for missing cells."
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": _b64(path),
                        },
                    },
                    {"type": "text", "text": recipe.prompt},
                ],
            }
        ],
    ) as stream:
        msg = stream.get_final_message()
    text = "".join(block.text for block in msg.content if block.type == "text")
    try:
        payload = _extract_json(text)
    except Exception:
        # Persist raw text for forensic inspection.
        (OUT_DIR / f"page-{page:02d}.raw.txt").write_text(text, encoding="utf-8")
        raise
    payload["_meta"] = {
        "page": page,
        "kind": recipe.kind,
        "model": MODEL,
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
    }
    return payload


def main() -> int:
    load_dotenv(ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", type=int,
                    help="Specific page numbers to extract (default: all)")
    ap.add_argument("--force", action="store_true",
                    help="Re-extract even if a cached JSON exists")
    args = ap.parse_args()

    targets = sorted(args.pages) if args.pages else sorted(PAGES.keys())

    client = Anthropic()
    total_in = 0
    total_out = 0
    for page in targets:
        if page not in PAGES:
            print(f"  page {page}: no recipe configured, skipping")
            continue
        out = OUT_DIR / f"page-{page:02d}.json"
        if out.exists() and not args.force:
            print(f"  page {page}: cached → {out.name}")
            continue
        recipe = PAGES[page]
        print(f"  page {page} [{recipe.kind}] … ", end="", flush=True)
        t0 = time.time()
        try:
            payload = extract_page(client, page, recipe)
        except Exception as e:
            print(f"FAILED ({e})")
            continue
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        dt = time.time() - t0
        meta = payload["_meta"]
        total_in += meta["input_tokens"]
        total_out += meta["output_tokens"]
        print(f"ok in {dt:.1f}s "
              f"(in {meta['input_tokens']} / out {meta['output_tokens']})")
    print(f"\nTotals: in {total_in} / out {total_out} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
