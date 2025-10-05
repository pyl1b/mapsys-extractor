"""Tests for the AR5 VA50 parser."""

from __future__ import annotations

import struct

import pytest

from mapsys.parser.ar5_polys import Ar5Data, Ar5Header, parse_ar5


def _build_ar5_bytes(records: list[tuple[int, ...]]) -> bytes:
    # Header: signature + 4x u32 (no header pad byte in parser)
    header = struct.pack("<4s4I", b"VA50", 1, 2, 3, 4)

    # File-level 9-byte pad
    pad9 = b"\x00" * 9

    # Data records follow parser struct: <BIIIIHIBIB
    rec_fmt = struct.Struct("<BIIIIHIBIB")
    rec_bytes = b"".join(rec_fmt.pack(*r) for r in records)

    return header + pad9 + rec_bytes


def test_parse_ar5_header_and_no_records() -> None:
    data = _build_ar5_bytes(records=[])
    header, items = parse_ar5(data)

    assert isinstance(header, Ar5Header)
    assert header.signature == b"VA50"
    assert header.int1 == (1, 2, 3, 4)
    assert items == []


def test_parse_ar5_with_two_records() -> None:
    # (unk8, line_id, line_nr, unk1, vertex_offset, vertex_count, lay_rec,
    #  layer_count, unk6, unk7)
    r1 = (0, 10, 20, 0, 100, 7, 111, 2, 222, 1)
    r2 = (1, 11, 21, 0, 104, 9, 112, 3, 223, 2)

    data = _build_ar5_bytes(records=[r1, r2])

    header, items = parse_ar5(data)
    assert header.signature == b"VA50"
    assert len(items) == 2

    a, b = items
    assert isinstance(a, Ar5Data) and isinstance(b, Ar5Data)

    assert (
        a.unk8,
        a.line_id,
        a.line_nr,
        a.unk1,
        a.vertex_offset,
        a.vertex_count,
        a.lay_rec,
        a.layer_count,
        a.unk6,
        a.unk7,
    ) == r1

    assert (
        b.unk8,
        b.line_id,
        b.line_nr,
        b.unk1,
        b.vertex_offset,
        b.vertex_count,
        b.lay_rec,
        b.layer_count,
        b.unk6,
        b.unk7,
    ) == r2


def test_invalid_signature_raises() -> None:
    # Build header with bad signature, keep enough bytes for header+pad
    header = struct.pack("<4s4I", b"BAD!", 1, 2, 3, 4)
    data = header + (b"\x00" * 9)
    with pytest.raises(ValueError):
        parse_ar5(data)


def test_buffer_too_small_raises() -> None:
    with pytest.raises(ValueError):
        parse_ar5(b"\x00\x01\x02")
