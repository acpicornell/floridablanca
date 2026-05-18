"""Flatten the DuckDB tables into web/data.json for the static site.

The output is a single JSON file consumed by web/app.js. Shape:

    {
      "meta":           { generated_at, source, totals: {...} },
      "lookups":        { categories, authorities, jurisdictions,
                          districts, current_municipalities },
      "pueblos":        [ { cod, name_current, ..., population: {...},
                            religious: [...], welfare: [...],
                            other: [...] }, ... ],
      "comentario":     "...",
      "nota_1787":      "..."
    }

Usage:
    python scripts/export_web_data.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "floridablanca.duckdb"
OUT_PATH = ROOT / "web" / "data.json"


def export() -> dict:
    con = duckdb.connect(str(DB_PATH), read_only=True)

    cats = dict(con.execute("SELECT code, label FROM category_codes").fetchall())
    auths = dict(con.execute("SELECT code, label FROM authority_codes").fetchall())
    juris = dict(con.execute("SELECT code, label FROM jurisdiction_codes").fetchall())
    dists = dict(con.execute("SELECT code, label FROM district_codes").fetchall())
    munis = dict(con.execute(
        "SELECT code, name FROM current_municipalities ORDER BY code"
    ).fetchall())

    pueblos_rows = con.execute(
        "SELECT cod, name_current, name_1787, category_code, authority_code, "
        "       jurisdiction_code, intendancy, district_code, "
        "       current_municipality_code, manuscript_page, ine_photogram, "
        "       in_table_2, in_table_3, in_table_4, in_table_5, in_table_6, "
        "       in_table_7, observations, parent_cod "
        "FROM pueblos ORDER BY cod"
    ).fetchall()

    pueblos: list[dict] = []
    by_cod: dict[int, dict] = {}
    for r in pueblos_rows:
        (cod, name_cur, name_1787, cat, auth, jur, intd, dist, mcod, mpage,
         photo, t2, t3, t4, t5, t6, t7, obs, parent) = r
        p = {
            "cod": cod,
            "name_current": name_cur,
            "name_1787": name_1787,
            "category": cat,
            "category_label": cats.get(cat),
            "authority": auth,
            "authority_label": auths.get(auth),
            "jurisdiction": jur,
            "jurisdiction_label": juris.get(jur),
            "intendancy": intd,
            "district": dist,
            "district_label": dists.get(dist),
            "current_municipality_code": mcod,
            "current_municipality_name": munis.get(mcod),
            "manuscript_page": mpage,
            "ine_photogram": photo,
            "in_tables": {
                "2": t2, "3": t3, "4": t4, "5": t5, "6": t6, "7": t7,
            },
            "observations": obs,
            "parent_cod": parent,
            "population": None,
            "religious": [],
            "welfare": [],
            "other_centres": [],
        }
        pueblos.append(p)
        by_cod[cod] = p

    # Table 2: housing.
    housing_rollup: dict[int, dict] = defaultdict(lambda: {
        "total": {}, "family": {},
        "collective_religious": {}, "collective_other": {},
    })
    for cod, htype, sex, count in con.execute(
        "SELECT pueblo_cod, housing_type, sex, count FROM population_by_housing"
    ).fetchall():
        housing_rollup[cod][htype][sex] = count

    # Table 3: marital × age × sex.
    marital_rollup: dict[int, dict] = defaultdict(lambda: defaultdict(dict))
    for cod, ms, ag, sex, count in con.execute(
        "SELECT pueblo_cod, marital_status, age_group, sex, count "
        "FROM population_by_marital_age_sex"
    ).fetchall():
        marital_rollup[cod].setdefault(ms, {}).setdefault(ag, {})[sex] = count

    # Table 4: occupations.
    occ_rollup: dict[int, dict] = defaultdict(dict)
    notes_rollup: dict[int, str] = {}
    for cod, occ, count, note in con.execute(
        "SELECT pueblo_cod, occupation, count, note FROM population_by_occupation"
    ).fetchall():
        occ_rollup[cod][occ] = count
        if note:
            notes_rollup[cod] = note

    for cod, p in by_cod.items():
        if cod in housing_rollup or cod in marital_rollup or cod in occ_rollup:
            p["population"] = {
                "housing":    housing_rollup.get(cod, {}),
                "marital":    marital_rollup.get(cod, {}),
                "occupation": occ_rollup.get(cod, {}),
                "occupation_notes": notes_rollup.get(cod),
            }

    # Table 5: religious communities.
    for rid, cod, ctype, name, order, members, notes in con.execute(
        "SELECT id, pueblo_cod, community_type, name, religious_order, "
        "       members, notes "
        "FROM religious_communities ORDER BY id"
    ).fetchall():
        p = by_cod.get(cod)
        if not p:
            continue
        p["religious"].append({
            "id": rid,
            "type": ctype,
            "name": name,
            "order": order,
            "members": json.loads(members) if members else {},
            "notes": notes,
        })

    # Table 6: welfare.
    for rid, cod, ctype, name, total, males, females, roles, notes in con.execute(
        "SELECT id, pueblo_cod, center_type, name, total, males, females, "
        "       roles, notes FROM welfare_centers ORDER BY id"
    ).fetchall():
        p = by_cod.get(cod)
        if not p:
            continue
        p["welfare"].append({
            "id": rid,
            "type": ctype,
            "name": name,
            "total": total,
            "males": males,
            "females": females,
            "roles": json.loads(roles) if roles else {},
            "notes": notes,
        })

    # Table 7: other.
    other_grouped: dict[int, dict[str, dict]] = defaultdict(dict)
    for rid, cod, name, role, count in con.execute(
        "SELECT id, pueblo_cod, name, role, count FROM other_centers "
        "ORDER BY id"
    ).fetchall():
        if cod is None or name is None:
            continue
        centre = other_grouped[cod].setdefault(name, {"name": name, "roles": []})
        centre["roles"].append({"role": role, "count": count})
    for cod, group in other_grouped.items():
        p = by_cod.get(cod)
        if p:
            p["other_centres"] = list(group.values())

    # Source documents.
    docs = {k: v for k, _t, _p, v in con.execute(
        "SELECT section_key, title, printed_pages, body FROM source_documents"
    ).fetchall()}

    # Province totals from the housing table — the printed roll-up row
    # we extracted alongside the pueblos is not loaded into the DB
    # (Table 2 stores only cod-bearing rows), so we recompute here.
    total_pop = sum(
        (housing_rollup[cod]["total"].get("T") or 0) for cod in housing_rollup
    )
    sum_total_t = con.execute(
        "SELECT COALESCE(SUM(count), 0) FROM population_by_housing "
        "WHERE housing_type='total' AND sex='T'"
    ).fetchone()[0]
    pueblos_with_data = con.execute(
        "SELECT COUNT(*) FROM pueblos WHERE in_table_3 = TRUE"
    ).fetchone()[0]

    by_district = dict(con.execute(
        "SELECT p.district_code, COUNT(*) AS n "
        "FROM pueblos p WHERE p.parent_cod IS NULL "
        "GROUP BY p.district_code ORDER BY p.district_code"
    ).fetchall())

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": (
                "INE (1986) — Censo de 1787, Floridablanca. Tomo VI: "
                "Provincia de Baleares. Madrid: INE."
            ),
            "totals": {
                "pueblos": len([p for p in pueblos if not p["parent_cod"]]),
                "pueblos_with_table_3": pueblos_with_data,
                "total_population": int(sum_total_t),
                "by_district": by_district,
            },
        },
        "lookups": {
            "categories":     [{"code": k, "label": v} for k, v in cats.items()],
            "authorities":    [{"code": k, "label": v} for k, v in auths.items()],
            "jurisdictions":  [{"code": k, "label": v} for k, v in juris.items()],
            "districts":      [{"code": k, "label": v} for k, v in dists.items()],
            "current_municipalities":
                [{"code": k, "name": v} for k, v in munis.items()],
        },
        "pueblos": pueblos,
        "comentario": docs.get("comentario", ""),
        "nota_1787":  docs.get("nota_1787", ""),
    }


def main() -> None:
    payload = export()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    n_pueblos = len(payload["pueblos"])
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"Wrote {OUT_PATH.relative_to(ROOT)} "
          f"({n_pueblos} pueblos, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
