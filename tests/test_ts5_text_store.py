"""Tests for the TS5 VA50 text store parser."""

from __future__ import annotations

import struct
from typing import List

import pytest

from mapsys.parser.ts5_text_store import Ts5Header, parse_ts5


def _build_ts5_bytes(strings: List[bytes]) -> bytes:
    # Header: signature, 4x u32, pad u8
    header = struct.pack("<4s4IB", b"VA50", 1, 2, 3, 4, 0)

    # Payload: NUL-terminated byte strings
    payload = b"".join(s + b"\x00" for s in strings)

    return header + payload


def test_parse_ts5_header_and_no_strings() -> None:
    data = _build_ts5_bytes(strings=[])
    header, texts = parse_ts5(data)

    assert isinstance(header, Ts5Header)
    assert header.signature == b"VA50"
    assert header.int1 == (1, 2, 3, 4)
    assert header.pad == 0
    assert texts == []


def test_parse_ts5_with_strings_and_offsets() -> None:
    parts = [b"hello", b"", b"world"]
    data = _build_ts5_bytes(strings=parts)

    header, texts = parse_ts5(data)
    assert header.signature == b"VA50"

    # Expect three entries: "hello", "", "world"
    assert [t.text for t in texts] == ["hello", "", "world"]

    # Offsets are relative to the start of the string block
    # "hello" at 0, empty at 6 (len("hello") + 1), "world" at 7
    assert [t.offset for t in texts] == [0, 6, 7]


def test_parse_ts5_invalid_signature_raises() -> None:
    # Build a header with an invalid signature and no payload
    bad_header = struct.pack("<4s4IB", b"VA50", 0, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        parse_ts5(bad_header)


def test_parse_ts5_too_small_buffer_raises() -> None:
    # Smaller than the header size
    with pytest.raises(ValueError):
        parse_ts5(b"\x00\x01")
