"""CLI tests for the directory-wide XLSX export command."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from mapsys.cli import cli


class _DummyContent:
    def __init__(self) -> None:
        self.points: list[object] = []
        self.texts: list[object] = []
        self.t_meta: list[object] = []
        self.p_meta: list[object] = []
        self.v_offsets: list[int] = []
        self.p_layers: list[object] = []
        self.pr5: object | None = None


def test_cli_to_xlsx_dir_exports_all(tmp_path: Path, monkeypatch: Any) -> None:
    """`to-xlsx-dir` writes XLSX files for each .pr5 and prints a summary."""

    # Two projects: one in root, one in a subdir
    (tmp_path / "a.pr5").write_bytes(b"a")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.pr5").write_bytes(b"b")

    def _fake_create(_: Path) -> Any:
        return _DummyContent()

    import mapsys.parser.content as mcontent

    monkeypatch.setattr(mcontent.Content, "create", _fake_create)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "to-xlsx-dir",
            str(tmp_path),
            "--max-depth",
            "1",
        ],
    )

    assert result.exit_code == 0
    # Summary contains numbers of processed directories and exported files
    assert "exported" in result.output
    # Both XLSX should be created next to each .pr5
    assert (tmp_path / "a.xlsx").exists()
    assert (sub / "b.xlsx").exists()
