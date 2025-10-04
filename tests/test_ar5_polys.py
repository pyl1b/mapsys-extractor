"""Tests for the AR5 VS50 parser."""

from __future__ import annotations

import struct

from mapsys.ar5_polys import Ar5Data, Ar5Header, parse_ar5


def _build_ar5_bytes(records: list[tuple[int, ...]]) -> bytes:
    # Header: signature, 4x u32, pad u8
    header = struct.pack("<4s4IB", b"VS50", 1, 2, 3, 4, 0)

    # File-level 9-byte pad
    pad9 = b"\x00" * 9

    # Data records: <IIIIHIBIBB
    rec_fmt = struct.Struct("<IIIIHIBIBB")
    rec_bytes = b"".join(rec_fmt.pack(*r) for r in records)

    return header + pad9 + rec_bytes


def test_parse_ar5_header_and_no_records() -> None:
    data = _build_ar5_bytes(records=[])
    header, items = parse_ar5(data)

    assert isinstance(header, Ar5Header)
    assert header.signature == b"VS50"
    assert header.int1 == (1, 2, 3, 4)
    assert header.pad == 0
    assert items == []


def test_parse_ar5_with_two_records() -> None:
    r1 = (
        10,  # line_id
        20,  # line_nr
        0,  # unk1
        100,  # vertex_offset
        7,  # vertex_count (u16)
        111,  # uniq_b
        2,  # layer_count (u8)
        222,  # unk6
        1,  # unk7 (u8)
        0,  # unk8 (u8)
    )
    r2 = (
        11,
        21,
        0,
        104,
        9,
        112,
        3,
        223,
        2,
        1,
    )
    data = _build_ar5_bytes(records=[r1, r2])

    header, items = parse_ar5(data)
    assert header.signature == b"VS50"
    assert len(items) == 2

    a, b = items
    assert isinstance(a, Ar5Data) and isinstance(b, Ar5Data)

    assert (
        a.line_id,
        a.line_nr,
        a.unk1,
        a.vertex_offset,
        a.vertex_count,
        a.uniq_b,
        a.layer_count,
        a.unk6,
        a.unk7,
        a.unk8,
    ) == r1

    assert (
        b.line_id,
        b.line_nr,
        b.unk1,
        b.vertex_offset,
        b.vertex_count,
        b.uniq_b,
        b.layer_count,
        b.unk6,
        b.unk7,
        b.unk8,
    ) == r2


# End of file
