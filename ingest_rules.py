"""
ingest_rules.py
===============
Standalone utility script that reads `synthetic_compliance_rules.csv` and
populates a Neo4j graph database with Framework and Rule nodes, connected
by HAS_RULE relationships.

Usage
-----
    python ingest_rules.py

Prerequisites
-------------
    - A local `.env` file with NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD set.
    - `synthetic_compliance_rules.csv` present in the same directory.
    - Packages: neo4j>=5.21.0, python-dotenv>=1.0.1  (see requirements.txt)

Idempotency
-----------
    Cypher MERGE guarantees that re-running the script will update existing
    nodes rather than creating duplicates.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, exceptions as neo4j_exc

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).parent.resolve()
_CSV_PATH = _SCRIPT_DIR / "synthetic_compliance_rules.csv"
_ENV_PATH = _SCRIPT_DIR / ".env"

# ─────────────────────────────────────────────────────────────────────────────
# Cypher Template — Idempotent MERGE
# ─────────────────────────────────────────────────────────────────────────────

_MERGE_QUERY = """
MERGE (f:Framework {id: $framework_id})
ON CREATE SET f.name = $framework_name
ON MATCH  SET f.name = $framework_name

MERGE (r:Rule {id: $rule_id})
ON CREATE SET r.title = $rule_title, r.text = $rule_text
ON MATCH  SET r.title = $rule_title, r.text = $rule_text

MERGE (f)-[:HAS_RULE]->(r)
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _load_env() -> tuple[str, str, str]:
    """Load Neo4j credentials from the .env file.

    Returns
    -------
    tuple[str, str, str]
        (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    Raises
    ------
    SystemExit
        If any required variable is missing.
    """
    load_dotenv(dotenv_path=_ENV_PATH)

    missing: list[str] = []
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    for name, value in [("NEO4J_URI", uri), ("NEO4J_USER", user), ("NEO4J_PASSWORD", password)]:
        if not value:
            missing.append(name)

    if missing:
        print(f"[ERROR] Missing required environment variable(s): {', '.join(missing)}")
        print(f"        Please set them in: {_ENV_PATH}")
        sys.exit(1)

    return uri, user, password  # type: ignore[return-value]


def _load_csv() -> list[dict[str, str]]:
    """Read and validate the compliance rules CSV.

    Returns
    -------
    list[dict[str, str]]
        A list of row dicts, each containing the five expected columns.

    Raises
    ------
    SystemExit
        If the file is missing or required columns are absent.
    """
    required_columns = {"framework_id", "framework_name", "rule_id", "rule_title", "rule_text"}

    if not _CSV_PATH.exists():
        print(f"[ERROR] CSV file not found: {_CSV_PATH}")
        sys.exit(1)

    rows: list[dict[str, str]] = []
    with _CSV_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        # Validate header columns
        if reader.fieldnames is None:
            print("[ERROR] CSV file appears to be empty.")
            sys.exit(1)

        actual_columns = set(reader.fieldnames)
        if not required_columns.issubset(actual_columns):
            missing_cols = required_columns - actual_columns
            print(f"[ERROR] CSV is missing required columns: {missing_cols}")
            sys.exit(1)

        for row in reader:
            # Skip blank/trailing rows
            if not any(row.values()):
                continue
            rows.append(row)

    print(f"[INFO]  Loaded {len(rows)} rule(s) from: {_CSV_PATH.name}")
    return rows


def _ingest(uri: str, user: str, password: str, rows: list[dict[str, str]]) -> None:
    """Connect to Neo4j and execute MERGE for every CSV row.

    Parameters
    ----------
    uri : str
        Neo4j Bolt/HTTP URI (e.g. ``bolt://localhost:7687``).
    user : str
        Neo4j username.
    password : str
        Neo4j password.
    rows : list[dict[str, str]]
        Parsed CSV rows produced by :func:`_load_csv`.
    """
    print(f"[INFO]  Connecting to Neo4j at {uri} …")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        # Verify connectivity before processing rows
        driver.verify_connectivity()
    except neo4j_exc.AuthError as exc:
        print(f"[ERROR] Authentication failed: {exc}")
        sys.exit(1)
    except neo4j_exc.ServiceUnavailable as exc:
        print(f"[ERROR] Neo4j is unreachable at {uri}: {exc}")
        sys.exit(1)

    success = 0
    failed = 0

    with driver.session() as session:
        for idx, row in enumerate(rows, start=1):
            params = {
                "framework_id":   row["framework_id"].strip(),
                "framework_name": row["framework_name"].strip(),
                "rule_id":        row["rule_id"].strip(),
                "rule_title":     row["rule_title"].strip(),
                "rule_text":      row["rule_text"].strip(),
            }

            try:
                session.run(_MERGE_QUERY, **params)
                success += 1
                print(
                    f"  [{idx:>3}/{len(rows)}] ✔  Merged Rule '{params['rule_id']}' "
                    f"→ Framework '{params['framework_id']}'"
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(
                    f"  [{idx:>3}/{len(rows)}] ✘  Failed for rule_id='{params['rule_id']}': {exc}"
                )

    driver.close()

    print()
    print("─" * 60)
    print(f"[DONE]  Ingestion complete — {success} succeeded, {failed} failed.")
    print("─" * 60)

    if failed:
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Compliance Rules — Neo4j Ingestion Utility")
    print("=" * 60)

    neo4j_uri, neo4j_user, neo4j_password = _load_env()
    csv_rows = _load_csv()
    _ingest(neo4j_uri, neo4j_user, neo4j_password, csv_rows)
