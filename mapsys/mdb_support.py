"""
Extract all tables from an Access .mdb/.accdb into simple Python structures.

Usage:
    data = extract_access_db("path/to/db.mdb")
    # data is a dict: { table_name: [ {col: val, ...}, ... ], ... }

    # If you want JSON:
    import json
    print(json.dumps(data, ensure_ascii=False, indent=2))
"""

from __future__ import annotations
import logging
import os
import json
import sys
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List
import pyodbc  # type: ignore


logger = logging.getLogger(__name__)


def _convert_value(v: Any) -> Any:
    """Make values JSON/pure-Python friendly."""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        # Use float for simplicity; switch to str(v) if you want exact
        # precision.
        return float(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        # Represent binary as hex (readable, lossless)
        return bytes(v).hex()
    return v


def _extract_with_pyodbc(db_path: str) -> Dict[str, List[Dict[str, Any]]]:

    # Common Access driver name on Windows. On macOS/Linux you may have a
    # unixODBC driver installed.
    drivers = [
        "{Microsoft Access Driver (*.mdb, *.accdb)}",
        "{Microsoft Access Driver (*.mdb)}",
        "{MDBToolsODBC}",  # some unixODBC setups
    ]

    last_err = None
    conn = None
    for drv in drivers:
        conn_str = f"DRIVER={drv};DBQ={db_path};"
        try:
            conn = pyodbc.connect(conn_str, autocommit=True)
            break
        except Exception as e:
            last_err = e

    if conn is None:
        raise RuntimeError(
            f"Could not connect via ODBC. "
            f"Tried drivers {drivers}. Last error: {last_err}"
        )

    data: Dict[str, List[Dict[str, Any]]] = {}
    try:
        cur = conn.cursor()

        # List user tables; avoid MSys* system tables
        tables = []
        for row in cur.tables(tableType="TABLE"):
            name = row.table_name
            if not name.startswith("MSys"):
                tables.append(name)

        # Fallback: some drivers don’t return table types reliably
        if not tables:
            cur.execute(
                "SELECT name FROM MSysObjects WHERE Type=1 AND Flags=0")
            tables = [r[0]
                      for r in cur.fetchall() if not r[0].startswith("MSys")]

        for tbl in tables:
            try:
                cur.execute(f"SELECT * FROM [{tbl}]")
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                data[tbl] = [
                    {col: _convert_value(val)
                     for col, val in zip(columns, row)}
                    for row in rows
                ]
            except Exception as e:
                # Don’t die on one bad table; record the error instead
                data[f"{tbl}__ERROR"] = [{"error": str(e)}]
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return data


# -------------------- Public API --------------------


def extract_access_db(db_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract all non-system tables to {table: [row dicts]}.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)

    try:
        return _extract_with_pyodbc(db_path)
    except Exception as e:
        logger.warning("pyodbc failed: %s", e)
        raise

# -------------------- Example CLI --------------------


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Dump Access DB to JSON")
    ap.add_argument("db", help="Path to .mdb or .accdb")
    ap.add_argument("-o", "--out", help="Write JSON to this path")
    args = ap.parse_args()

    result = extract_access_db(args.db)
    js = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(js)
        print(f"Wrote {args.out}")
    else:
        print(js)
