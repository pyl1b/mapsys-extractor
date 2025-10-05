"""Tests for mapsys.parser.content.Content aggregation helpers.

The tests build minimal binary buffers for AL5, AR5 and TS5 to verify that
``Content.create`` discovers files, parses them and exposes helpers like
``text_by_offset`` and ``get_poly_layer`` correctly.
"""

from __future__ import annotations

import struct
from pathlib import Path

from mapsys.parser.content import Content


def _build_al5(layer_values: list[tuple[int, int, int]]) -> bytes:
    """Create a minimal AL5 file with the given 3-byte records."""

    header = struct.pack("<4s4IB", b"VA50", 0, 0, 0, 0, 0)
    data = b"".join(struct.pack("<BBB", a, b, c) for a, b, c in layer_values)
    return header + data


def _build_ar5(
    *,
    lay_rec: int,
    vertex_count: int = 1,
    layer_count: int = 1,
) -> bytes:
    """Create a minimal AR5 file with a single data record."""

    header = struct.pack("<4s4I", b"VA50", 0, 0, 0, 0)
    pad9 = b"\x00" * 9
    record = struct.pack(
        "<BIIIIHIBIB",
        0,  # unk8
        1,  # line_id
        2,  # line_nr
        0,  # unk1
        0,  # vertex_offset
        vertex_count,  # vertex_count
        lay_rec,  # lay_rec
        layer_count,  # layer_count
        123,  # unk6
        0,  # unk7
    )
    return header + pad9 + record


def _build_ts5(strings: list[str]) -> tuple[bytes, list[int]]:
    """Create a minimal TS5 file and report each string's start offset."""

    header = struct.pack("<4s4IB", b"VA50", 0, 0, 0, 0, 0)
    offsets: list[int] = []
    block = b""
    current = 0
    for s in strings:
        offsets.append(current)
        raw = s.encode("windows-1250") + b"\x00"
        block += raw
        current += len(raw)
    return header + block, offsets


class TestContent:
    def test_create_and_helpers(self, tmp_path: Path) -> None:
        # Prepare minimal AL5, AR5, TS5 companions for a base name "MAIN".
        al5_bytes = _build_al5([(5, 0, 0), (7, 0, 0)])
        ar5_bytes = _build_ar5(lay_rec=1)
        ts5_bytes, ts5_offsets = _build_ts5(["hello", "world"])  # noqa: F841

        (tmp_path / "MAIN.AL5").write_bytes(al5_bytes)
        (tmp_path / "MAIN.AR5").write_bytes(ar5_bytes)
        ts5_path = tmp_path / "MAIN.TS5"
        ts5_path.write_bytes(ts5_bytes)

        # Create Content using the TS5 file as the entry point.
        content = Content.create(ts5_path)
        assert content is not None

        # Verify AL5 and AR5 interaction via get_poly_layer.
        assert len(content.p_layers) == 2
        assert len(content.p_meta) == 1
        assert content.get_poly_layer(content.p_meta[0]) == 7

        # Verify text_by_offset builds the cache and returns expected values.
        assert content.text_by_offset(0) == "hello"
        # Second string starts after "hello\x00" (6 bytes from block start).
        assert content.text_by_offset(6) == "world"
        # Unknown offset returns None.
        assert content.text_by_offset(9999) is None
