"""Tests for ``mapsys.parser.mdb_support``.

These tests mock the ODBC layer to avoid relying on an actual Access driver
or database file. They validate success paths, fallback enumeration, per-table
error handling, and connection failure behavior.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, List, Sequence

import pytest

from mapsys.parser import mdb_support as ms


class FakeCursor:
    """Simple fake ODBC cursor.

    The instance is configured with a mapping of table -> rows and can
    optionally raise when selecting from certain tables.
    """

    def __init__(
        self,
        tables_rows: dict[str, list[tuple[Any, ...]]],
        *,
        raise_on: set[str] | None = None,
    ) -> None:
        self._tables_rows = tables_rows
        self._raise_on = raise_on or set()
        self._last_sql: str | None = None
        self.description: Sequence[Sequence[Any]] | None = None

    # noqa: N803 - keep param name consistent with pyodbc API
    def tables(self, tableType: str = "TABLE") -> List[SimpleNamespace]:
        del tableType
        # include a system table and one user table
        return [
            SimpleNamespace(table_name="MSysObjects"),
            SimpleNamespace(table_name="Users"),
        ]

    def execute(self, sql: str) -> None:
        self._last_sql = sql
        # Handle fallback query for table listing
        if sql.strip().startswith("SELECT name FROM MSysObjects"):
            self.description = [("name",)]
            return

        # Handle SELECT * FROM [Table]
        if sql.strip().startswith("SELECT * FROM [") and sql.strip().endswith(
            "]"
        ):
            table = sql.strip()[len("SELECT * FROM [") : -1]
            if table in self._raise_on:
                raise RuntimeError(f"boom on {table}")

            # Set a minimal description; only d[0] is used by the code
            rows = self._tables_rows.get(table, [])
            if rows:
                num_cols = len(rows[0])
                self.description = [(f"col{i}",) for i in range(num_cols)]
            else:
                self.description = [("col0",)]
            return

        # Any other statement is not expected in these tests
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchall(self) -> list[Any]:
        assert self._last_sql is not None
        if self._last_sql.strip().startswith("SELECT name FROM MSysObjects"):
            # One system table and two user tables, one filtered later
            return [("MSysX",), ("Users",), ("Orders",)]

        if self._last_sql.strip().startswith("SELECT * FROM ["):
            table = self._last_sql.strip()[len("SELECT * FROM [") : -1]
            return list(self._tables_rows.get(table, []))

        raise AssertionError(f"Unexpected SQL for fetchall: {self._last_sql}")


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def close(self) -> None:
        self.closed = True


class FakeCursorUsersAndBad(FakeCursor):
    """Cursor that lists both Users and Bad tables.

    Used to simulate a per-table error during row fetching for one table.
    """

    # noqa: N803 - keep param name consistent with pyodbc API
    def tables(self, tableType: str = "TABLE") -> List[SimpleNamespace]:
        del tableType
        return [
            SimpleNamespace(table_name="Users"),
            SimpleNamespace(table_name="Bad"),
        ]


def test_convert_value_covers_datetime_decimal_and_bytes() -> None:
    dt = datetime(2024, 1, 2, 3, 4, 5)
    d = date(2024, 1, 2)
    dec = Decimal("12.34")
    bs = b"\x01\xab"

    assert ms._convert_value(dt) == "2024-01-02T03:04:05"
    assert ms._convert_value(d) == "2024-01-02"
    # Decimal conversion uses float for simplicity
    assert ms._convert_value(dec) == pytest.approx(12.34)
    # Binary is hex-encoded
    assert ms._convert_value(bs) == "01ab"


def test_extract_access_db_file_not_found(tmp_path: Any) -> None:
    missing = tmp_path / "nope.mdb"
    with pytest.raises(FileNotFoundError):
        ms.extract_access_db(str(missing))


def test_extract_access_db_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    # Prepare fake DB and driver
    rows = {
        "Users": [(1, "Alice"), (2, "Bob")],
    }
    fake_cursor = FakeCursor(rows)
    fake_conn = FakeConnection(fake_cursor)

    def fake_connect(conn_str: str, autocommit: bool) -> FakeConnection:  # noqa: ARG001
        assert autocommit is True
        return fake_conn

    monkeypatch.setattr(ms, "pyodbc", SimpleNamespace(connect=fake_connect))

    db_path = tmp_path / "ok.mdb"
    db_path.write_text("dummy")

    data = ms.extract_access_db(str(db_path))
    assert "Users" in data
    assert data["Users"] == [
        {"col0": 1, "col1": "Alice"},
        {"col0": 2, "col1": "Bob"},
    ]


def test_extract_access_db_fallback_table_enumeration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    # Force .tables() to still return entries but also test the fallback.
    rows: dict[str, list[tuple[Any, ...]]] = {
        "Users": [(1, "Alice")],
        "Orders": [(10,)],
    }
    fake_cursor = FakeCursor(rows)
    fake_conn = FakeConnection(fake_cursor)

    def fake_connect(conn_str: str, autocommit: bool) -> FakeConnection:  # noqa: ARG001
        return fake_conn

    monkeypatch.setattr(ms, "pyodbc", SimpleNamespace(connect=fake_connect))

    db_path = tmp_path / "ok2.mdb"
    db_path.write_text("dummy")

    data = ms.extract_access_db(str(db_path))
    # System tables are filtered; user tables present
    assert set(data.keys()) == {"Users", "Orders"}


def test_extract_access_db_records_per_table_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    rows: dict[str, list[tuple[Any, ...]]] = {
        "Users": [(1, "Alice")],
    }
    fake_cursor = FakeCursorUsersAndBad(rows, raise_on={"Bad"})

    fake_conn = FakeConnection(fake_cursor)

    def fake_connect(conn_str: str, autocommit: bool) -> FakeConnection:  # noqa: ARG001
        return fake_conn

    monkeypatch.setattr(ms, "pyodbc", SimpleNamespace(connect=fake_connect))

    db_path = tmp_path / "ok3.mdb"
    db_path.write_text("dummy")

    data = ms.extract_access_db(str(db_path))
    assert "Users" in data
    assert "Bad__ERROR" in data
    assert isinstance(data["Bad__ERROR"][0].get("error"), str)


def test_extract_access_db_all_drivers_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    def failing_connect(conn_str: str, autocommit: bool) -> Any:  # noqa: ARG001
        raise RuntimeError("no driver")

    monkeypatch.setattr(ms, "pyodbc", SimpleNamespace(connect=failing_connect))

    db_path = tmp_path / "bad.mdb"
    db_path.write_text("dummy")

    with pytest.raises(RuntimeError):
        ms.extract_access_db(str(db_path))
