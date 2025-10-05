"""Extract all user tables from an Access database into plain Python data.

This module connects to a Microsoft Access ``.mdb``/``.accdb`` file using
ODBC and extracts each non-system table as a list of row dictionaries. The
result can be easily serialized to JSON or used directly in Python code.

Usage:
    data = extract_access_db("path/to/db.mdb")
    # ``data`` is { table_name: [ {column: value, ...}, ... ], ... }

    # If you want JSON:
    import json
    print(json.dumps(data, ensure_ascii=False, indent=2))
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List

import pyodbc  # type: ignore

logger = logging.getLogger(__name__)


# -------------------- Composed types --------------------


# Note: we keep row dictionaries flexible (``Dict[str, Any]``) because table
# schemas vary and error rows may include an ``"error"`` field.
RowDict = Dict[str, Any]
TableData = List[RowDict]
ExtractedDb = Dict[str, TableData]


def _convert_value(v: Any) -> Any:
    """Make a value JSON- and pure-Python-friendly.

    The conversion rules are conservative and readable:

    - ``datetime``/``date`` -> ISO 8601 string
    - ``Decimal`` -> ``float`` (for simplicity)
    - binary-like (``bytes``, ``bytearray``, ``memoryview``) -> hex string

    Args:
        v: Input value as returned by the database driver.

    Returns:
        The converted value suitable for JSON serialization.
    """
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


def _extract_with_pyodbc(db_path: str) -> ExtractedDb:
    """Extract tables using ``pyodbc``.

    Tries a small list of common Access ODBC drivers and connects using the
    first one that succeeds. System tables (``MSys*``) are skipped.

    Args:
        db_path: Path to the ``.mdb``/``.accdb`` file.

    Returns:
        A mapping of table name to list of row dictionaries.

    Throws:
        RuntimeError: If a connection cannot be established with any known
            driver.
    """

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

    data: ExtractedDb = {}
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
                "SELECT name FROM MSysObjects WHERE Type=1 AND Flags=0"
            )
            tables = [
                r[0] for r in cur.fetchall() if not r[0].startswith("MSys")
            ]

        for tbl in tables:
            try:
                cur.execute(f"SELECT * FROM [{tbl}]")
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                data[tbl] = [
                    {
                        col: _convert_value(val)
                        for col, val in zip(columns, row)
                    }
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


def extract_access_db(db_path: str) -> ExtractedDb:
    """Extract all non-system tables to ``{table: [row dicts]}``.

    This is the public API and includes a simple existence check for the
    database file path. Internally it uses ``pyodbc`` extraction.

    Args:
        db_path: Path to the ``.mdb``/``.accdb`` file.

    Returns:
        A mapping of table name to list of row dictionaries.

    Throws:
        FileNotFoundError: If ``db_path`` does not exist.
        RuntimeError: If connecting via ODBC fails.
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
