"""[EXPERIMENTAL] Extract Table 4 (occupations) using local Tesseract.

This is a fallback for when the Anthropic API is unavailable. Quality
is ~70% cell accuracy on Tables 4-7 of the INE 1986 facsimile (the
typewriter face confuses dotted leaders, drifts column positions
across pages, and frequently mis-OCRs "TOTAL" as "e A" or "po PAR").
For a publishable dataset use scripts/extract_pages.py with Claude
Sonnet via the API.

Strategy:
1. Run Tesseract in TSV mode (positional output) over each half-page
   crop.
2. Group tokens into lines by y-coordinate.
3. Anchor the 10 numeric column centres on the CURAS row, which is
   the first profession row and always reads as 10 clean "1" digits.
4. For every subsequent profession row, assign each numeric token to
   the nearest column centre.
5. Classify the row label (leftmost tokens) into a snake_case
   profession key. The TOTAL row is identified structurally as the
   last row with N values, since Tesseract frequently mis-OCRs
   "TOTAL" as "e A", "po PAR" or "TOM".

The output JSON matches the shape produced by extract_pages.py so
load_all.py picks it up unchanged.

Usage:
    python scripts/ocr_table4.py [--page 25]   # default: all 3 pages
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CROPS = ROOT / "data" / "pages" / "crops"
OUT   = ROOT / "data" / "extracted"


PAGE_GRIDS = {
    25: {"top":    [1,  2,  3,  5,  6,  8, 17, 19, 22, 23],
         "bottom": [24, 28, 31, 32, 33, 36, 37, 39, 43, 44]},
    26: {"top":    [49, 52, 53, 54, 57, 59, 61, 63, 64, 66],
         "bottom": [67, 69, 70, 72, 73, 77, 78, 79, 80, 83]},
    27: {"top":    [84, 85, 88, 89, 90, 91, 94, 95, 96, 97],
         "bottom": [98, 99, 100, 101, 102, 109, 111, 200, 201, 202]},
}

FOOTNOTES = {
    2:  "* 23 Sacerdotes / 1 Tonsurado",
    3:  "(*) El OM dice haber 750 Presidiarios no incluidos en las tablas.",
    28: "* 3 Vicarios",
    31: "* 4 Expósitos",
}


LABEL_MAP = [
    (r"\bCURAS",                          "curas"),
    (r"\bBENEFI[CO]IADOS",                "beneficiados"),
    (r"\bTENIENTES.{0,4}CURA",            "tenientes_de_cura"),
    (r"\bSACRISTANES",                    "sacristanes"),
    (r"\b[AMÁ]COLITOS",                   "acolitos"),
    (r"\bORDEN.{0,4}T.{0,4}PATRIMONIO",   "ordenados_titulo_patrimonio"),
    (r"\bORDEN.{0,4}DE.{0,4}MENORES",     "ordenados_de_menores"),
    (r"\bHIDALGOS",                       "hidalgos"),
    (r"\bABOGADOS",                       "abogados"),
    (r"\bESCRIBANOS",                     "escribanos"),
    (r"\bESTUDIANTES",                    "estudiantes"),
    (r"\bLABRADORES",                     "labradores"),
    (r"\bJORNALEROS",                     "jornaleros"),
    (r"\bCOMERCIANTES",                   "comerciantes"),
    (r"\bFABRICANTES",                    "fabricantes"),
    (r"\bARTESANOS",                      "artesanos"),
    (r"\bCRIADOS",                        "criados"),
    (r"\bEMPL.{0,4}SUELDO",               "empleados_sueldo_real"),
    (r"\b[PF]UERO.{0,4}MILITAR",          "fuero_militar"),
    (r"\bDEP.{0,4}INQUISI",               "dep_inquisicion"),
    (r"\bS[IÍ]NDICOS",                    "sindicos_ord_relig"),
    (r"\bDEPEND.{0,4}CRUZADA",            "depend_cruzada"),
    (r"\bDEMANDANTES",                    "demandantes"),
    (r"\bO[MTÑ]ROS",                      "otros"),
    (r"\bMENORES",                        "menores_sin_profesion"),
]


def classify(label: str) -> str | None:
    for pat, key in LABEL_MAP:
        if re.search(pat, label):
            return key
    return None


def parse_int(tok: str) -> int | None:
    tok = tok.strip().rstrip(".,").rstrip("*")
    tok = tok.replace(".", "").replace(",", "")
    if tok in ("", "-", "—", "–", "_", "~"):
        return None
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    return None


def tsv_tokens(img: Path) -> list[dict]:
    out = subprocess.run(
        ["tesseract", str(img), "-", "-l", "spa", "--psm", "6", "tsv"],
        check=True, capture_output=True, text=True,
    ).stdout
    toks = []
    for r in csv.DictReader(out.splitlines(), delimiter="\t"):
        t = (r.get("text") or "").strip()
        if not t:
            continue
        toks.append({"x": int(r["left"]), "y": int(r["top"]),
                     "w": int(r["width"]), "h": int(r["height"]),
                     "text": t})
    return toks


def group_lines(toks: list[dict], y_tol: int = 14) -> list[list[dict]]:
    """Cluster tokens into lines by y centre."""
    toks = sorted(toks, key=lambda t: (t["y"], t["x"]))
    lines: list[list[dict]] = []
    cur: list[dict] = []
    cur_y: float | None = None
    for t in toks:
        cy = t["y"] + t["h"] / 2
        if cur_y is None or abs(cy - cur_y) <= y_tol:
            cur.append(t)
            # Weighted moving average so the line's y centre adapts
            # as we accrete tokens.
            cur_y = ((cur_y or cy) * (len(cur) - 1) + cy) / max(len(cur), 1)
        else:
            lines.append(cur)
            cur = [t]
            cur_y = cy
    if cur:
        lines.append(cur)
    return lines


LABEL_X_CUTOFF = 540


def split_line(line: list[dict]) -> tuple[str, list[dict]]:
    label_toks = [t for t in line if t["x"] < LABEL_X_CUTOFF]
    value_toks = [t for t in line if t["x"] >= LABEL_X_CUTOFF]
    label = " ".join(t["text"] for t in label_toks)
    label = re.sub(r"\.{2,}", " ", label)
    label = re.sub(r"\s+", " ", label).upper().strip(" .-_")
    return label, sorted(value_toks, key=lambda t: t["x"])


def find_column_centers(lines: list[list[dict]]) -> list[float] | None:
    """The CURAS row reads as ten clean '1' tokens. Use its x-centres
    as the canonical column positions for the grid."""
    for line in lines:
        label, vals = split_line(line)
        if classify(label) == "curas":
            cx = [t["x"] + t["w"] / 2 for t in vals if parse_int(t["text"]) is not None]
            if len(cx) >= 8:                  # tolerate 1-2 missed
                if len(cx) == 10:
                    return cx
                # Re-derive missing positions by assuming uniform spacing.
                cx.sort()
                step = (cx[-1] - cx[0]) / (len(cx) - 1)
                start = cx[0]
                return [start + i * step for i in range(10)]
    return None


def assign(value_toks: list[dict], centers: list[float],
           tol: float) -> list[str | None]:
    """Map value tokens to the 10 columns by nearest x-centre."""
    out: list[str | None] = [None] * 10
    for t in value_toks:
        cx = t["x"] + t["w"] / 2
        # Closest centre.
        best = min(range(10), key=lambda i: abs(cx - centers[i]))
        if abs(cx - centers[best]) > tol:
            continue
        if out[best] is None:
            out[best] = t["text"]
    return out


def extract_grid(img: Path, cods: list[int]) -> list[dict]:
    lines = group_lines(tsv_tokens(img))
    centers = find_column_centers(lines)
    if not centers:
        return [{"cod": c, "name": "", "has_footnote": False,
                 "notes": None, "counts": {}} for c in cods]
    tol = (centers[1] - centers[0]) * 0.55     # ~half a column width

    out = [{"cod": c, "name": "", "has_footnote": False,
            "notes": None, "counts": {}} for c in cods]

    last_unlabelled: list[str | None] | None = None
    for line in lines:
        label, vals = split_line(line)
        cells = assign(vals, centers, tol)
        key = classify(label)
        if key is None:
            # Likely the TOTAL or COD row; remember.
            n_filled = sum(1 for c in cells
                           if c is not None and parse_int(c) is not None)
            if n_filled >= 6:
                last_unlabelled = cells
            continue
        for i, raw in enumerate(cells):
            out[i]["counts"][key] = parse_int(raw) if raw else None

    if last_unlabelled is not None and "total" not in out[0]["counts"]:
        for i, raw in enumerate(last_unlabelled):
            out[i]["counts"]["total"] = parse_int(raw) if raw else None

    return out


def populate_names(grids: list[list[dict]]) -> None:
    try:
        import duckdb
        con = duckdb.connect(str(ROOT / "db" / "floridablanca.duckdb"), read_only=True)
        name_by_cod = dict(con.execute(
            "SELECT cod, name_current FROM pueblos"
        ).fetchall())
        con.close()
    except Exception:
        name_by_cod = {}
    for g in grids:
        for p in g:
            p["name"] = name_by_cod.get(p["cod"], f"COD {p['cod']}")
            if p["cod"] in FOOTNOTES:
                p["notes"] = FOOTNOTES[p["cod"]]
                p["has_footnote"] = True


def main():
    import sys
    pages = (25, 26, 27)
    if "--page" in sys.argv:
        pages = (int(sys.argv[sys.argv.index("--page") + 1]),)
    for n in pages:
        top = extract_grid(CROPS / f"page-{n:02d}-top.jpg", PAGE_GRIDS[n]["top"])
        bot = extract_grid(CROPS / f"page-{n:02d}-bot.jpg", PAGE_GRIDS[n]["bottom"])
        populate_names([top, bot])
        (OUT / f"page-{n:02d}.json").write_text(
            json.dumps({"pueblos": top + bot,
                        "_meta": {"page": n, "kind": "table_4_via_tesseract",
                                  "model": "tesseract+spa"}},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        ok_tot = sum(1 for p in (top + bot)
                     if p["counts"].get("total") is not None)
        ok_lab = sum(1 for p in (top + bot)
                     if p["counts"].get("labradores") is not None)
        print(f"  page {n:02d}: TOTAL {ok_tot}/{len(top)+len(bot)} · "
              f"LABRADORES {ok_lab}/{len(top)+len(bot)}")


if __name__ == "__main__":
    main()
