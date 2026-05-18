-- Schema for the floridablanca project: the Balearic volume (Tomo VI)
-- of the Floridablanca Census of 1787, as published in facsimile by
-- the Instituto Nacional de Estadística (Madrid, 1986).
--
-- The source PDF (data/pdfs/floridablanca_tomo6_baleares.pdf, 36 pages,
-- ~4 MB) contains:
--   - A "Comentario" page summarising the Balearic data.
--   - A facsimile of the original 1787 manuscript questionnaire for
--     Palma (the capital), as preserved at the Real Academia de la
--     Historia.
--   - The glossary of abbreviations and a code table for present-day
--     (1986) municipalities.
--   - Seven tabulations (Tables 1-7) covering 111 pueblos plus a
--     provincial summary.
--
-- We model the seven tables in long form (one fact per row) so that
-- the data is queryable without further reshaping. Lookup tables
-- (category, authority, jurisdiction, district) carry the printed
-- glossary verbatim and let us decode abbreviations on the web side.

-- Lookups ---------------------------------------------------------------

-- Pueblo category codes (table 1a, column "CATEGORIA").
-- A = Aldea, Ar = Arrabal, C = Ciudad, CR = Coto Redondo,
-- D = Despoblado, L = Lugar, Pq = Parroquia, V = Villa.
CREATE TABLE IF NOT EXISTS category_codes (
    code   TEXT PRIMARY KEY,
    label  TEXT NOT NULL
);

-- Pueblo authority codes (table 1a, column "AUTORIDAD").
-- A = Alcalde, AMR = Alcalde Mayor de Realengo, AO = Alcalde Ordinario,
-- AOR = AO de Realengo, AOS = AO de Señorío, AP = Alcalde Pedáneo,
-- APR = AP de Realengo, APS = AP de Señorío,
-- C.AM = Corregidor y Alcalde Mayor, G.AL = Gobernador y Alguacil,
-- G.JO = Gobernador y Justicia Ordinario, JO = Justicia Ordinario,
-- S/A = Sin Alcalde.
CREATE TABLE IF NOT EXISTS authority_codes (
    code   TEXT PRIMARY KEY,
    label  TEXT NOT NULL
);

-- Jurisdiction codes (table 1a, column "JURISDICCION").
-- R = Realengo, S = Señorío, SE = Señorío Eclesiástico,
-- SS = Señorío Secular.
CREATE TABLE IF NOT EXISTS jurisdiction_codes (
    code   TEXT PRIMARY KEY,
    label  TEXT NOT NULL
);

-- "Partido" / district codes (table 1a, column "PARTIDO").
-- IBI = Ibiza, MAL = Mallorca, MEN = Menorca.
CREATE TABLE IF NOT EXISTS district_codes (
    code   TEXT PRIMARY KEY,
    label  TEXT NOT NULL
);

-- 1986 municipalities (printed code table, pp. 5638). 65 rows: the
-- INE facsimile uses the Castilian / administrative form in force in
-- 1986 ("ANDRAITX", "MAHON", "POLLENSA", "VILLACARLOS", …). The
-- `name_official` column carries the current official Catalan form
-- ("Andratx", "Maó", "Pollença", "es Castell", …) as fixed by Decret
-- 36/1988 and subsequent corrections; populated by load_lookups.py
-- from the Viquipèdia "Llista de municipis de les Illes Balears".
CREATE TABLE IF NOT EXISTS current_municipalities (
    code           INTEGER PRIMARY KEY,           -- 1..65
    name           TEXT NOT NULL,                 -- INE 1986 form (Castilian)
    name_official  TEXT                           -- current official Catalan form
);

-- Pueblos --------------------------------------------------------------

