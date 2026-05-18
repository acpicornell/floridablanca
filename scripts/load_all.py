"""Load every per-page JSON under data/extracted/ into DuckDB.

Idempotent: each section truncates its tables before inserting, so
re-running after a re-extract is safe.

Usage:
    python scripts/load_all.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
EXTRACTED = ROOT / "data" / "extracted"
DB_PATH = ROOT / "db" / "floridablanca.duckdb"


def _read(name: str) -> dict | None:
    p = EXTRACTED / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# Strip trailing "(*)" footnote markers from a pueblo name. The marker
# is purely typographic — it flags pueblos no longer present as
# distinct entities in the 1986 municipality map.
_FOOTNOTE_RE = re.compile(r"\s*\(\*+\)\s*$")


def _clean_name(s: str | None) -> tuple[str | None, bool]:
    if not s:
        return s, False
    if _FOOTNOTE_RE.search(s):
        return _FOOTNOTE_RE.sub("", s).strip(), True
    return s.strip(), False


# OCR-driven typos that we map back to the canonical glossary code. The
# 1986 INE typewriter face confuses G/C and a few other glyph pairs in
# the cramped 3-character cell, so the same correction comes up often.
_AUTHORITY_FIXES = {
    "C.JO": "G.JO",
    "C.AL": "G.AL",
    "G.AM": "C.AM",
}
_CATEGORY_FIXES: dict[str, str] = {}
_JURISDICTION_FIXES = {
    "SF": "SE",
}


def _norm(value, fixes):
    """Trim stray trailing punctuation and apply the OCR-fix table."""
    if not value:
        return value
    v = value.strip().rstrip(".* ").strip()
    return fixes.get(v, v)


def _validate(value, valid: set[str], where: str) -> str | None:
    if value is None or value == "":
        return None
    if value not in valid:
        print(f"    [warn] {where}: unknown code {value!r} → NULL")
        return None
    return value


def load_table_1(con: duckdb.DuckDBPyConnection) -> None:
    """Pueblos: combine table 1a (parts 1+2) with table 1b (parts 1+2)."""
    valid_cat   = {r[0] for r in con.execute("SELECT code FROM category_codes").fetchall()}
    valid_auth  = {r[0] for r in con.execute("SELECT code FROM authority_codes").fetchall()}
    valid_juris = {r[0] for r in con.execute("SELECT code FROM jurisdiction_codes").fetchall()}
    valid_dist  = {r[0] for r in con.execute("SELECT code FROM district_codes").fetchall()}
    valid_muni  = {r[0] for r in con.execute("SELECT code FROM current_municipalities").fetchall()}

    a1 = _read("page-12.json") or {"pueblos": []}
    a2 = _read("page-14.json") or {"pueblos": []}
    b1 = _read("page-13.json") or {"refs": []}
    b2 = _read("page-15.json") or {"refs": []}

    pueblos_a = a1["pueblos"] + a2["pueblos"]
    pueblos_b = b1["refs"] + b2["refs"]

    # Pair rows. Numbered rows pair by cod; the Ibiza parish rows are
    # appended in the same order to both tables and pair positionally.
    by_cod = {p["cod"]: p for p in pueblos_b if p.get("cod") is not None}
    extras_b = [p for p in pueblos_b if p.get("cod") is None]
    extras_a = [p for p in pueblos_a if p.get("cod") is None]

    rows = []
    notes_rows = []
    for pa in pueblos_a:
        cod = pa.get("cod")
        if cod is None:
            continue
        pb = by_cod.get(cod, {})
        name_current, footnote = _clean_name(pa.get("name_current"))
        name_1787, _ = _clean_name(pa.get("name_1787"))
        observations = pb.get("observations")
        if footnote and not observations:
            observations = "(*) Pueblo no incluido en el mapa municipal de 1986."
        elif footnote:
            observations = "(*) Pueblo no incluido en el mapa municipal de 1986. " + observations
        rows.append((
            cod,
            name_current,
            name_1787,
            _validate(_norm(pa.get("category"),     _CATEGORY_FIXES),     valid_cat,   f"cod {cod} category"),
            _validate(_norm(pa.get("authority"),    _AUTHORITY_FIXES),    valid_auth,  f"cod {cod} authority"),
            _validate(_norm(pa.get("jurisdiction"), _JURISDICTION_FIXES), valid_juris, f"cod {cod} jurisdiction"),
            pa.get("intendancy"),
            _validate(pa.get("district"), valid_dist, f"cod {cod} district"),
            _validate(pa.get("current_municipality"), valid_muni, f"cod {cod} municipality"),
            pb.get("manuscript_page"),
            pb.get("ine_photogram"),
            bool(pb.get("in_table_2")),
            bool(pb.get("in_table_3")),
            bool(pb.get("in_table_4")),
            bool(pb.get("in_table_5")),
            bool(pb.get("in_table_6")),
            bool(pb.get("in_table_7")),
            observations,
            None,    # parent_cod
        ))

    # Ibiza parish supplemental rows. cod assigned 200, 201, 202.
    # Canonical parish names (the printed table has them as the three
    # "Pq. de …" rows under the IBIZA detail block); we patch the
    # commonly-mangled middle one here.
    CANONICAL_PARISH_NAMES = [
        "Pq. de San Salvador",
        "Pq. de S. Pedro y S. Cristóbal",
        "Pq. de Santa Eulalia",
    ]
    ibiza_cod = next(
        (p.get("cod") for p in pueblos_a
         if (p.get("name_current") or "").upper().startswith("IBIZA")),
        None,
    )
    for i, (pa, pb) in enumerate(zip(extras_a, extras_b)):
        name_current, _ = _clean_name(pa.get("name_current"))
        name_1787, _ = _clean_name(pa.get("name_1787"))
        if i < len(CANONICAL_PARISH_NAMES):
            name_current = CANONICAL_PARISH_NAMES[i]
        rows.append((
            200 + i,
            name_current,
            name_1787,
            _validate(_norm(pa.get("category"),     _CATEGORY_FIXES),     valid_cat,   f"parish {i} category"),
            _validate(_norm(pa.get("authority"),    _AUTHORITY_FIXES),    valid_auth,  f"parish {i} authority"),
            _validate(_norm(pa.get("jurisdiction"), _JURISDICTION_FIXES), valid_juris, f"parish {i} jurisdiction"),
            pa.get("intendancy"),
            _validate(pa.get("district"), valid_dist, f"parish {i} district"),
            _validate(pa.get("current_municipality"), valid_muni, f"parish {i} municipality"),
            pb.get("manuscript_page"),
            pb.get("ine_photogram"),
            bool(pb.get("in_table_2")),
            bool(pb.get("in_table_3")),
            bool(pb.get("in_table_4")),
            bool(pb.get("in_table_5")),
            bool(pb.get("in_table_6")),
            bool(pb.get("in_table_7")),
            pb.get("observations"),
            ibiza_cod,
        ))

    # Children (Ibiza parishes) carry a FK to their IBIZA parent; delete
    # them first so DuckDB lets us truncate the parent rows.
    con.executemany(
        "INSERT INTO pueblos VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    print(f"  pueblos: {len(rows)} rows")


def load_table_2(con: duckdb.DuckDBPyConnection) -> None:
    """Population by housing type and sex."""
    d = _read("page-17.json")
    if not d:
        print("  population_by_housing: source page-17.json missing, skipped")
        return
    name_to_cod = {
        r[0].upper(): r[1]
        for r in con.execute(
            "SELECT name_current, cod FROM pueblos"
        ).fetchall()
    }
    rows = []
    for r in d.get("rows", []):
        cod = r.get("cod")
        label = (r.get("label") or "").strip()
        # Prefer the printed label when it matches a real pueblo —
        # the model sometimes mis-reads the tiny COD digit but reads
        # the pueblo name cleanly (e.g. FELANITX cod=35 → 36).
        if label and label.upper() in name_to_cod:
            cod = name_to_cod[label.upper()]
        if cod is None:
            continue                 # roll-up rows handled separately
        # Cross-check the printed TOTAL against the sum of its three
        # components. Either side may carry an OCR misread, so we
        # don't auto-correct — just surface mismatches for review.
        for sex in ("T", "V", "M"):
            fam = (r.get("family") or {}).get(sex)
            rel = (r.get("collective_religious") or {}).get(sex)
            oth = (r.get("collective_other") or {}).get(sex)
            tot = (r.get("total") or {}).get(sex)
            if fam is not None and tot is not None:
                calc = (fam or 0) + (rel or 0) + (oth or 0)
                if calc != tot:
                    print(f"    [check] cod {cod} {label} [{sex}] "
                          f"total={tot} vs components sum={calc}")
        for housing_type, key in (
            ("total", "total"),
            ("family", "family"),
            ("collective_religious", "collective_religious"),
            ("collective_other", "collective_other"),
        ):
            block = r.get(key) or {}
            for sex in ("T", "V", "M"):
                rows.append((cod, housing_type, sex, block.get(sex)))
    con.executemany("INSERT INTO population_by_housing VALUES (?, ?, ?, ?)", rows)
    print(f"  population_by_housing: {len(rows)} rows")


_AGE_ORDER = ["all", "<7", "7-16", "16-25", "25-40", "40-50", ">50"]
_SEX_ORDER = ["T", "V", "M"]


def _resolve_cod(p: dict, name_to_cod: dict[str, int],
                 parish_to_cod: dict[str, int]) -> int | None:
    """Best-effort cod resolution: trust the cod from the extraction
    when present, else look up by pueblo name. The model sometimes
    misreads small COD digits but reads the full pueblo name cleanly.
    """
    cod = p.get("cod")
    if cod is not None:
        return cod
    name = (p.get("name") or "").strip()
    if not name:
        return None
    parish_cod = _is_parish(name)
    if parish_cod is not None:
        return parish_cod
    if name in parish_to_cod:
        return parish_to_cod[name]
    return name_to_cod.get(name.upper())


def load_table_3(con: duckdb.DuckDBPyConnection) -> None:
    """Population by marital status × age × sex.

    Accepts two extraction shapes:
      - Compact (current): pueblo has `stats: {marital: [[T,V,M], …]}`
        with 7 age-band tuples in `_AGE_ORDER`.
      - Long-form (legacy): pueblo has `rows: [{marital_status,
        age_group, sex, count}, …]`.
    """
    rows = []
    seen: set[tuple] = set()
    parish_name_to_cod = _build_parish_lookup(con)
    name_to_cod = {
        r[0].upper(): r[1]
        for r in con.execute(
            "SELECT name_current, cod FROM pueblos"
        ).fetchall()
    }
    for n in range(19, 25):
        d = _read(f"page-{n:02d}.json")
        if not d:
            continue
        for p in d.get("pueblos", []):
            cod = _resolve_cod(p, name_to_cod, parish_name_to_cod)
            if cod is None:
                print(f"    [warn] table 3 p{n}: pueblo {p.get('name')!r} not matched")
                continue
            stats = p.get("stats")
            if isinstance(stats, dict):
                for ms, bands in stats.items():
                    if not isinstance(bands, list):
                        continue
                    for ag_idx, band in enumerate(bands[:len(_AGE_ORDER)]):
                        if not isinstance(band, list):
                            continue
                        ag = _AGE_ORDER[ag_idx]
                        for sx_idx, count in enumerate(band[:3]):
                            sx = _SEX_ORDER[sx_idx]
                            key = (cod, ms, ag, sx)
                            if key in seen:
                                continue
                            seen.add(key)
                            rows.append((cod, ms, ag, sx, count))
            else:
                for r in p.get("rows", []):
                    key = (cod, r["marital_status"], r["age_group"], r["sex"])
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append((cod, r["marital_status"], r["age_group"],
                                 r["sex"], r.get("count")))
    if rows:
        con.executemany(
            "INSERT INTO population_by_marital_age_sex VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    print(f"  population_by_marital_age_sex: {len(rows)} rows")


def load_table_4(con: duckdb.DuckDBPyConnection) -> None:
    """Population by occupation."""
    rows = []
    seen: set[tuple] = set()
    parish_name_to_cod = _build_parish_lookup(con)
    name_to_cod = {
        r[0].upper(): r[1]
        for r in con.execute(
            "SELECT name_current, cod FROM pueblos"
        ).fetchall()
    }
    for n in range(25, 28):                  # Table 4 lives on pp. 25-27
        d = _read(f"page-{n:02d}.json")
        if not d:
            continue
        for p in d.get("pueblos", []):
            cod = _resolve_cod(p, name_to_cod, parish_name_to_cod)
            if cod is None:
                print(f"    [warn] table 4 p{n}: pueblo {p.get('name')!r} not matched")
                continue
            counts = p.get("counts", {}) or {}
            notes = p.get("notes")
            for occ, cnt in counts.items():
                if (cod, occ) in seen:
                    continue
                seen.add((cod, occ))
                rows.append((cod, occ, cnt, notes if occ == "total" else None))
    if rows:
        con.executemany(
            "INSERT INTO population_by_occupation VALUES (?, ?, ?, ?)", rows
        )
    print(f"  population_by_occupation: {len(rows)} rows")


def load_table_5(con: duckdb.DuckDBPyConnection) -> None:
    """Religious communities (one row per friars/nuns/other convent)."""
    rows = []
    # Merge per-pueblo blocks across pages (PALMA spans 2 pages).
    pueblos: dict[str, dict] = {}
    for n in range(29, 35):                  # Table 5 lives on pp. 29-34
        d = _read(f"page-{n:02d}.json")
        if not d:
            continue
        for p in d.get("pueblos", []):
            name = (p.get("name") or "").strip().upper()
            if not name:
                continue
            cur = pueblos.setdefault(
                name,
                {"name": name, "total": None, "males": None, "females": None,
                 "friars": [], "nuns": [], "other": [], "notes": None},
            )
            for k in ("total", "males", "females"):
                if p.get(k) is not None:
                    cur[k] = p[k]
            for k in ("friars", "nuns", "other"):
                cur[k].extend(p.get(k) or [])
            if p.get("notes"):
                cur["notes"] = (cur["notes"] or "") + p["notes"]

    name_to_cod = {
        r[0].upper(): r[1]
        for r in con.execute(
            "SELECT name_current, cod FROM pueblos"
        ).fetchall()
    }
    # Manual map for spellings that differ between table 5 and table 1.
    name_aliases = {
        "ALGAYDA": "ALGAIDA",
        "BUÑOLA": "BUROLA",
    }

    rid = 0
    for name, body in pueblos.items():
        cod = name_to_cod.get(name_aliases.get(name, name))
        if cod is None:
            print(f"    [warn] table 5 pueblo {name!r} not matched to a cod")
            continue
        for friars in body["friars"]:
            rid += 1
            rows.append((rid, cod, "friars",
                         friars.get("name"), friars.get("order"),
                         json.dumps({k: v for k, v in friars.items()
                                     if k not in ("name", "order")},
                                    ensure_ascii=False),
                         None))
        for nuns in body["nuns"]:
            rid += 1
            rows.append((rid, cod, "nuns",
                         nuns.get("name"), nuns.get("order"),
                         json.dumps({k: v for k, v in nuns.items()
                                     if k not in ("name", "order")},
                                    ensure_ascii=False),
                         None))
        for other in body["other"]:
            rid += 1
            rows.append((rid, cod, "other",
                         other.get("name"), None,
                         json.dumps({k: v for k, v in other.items()
                                     if k != "name"},
                                    ensure_ascii=False),
                         body.get("notes")))
    if rows:
        con.executemany(
            "INSERT INTO religious_communities VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    print(f"  religious_communities: {len(rows)} rows")


def load_table_6(con: duckdb.DuckDBPyConnection) -> None:
    """Welfare and assistance centres."""
    rows = []
    d = _read("page-35.json")                 # Table 6 is now on p. 35
    if not d:
        print("  welfare_centers: source page-35.json missing, skipped")
        return
    table6 = d
    name_to_cod = {
        r[0].upper(): r[1]
        for r in con.execute(
            "SELECT name_current, cod FROM pueblos"
        ).fetchall()
    }
    rid = 0
    for p in table6.get("pueblos", []):
        name = (p.get("name") or "").strip().upper()
        cod = name_to_cod.get(name)
        if cod is None:
            print(f"    [warn] table 6 pueblo {name!r} not matched")
            continue
        for kind_key, kind in (
            ("hospitals", "hospital"),
            ("hospices", "hospicio"),
            ("foundling_houses", "casa_expositos"),
        ):
            for c in p.get(kind_key, []) or []:
                rid += 1
                centre_name = c.pop("name", None) if isinstance(c, dict) else None
                rows.append((
                    rid, cod, kind, centre_name,
                    p.get("total") if kind == "hospital" and kind_key == "hospitals" and len(p.get("hospitals", [])) == 1 else None,
                    p.get("males") if kind == "hospital" and len(p.get("hospitals", [])) == 1 else None,
                    p.get("females") if kind == "hospital" and len(p.get("hospitals", [])) == 1 else None,
                    json.dumps(c, ensure_ascii=False),
                    c.get("notes") if isinstance(c, dict) else None,
                ))
    if rows:
        con.executemany(
            "INSERT INTO welfare_centers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    print(f"  welfare_centers: {len(rows)} rows")


def load_table_7(con: duckdb.DuckDBPyConnection) -> None:
    """Other centres."""
    rows = []
    d = _read("page-36.json")                 # Table 7 lives on p. 36
    if not d:
        print("  other_centers: source page-36.json missing, skipped")
        return
    table7 = d
    rid = 0
    for e in table7.get("entries", []) or []:
        rid += 1
        rows.append((rid, e.get("cod"), e.get("centro"), e.get("role"), e.get("count")))
    if rows:
        con.executemany(
            "INSERT INTO other_centers VALUES (?, ?, ?, ?, ?)", rows
        )
    print(f"  other_centers: {len(rows)} rows")


def load_comentario(con: duckdb.DuckDBPyConnection) -> None:
    d = _read("page-03.json")
    if not d:
        print("  source_documents: source page-03.json missing, skipped")
        return
    body = d.get("body") or ""
    note = d.get("note_1787") or ""
    if d.get("cities"):
        body += "\n\nCiudades del archipiélago: " + ", ".join(d["cities"]) + "."
    con.execute(
        "INSERT INTO source_documents VALUES (?, ?, ?, ?), (?, ?, ?, ?)",
        [
            "comentario", "Comentario", "5631", body,
            "nota_1787", "Nota del Nomenclátor de 1787 (pueblos de Ibiza, p. 328)",
            "5631", note,
        ],
    )
    print(f"  source_documents: 2 rows")


def _build_parish_lookup(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Map the three Ibiza parish names back to their cod.

    The model emits the parish names in many minor variants ("Pq.
    Santa Eulalia", "Pq. de Sta Eulalia", "DETALLES DE IBIZA - Pq.
    Sta Eulalia", "Pq. S.Pedro y S.Cristóbal"…). We match on the
    distinctive token (San Salvador / Pedro / Eulalia) regardless of
    surrounding decoration.
    """
    out: dict[str, int] = {}
    # The three parishes are deterministic — encode the match keys
    # directly. cod 200 = San Salvador, 201 = S.Pedro y S.Cristóbal,
    # 202 = Santa Eulalia.
    for cod, name in con.execute(
        "SELECT cod, name_current FROM pueblos WHERE parent_cod IS NOT NULL "
        "ORDER BY cod"
    ).fetchall():
        if not name:
            continue
        out[name] = cod
        out[name.replace("Pq. de ", "Pq. ")] = cod
        out[name.replace("Pq. ", "Pq. de ")] = cod
    return out


