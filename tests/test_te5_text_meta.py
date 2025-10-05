"""Tests for the TE5 VA50 text metadata parser."""

from __future__ import annotations

import struct
from typing import List, Tuple

import pytest

from mapsys.parser.te5_text_meta import (
    FLAG_TEXT_FRAME,
    FLAG_TRUE_TYPE_FONT,
    Te5Header,
    Te5TextMeta,
    parse_te5,
)


def _build_te5_bytes(records: List[Tuple]) -> bytes:
    # Header: signature, unk u8, 6 x u32
    header = struct.pack("<4sB6I", b"VA50", 7, 1, 2, 3, 4, 5, 6)

    # Coord record struct mirrors module: <BIBBBffddfffIB
    rec_fmt = struct.Struct("<BIBBBffddfffIB")
    body = b"".join(rec_fmt.pack(*r) for r in records)
    return header + body


def test_parse_te5_header_and_no_records() -> None:
    data = _build_te5_bytes(records=[])
    header, items = parse_te5(data)

    assert isinstance(header, Te5Header)
    assert header.signature == b"VA50"
    assert header.unk == 7
    assert header.pad == (1, 2, 3, 4, 5, 6)
    assert items == []


def test_parse_te5_with_two_records_and_helpers() -> None:
    # Fields per record:
    # first_zero, text_id, layer, font, flags,
    # height, direction, east(f64), north(f64), align_east, align_north, z,
    # offset(u32), length(u8)
    r1 = (
        0,
        1001,
        1,
        2,
        FLAG_TEXT_FRAME | FLAG_TRUE_TYPE_FONT,
        2.5,
        0.0,
        123.0,
        456.0,
        1.0,
        2.0,
        3.0,
        10,
        6,  # includes NUL -> true length 5
    )
    r2 = (
        1,
        1002,
        0,
        0,
        0,
        1.25,
        90.0,
        -1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        1,  # empty string length (only NUL)
    )

    data = _build_te5_bytes(records=[r1, r2])
    header, items = parse_te5(data)

    assert header.signature == b"VA50"
    assert len(items) == 2

    a, b = items
    assert isinstance(a, Te5TextMeta) and isinstance(b, Te5TextMeta)

    # Validate unpacked tuple equality for r1
    assert (
        a.first_zero,
        a.text_id,
        a.layer,
        a.font,
        a.flags,
        a.height,
        a.direction,
        a.east,
        a.north,
        a.align_east,
        a.align_north,
        a.z,
        a.offset,
        a.length,
    ) == r1

    # Helper methods
    assert a.true_length() == 5
    assert a.has_flag(FLAG_TEXT_FRAME)
    assert a.has_flag(FLAG_TRUE_TYPE_FONT)
    assert a.absolute_text_offset(1000) == 1010

    # r2 minimal flags and lengths
    assert b.true_length() == 0
    assert b.has_flag(FLAG_TEXT_FRAME) is False
    assert b.has_flag(FLAG_TRUE_TYPE_FONT) is False


def test_te5_invalid_signature_raises() -> None:
    # Build with wrong signature but valid header length
    bad_header = struct.pack("<4sB6I", b"VA50", 0, 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        parse_te5(bad_header)


def test_te5_buffer_too_small_header_raises() -> None:
    with pytest.raises(ValueError):
        parse_te5(b"\x00\x01")
