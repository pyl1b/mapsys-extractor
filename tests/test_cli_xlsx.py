"""CLI tests for XLSX export commands.

These tests exercise ``mapsys to-xlsx`` against a fabricated minimal project
directory. They avoid end-to-end parsing by mocking ``Content.create`` to
return a minimal in-memory object, and check that the command writes the
expected XLSX file and prints "Done".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from mapsys.cli import cli


class _DummyContent:
    """Minimal duck-typed content for XLSX export used by the CLI test."""

    def __init__(self) -> None:
        # Data tables
        self.points: list[object] = []
        self.texts: list[object] = []
        self.t_meta: list[object] = []
        self.p_meta: list[object] = []
        self.v_offsets: list[int] = []
        self.p_layers: list[object] = []

        # Optional PR5 structure
        self.pr5: object | None = None


def test_cli_to_xlsx_creates_file(tmp_path: Path, monkeypatch: Any) -> None:
    """``to-xlsx`` writes an XLSX next to the main file and prints Done."""

    # Arrange: directory with a dummy .pr5 file
    prj = tmp_path / "proj.pr5"
    prj.write_bytes(b"dummy")

    # Mock Content.create to avoid reading actual MapSys files
    def _fake_create(_: Path) -> Any:
        return _DummyContent()

    monkeypatch.setenv("mapsys_LOG_FILE", "")
    import mapsys.parser.content as mcontent

    monkeypatch.setattr(mcontent.Content, "create", _fake_create)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "to-xlsx",
            str(tmp_path),
            "--xlsx",
            str(tmp_path / "out.xlsx"),
        ],
    )
    assert result.exit_code == 0
    assert "Done" in result.output
    assert (tmp_path / "out.xlsx").exists()