def _is_parish(name: str) -> int | None:
    """Return the cod of the matching Ibiza parish, or None."""
    if not name:
        return None
    s = name.lower()
    if "san salvador" in s or "s. salvador" in s:
        return 200
    if "pedro" in s and "crist" in s:                    # S.Pedro y S.Cristóbal
        return 201
    if "pedro" in s and "salvador" not in s and "cristóbal" not in s:
        # Bare "Pq. San Pedro" — the model sometimes drops the second
        # half of the compound name.
        return 201
    if "eulalia" in s:
        return 202
    return None


def _truncate_all(con: duckdb.DuckDBPyConnection) -> None:
    """Clear all data tables in dependency-safe order, leaving the
    glossary lookup tables intact."""
    for t in (
        "population_by_housing",
        "population_by_marital_age_sex",
        "population_by_occupation",
        "religious_communities",
        "welfare_centers",
        "other_centers",
        "source_documents",
        "province_summary",
    ):
        con.execute(f"DELETE FROM {t}")
    con.execute("DELETE FROM pueblos WHERE parent_cod IS NOT NULL")
    con.execute("DELETE FROM pueblos")


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    print(f"Loading into {DB_PATH.relative_to(ROOT)}")
    _truncate_all(con)
    load_table_1(con)
    load_table_2(con)
    load_table_3(con)
    load_table_4(con)
    load_table_5(con)
    load_table_6(con)
    load_table_7(con)
    load_comentario(con)
    con.close()


if __name__ == "__main__":
    main()
