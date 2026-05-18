"""Initialise the DuckDB database from db/schema.sql.

Idempotent: the schema uses CREATE TABLE IF NOT EXISTS / CREATE INDEX
IF NOT EXISTS, so re-running this script is a no-op after the first.

Usage:
    python scripts/init_db.py
"""

from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema.sql"
DB_PATH = ROOT / "db" / "floridablanca.duckdb"


def main() -> None:
    schema_sql = SCHEMA.read_text(encoding="utf-8")
    con = duckdb.connect(str(DB_PATH))
    con.execute(schema_sql)
    # Migration: pre-existing DBs predate the name_official column.
    cols = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'current_municipalities'"
    ).fetchall()}
    if "name_official" not in cols:
        con.execute("ALTER TABLE current_municipalities ADD COLUMN name_official TEXT")
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    con.close()
    print(f"Initialised {DB_PATH.relative_to(ROOT)} with {len(tables)} tables:")
    for (t,) in tables:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
