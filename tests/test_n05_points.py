"""Tests for the NO5 VA50 parser."""

from __future__ import annotations

import struct

import pytest

from mapsys.parser.n05_points import (
    No5Coord,
    No5Header,
    parse_no5,
)


def _build_no5_bytes(
    records: list[
        tuple[
            int,
            int,
            int,
            int,
            float,
            float,
            float,
            int,
            int,
        ]
    ],
):
    # Header: signature, 6x u32, pad u8
    header = struct.pack("<4s6IB", b"VA50", 1, 2, 3, 4, 5, 6, 0)

    # Coord records: <BIBIddfIB
    rec_fmt = struct.Struct("<BIBIddfIB")
    rec_bytes = b"".join(rec_fmt.pack(*r) for r in records)

    return header + rec_bytes


def test_parse_no5_header_and_no_records() -> None:
    data = _build_no5_bytes(records=[])
    header, items = parse_no5(data)

    assert isinstance(header, No5Header)
    assert header.signature == b"VA50"
    assert header.int1 == (1, 2, 3, 4, 5, 6)
    assert header.pad1 == 0
    assert items == []


def test_parse_no5_with_two_records() -> None:
    r1 = (
        16,  # type (node)
        1001,  # id_nr
        2,  # layer
        10,  # pt_nr
        123.5,  # east (f64)
        456.25,  # north (f64)
        7.75,  # z (f32)
        9999,  # uniq
        1,  # connexion
    )
    r2 = (
        0,
        1002,
        3,
        11,
        -1.0,
        0.0,
        0.5,
        10000,
        0,
    )
    data = _build_no5_bytes(records=[r1, r2])

    header, items = parse_no5(data)
    assert header.signature == b"VA50"
    assert len(items) == 2

    a, b = items
    assert isinstance(a, No5Coord) and isinstance(b, No5Coord)

    assert (
        a.type,
        a.id_nr,
        a.layer,
        a.pt_nr,
        a.east,
        a.north,
        a.z,
        a.uniq,
        a.connexion,
    ) == r1

    assert (
        b.type,
        b.id_nr,
        b.layer,
        b.pt_nr,
        b.east,
        b.north,
        b.z,
        b.uniq,
        b.connexion,
    ) == r2


def test_parse_no5_invalid_signature_raises() -> None:
    # Corrupt the signature to "VA50"
    bad_header = struct.pack("<4s6IB", b"VA50", 0, 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        parse_no5(bad_header)


def test_parse_no5_buffer_too_small_header() -> None:
    # Less than header size
    with pytest.raises(ValueError):
        parse_no5(b"VS")
