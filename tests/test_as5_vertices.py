"""Tests for the AS5 VA50 offsets parser."""

from __future__ import annotations

import struct

from mapsys.parser.as5_vertices import (
    As5Header,
    parse_as5,
)


def _build_as5_bytes(
    offset_values: list[int], signature: bytes = b"VA50"
) -> bytes:
    # Header: <4s4IB  -> signature, 4x u32, pad u8
    header = struct.pack("<4s4IB", signature, 1, 2, 3, 4, 0)

    # Offsets: sequence of u32
    offsets_blob = b"".join(struct.pack("<I", v) for v in offset_values)
    return header + offsets_blob


def test_parse_as5_header_and_no_offsets() -> None:
    data = _build_as5_bytes(offset_values=[])
    header, offsets = parse_as5(data)

    assert isinstance(header, As5Header)
    assert header.signature == b"VA50"
    assert header.int1 == (1, 2, 3, 4)
    assert header.pad == 0
    assert offsets == []


def test_parse_as5_with_offsets() -> None:
    values = [0, 4, 8, 100, 65535]
    data = _build_as5_bytes(offset_values=values)

    header, offsets = parse_as5(data)
    assert header.signature == b"VA50"
    assert offsets == values


def test_parse_as5_accepts_VA50_signature() -> None:
    values = [1, 2, 3]
    data = _build_as5_bytes(offset_values=values, signature=b"VA50")
    header, offsets = parse_as5(data)

    assert header.signature == b"VA50"
    assert header.int1 == (1, 2, 3, 4)
    assert header.pad == 0
    assert offsets == values


def test_parse_as5_rejects_invalid_signature() -> None:
    data = _build_as5_bytes(offset_values=[1], signature=b"BAD!")
    try:
        parse_as5(data)
    except ValueError as exc:
        assert "Invalid AS5 signature" in str(exc)
    else:
        assert False, "Expected ValueError for invalid signature"
    # End of file
