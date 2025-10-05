"""AL5 (VS50) poly-layer table parser.

This module defines a minimal parser for the AL5 VS50 format described by the
ImHex layout. The file stores a simple header followed by 3-byte records
until EOF.

Header (little-endian):
- signature: 4 bytes, expected to be b"VS50" (observed files use b"VA50")
- int1: 4 x u32
- pad: 1 x u8

Data record (repeated until EOF):
- layer: u8
- second: u8 (observed 0, 4, 8)
- third: u8 (observed 0 or 1)
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


_AL5_HEADER_STRUCT = struct.Struct("<4s4IB")
_AL5_DATA_STRUCT = struct.Struct("<BBB")


@dataclass(frozen=True)
class Al5Header:
    """AL5 file header."""

    signature: bytes
    int1: Tuple[int, int, int, int]
    pad: int


@dataclass(frozen=True)
class Al5Data:
    """Single AL5 data entry."""

    layer: int
    second: int
    third: int


def _parse_al5_header(data: bytes, offset: int = 0) -> Tuple[Al5Header, int]:
    """Parse the AL5 header starting at ``offset``.

    Validates the signature. While the ImHex pattern shows "VS50", other
    files in this project use and accept "VA50". We therefore accept either
    value for robustness.
    """

    if len(data) - offset < _AL5_HEADER_STRUCT.size:
        raise ValueError("Buffer too small for AL5 header")

    signature, i1, i2, i3, i4, pad = _AL5_HEADER_STRUCT.unpack_from(
        data, offset
    )

    if signature not in (b"VA50", b"VS50"):
        raise ValueError("Invalid AL5 signature: %r" % (signature,))

    header = Al5Header(signature=signature, int1=(i1, i2, i3, i4), pad=pad)
    return header, offset + _AL5_HEADER_STRUCT.size


def _parse_al5_data_until_eof(
    data: bytes, offset: int
) -> Tuple[List[Al5Data], int]:
    """Parse AL5 Data records from ``offset`` until EOF."""

    items: List[Al5Data] = []
    size = _AL5_DATA_STRUCT.size
    end = len(data)

    while offset + size <= end:
        layer, second, third = _AL5_DATA_STRUCT.unpack_from(data, offset)
        items.append(Al5Data(layer=layer, second=second, third=third))
        offset += size

    trailing = end - offset
    if trailing:
        logger.debug("Trailing %d byte(s) after AL5 data table", trailing)

    return items, offset


def parse_al5(data: bytes) -> Tuple[Al5Header, List[Al5Data]]:
    """Parse an AL5 VS50 file from bytes."""

    header, offset = _parse_al5_header(data, 0)
    items, _ = _parse_al5_data_until_eof(data, offset)
    return header, items


__all__ = ["Al5Header", "Al5Data", "parse_al5"]
