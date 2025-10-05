"""Tests for the AL5 VA50 parser."""

from __future__ import annotations

import logging
import struct
from typing import Iterable, Tuple

import pytest

from mapsys.parser.al5_poly_layer import Al5Data, Al5Header, parse_al5


def _build_al5_bytes(
    *,
    signature: bytes = b"VA50",
    header_ints: Tuple[int, int, int, int] = (1, 2, 3, 4),
    pad: int = 0,
    records: Iterable[Tuple[int, int, int]] = (),
    trailing: bytes = b"",
) -> bytes:
    """Construct a minimal AL5 file as bytes for tests."""

    # Header: 4s, 4x u32, u8
    header = struct.pack(
        "<4s4IB",
        signature,
        header_ints[0],
        header_ints[1],
        header_ints[2],
        header_ints[3],
        pad,
    )

    # Data records: 3 bytes each
    rec_fmt = struct.Struct("<BBB")
    rec_bytes = b"".join(rec_fmt.pack(*r) for r in records)

    return header + rec_bytes + trailing


class TestParseHeader:
    def test_parse_al5_vs50_header_and_no_records(self) -> None:
        data = _build_al5_bytes(signature=b"VA50", records=())
        header, items = parse_al5(data)

        assert isinstance(header, Al5Header)
        assert header.signature == b"VA50"
        assert header.int1 == (1, 2, 3, 4)
        assert header.pad == 0
        assert items == []

    def test_parse_al5_va50_header_two_records(self) -> None:
        rec1 = (5, 0, 1)
        rec2 = (6, 4, 0)
        data = _build_al5_bytes(signature=b"VA50", records=[rec1, rec2])

        header, items = parse_al5(data)
        assert header.signature == b"VA50"
        assert len(items) == 2

        a, b = items
        assert isinstance(a, Al5Data) and isinstance(b, Al5Data)
        assert (a.layer, a.second, a.third) == rec1
        assert (b.layer, b.second, b.third) == rec2


class TestParseData:
    def test_parse_al5_trailing_bytes_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        data = _build_al5_bytes(records=[(1, 2, 3)], trailing=b"\x00")

        with caplog.at_level(
            logging.DEBUG, logger="mapsys.parser.al5_poly_layer"
        ):
            _, items = parse_al5(data)

        assert len(items) == 1

        messages = "\n".join(r.getMessage() for r in caplog.records)
        assert "Trailing 1 byte(s) after AL5 data table" in messages

    def test_parse_al5_invalid_signature_raises(self) -> None:
        data = _build_al5_bytes(signature=b"ABCD")
        with pytest.raises(ValueError):
            parse_al5(data)

    def test_parse_al5_short_header_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_al5(b"\x00\x01\x02")


# End of file