-- One row per 1787 pueblo as catalogued in Table 1a/1b (cod 1..111).
-- The three Ibiza parish breakdowns (Pq. de San Salvador, Pq. de S.
-- Pedro y S. Cristóbal, Pq. de Santa Eulalia) appear as supplemental
-- detail rows in Table 1a/1b; they are loaded with cod >= 200 and
-- linked to their parent (cod 26 = IBIZA).
CREATE TABLE IF NOT EXISTS pueblos (
    cod                       INTEGER PRIMARY KEY,
    name_current              TEXT NOT NULL,        -- 1986 form
    name_1787                 TEXT,                 -- as printed in the Nomenclátor de 1787
    category_code             TEXT REFERENCES category_codes(code),
    authority_code            TEXT REFERENCES authority_codes(code),
    jurisdiction_code         TEXT REFERENCES jurisdiction_codes(code),
    intendancy                TEXT,                 -- always "RdM" (Reino de Mallorca)
    district_code             TEXT REFERENCES district_codes(code),
    current_municipality_code INTEGER REFERENCES current_municipalities(code),
    -- References (table 1b).
    manuscript_page           TEXT,                 -- "PAGINA M. 1787" (Real Academia ms.)
    ine_photogram             TEXT,                 -- "FOTOGRAMA INE", e.g. "25-0020"
    -- Which numeric tables the pueblo appears in. Mirrors the dot
    -- matrix printed at the right of table 1b.
    in_table_2                BOOLEAN DEFAULT FALSE,
    in_table_3                BOOLEAN DEFAULT FALSE,
    in_table_4                BOOLEAN DEFAULT FALSE,
    in_table_5                BOOLEAN DEFAULT FALSE,
    in_table_6                BOOLEAN DEFAULT FALSE,
    in_table_7                BOOLEAN DEFAULT FALSE,
    observations              TEXT,                 -- table 1b "OBSERVACIONES"
    parent_cod                INTEGER REFERENCES pueblos(cod)   -- non-null for Ibiza parishes
);

CREATE INDEX IF NOT EXISTS idx_pueblos_name_current ON pueblos(name_current);
CREATE INDEX IF NOT EXISTS idx_pueblos_district     ON pueblos(district_code);
CREATE INDEX IF NOT EXISTS idx_pueblos_municipality ON pueblos(current_municipality_code);

-- Table 2: Population by housing type and sex --------------------------
-- "POBLACION SEGUN TIPO DE ALOJAMIENTO Y SEXO".
-- Only printed for pueblos that have non-zero collective housing.
-- Long form: one row per (pueblo, housing_type, sex). Counts include
-- the implicit "TOTAL" rollup row (housing_type='total').
CREATE TABLE IF NOT EXISTS population_by_housing (
    pueblo_cod    INTEGER NOT NULL REFERENCES pueblos(cod),
    -- 'total', 'family' (Viviendas Familiares),
    -- 'collective_religious' (Com. Religiosas under Viviendas Colectivas),
    -- 'collective_other' (Otras under Viviendas Colectivas).
    housing_type  TEXT NOT NULL,
    sex           TEXT NOT NULL,                    -- 'T', 'V', 'M'
    count         INTEGER,                          -- NULL when "-" or no data
    PRIMARY KEY (pueblo_cod, housing_type, sex)
);

-- Table 3: Population by marital status, age and sex -------------------
-- "CLASIFICACION POR ESTADO CIVIL, EDAD Y SEXO". Covers the family-
-- housing subset only (the "Colec." label over some columns flags that
-- the pueblo *also* has collective housing tabulated in Table 2).
CREATE TABLE IF NOT EXISTS population_by_marital_age_sex (
    pueblo_cod      INTEGER NOT NULL REFERENCES pueblos(cod),
    -- 'total', 'single', 'married', 'widowed'.
    marital_status  TEXT NOT NULL,
    -- '<7', '7-16', '16-25', '25-40', '40-50', '>50', 'all'.
    age_group       TEXT NOT NULL,
    sex             TEXT NOT NULL,                  -- 'T', 'V', 'M'
    count           INTEGER,
    PRIMARY KEY (pueblo_cod, marital_status, age_group, sex)
);

-- Table 4: Population by occupation ------------------------------------
-- "CLASIFICACION POR OCUPACIONES". 25 standard occupation rows plus a
-- "MENORES/SIN PROF. ES." catch-all and a TOTAL.
CREATE TABLE IF NOT EXISTS population_by_occupation (
    pueblo_cod  INTEGER NOT NULL REFERENCES pueblos(cod),
    -- Normalised occupation key, e.g. 'curas', 'beneficiados',
    -- 'tenientes_de_cura', 'sacristanes', 'acolitos',
    -- 'ordenados_titulo_patrimonio', 'ordenados_de_menores',
    -- 'hidalgos', 'abogados', 'escribanos', 'estudiantes',
    -- 'labradores', 'jornaleros', 'comerciantes', 'fabricantes',
    -- 'artesanos', 'criados', 'empleados_sueldo_real',
    -- 'fuero_militar', 'dep_inquisicion', 'sindicos_ord_relig',
    -- 'depend_cruzada', 'demandantes', 'otros',
    -- 'menores_sin_profesion', 'total'.
    occupation  TEXT NOT NULL,
    count       INTEGER,
    note        TEXT,                               -- asterisk footnotes, e.g. "23 Sacerdotes, 1 Tonsurado"
    PRIMARY KEY (pueblo_cod, occupation)
);

-- Table 5: Religious communities ---------------------------------------
-- "COMUNIDADES RELIGIOSAS". A pueblo may have several friar convents,
-- several nun convents, and "otras casas de religión" (hermitages,
-- beaterios). One row per community, with member counts split by role.
CREATE TABLE IF NOT EXISTS religious_communities (
    id            INTEGER PRIMARY KEY,
    pueblo_cod    INTEGER NOT NULL REFERENCES pueblos(cod),
    community_type TEXT NOT NULL,                   -- 'friars', 'nuns', 'other'
    name          TEXT,                             -- "San Diego", "Real Convento", "Hermita de San Honorato"
    religious_order TEXT,                           -- "Franciscanos", "Agustinos", "Carmelitas", ...
    -- Member counts. Friars use profesos/novicios/legos/donados/criados/ninos/otros.
    -- Nuns use profesas/novicias/seglares/ninas/criadas/donados/criados/otros_var/otros_muj.
    -- Pulled together into a JSON map to avoid schema gymnastics; the
    -- web layer renders the appropriate labels per community_type.
    members       JSON,
    -- For community_type='other', titulares/otros varones/mujeres are
    -- printed below the box; we keep that breakdown in members too.
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS idx_religious_communities_pueblo
    ON religious_communities(pueblo_cod);

-- Table 6: Welfare and assistance centres ------------------------------
-- "CENTROS BENEFICOS Y ASISTENCIALES". Three sub-blocks: hospitales,
-- hospicios, casas de expósitos. Each centre lists role-by-count.
CREATE TABLE IF NOT EXISTS welfare_centers (
    id           INTEGER PRIMARY KEY,
    pueblo_cod   INTEGER NOT NULL REFERENCES pueblos(cod),
    center_type  TEXT NOT NULL,                     -- 'hospital', 'hospicio', 'casa_expositos'
    name         TEXT,                              -- "De la Villa", "General", "Real", "De Misericordia"
    -- Headcount totals printed at the top of the centre.
    total        INTEGER,
    males        INTEGER,
    females      INTEGER,
    -- Role-by-count map: {capellanes, empleados, facultativos,
    -- sirvientes, enfermos, enfermas, locos, locas, expositos,
    -- expositas, otros_muj, hombres, mujeres, ninos, ninas, ...}.
    roles        JSON,
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS idx_welfare_centers_pueblo
    ON welfare_centers(pueblo_cod);

-- Table 7: Other centres -----------------------------------------------
-- "OTROS CENTROS". Colegios, seminarios, casas de enseñanza, casas de
-- piedad, casas de niñas huérfanas. One row per (centre, role).
CREATE TABLE IF NOT EXISTS other_centers (
    id          INTEGER PRIMARY KEY,
    pueblo_cod  INTEGER NOT NULL REFERENCES pueblos(cod),
    name        TEXT NOT NULL,                      -- "Colegio NSS de Sapiencia"
    role        TEXT NOT NULL,                      -- "Rector", "Colegiales", "Pensionistas", "Criados"
    count       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_other_centers_pueblo
    ON other_centers(pueblo_cod);

-- Provincial roll-up ---------------------------------------------------
-- "RESUMEN PROVINCIAL" tables I-IV at pp. 5666-5667. One JSON blob per
-- table; the structure mirrors the printed grid so the web layer can
-- render it without committing to a fixed shape.
CREATE TABLE IF NOT EXISTS province_summary (
    section_key TEXT PRIMARY KEY,                   -- 'singular_entities', 'population_by_housing', 'family_housing', 'collective_housing'
    title       TEXT NOT NULL,                      -- printed heading
    data        JSON NOT NULL                       -- arbitrary nested grid
);

-- Narrative + provenance -----------------------------------------------
-- The opening "Comentario" page (5631) and the editorial preface
-- pages (Presentacion, Real Orden de Ejecucion, Introduccion) are
-- kept verbatim for citation. The Palma manuscript facsimile is a
-- separate set of image files; we record only the page span here.
CREATE TABLE IF NOT EXISTS source_documents (
    section_key   TEXT PRIMARY KEY,                 -- 'comentario', 'palma_facsimile', 'abbreviations_glossary'
    title         TEXT NOT NULL,
    printed_pages TEXT,                             -- e.g. "5631", "5633-5636"
    body          TEXT                              -- transcribed prose; NULL for image-only sections
);
