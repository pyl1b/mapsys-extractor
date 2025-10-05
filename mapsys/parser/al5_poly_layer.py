"""AL5 (VA50) poly-layer table parser.

This module provides a small, well-typed parser for the AL5 VA50 binary format
as described by the ImHex layout. Files contain a fixed-size header followed by
3-byte data records until EOF.

Header (little-endian):
- signature: 4 bytes, expected to be b"VA50" (observed files use b"VA50")
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


# Composed types used throughout this module.

Int4 = Tuple[int, int, int, int]
Al5DataList = List["Al5Data"]


@dataclass(frozen=True)
class Al5Header:
    """AL5 file header.

    Attributes:
      signature: Raw 4-byte signature. Expected b"VA50".
      int1: Tuple of four unsigned 32-bit integers from the header.
      pad: Single padding byte from the header.
    """

    signature: bytes
    int1: Int4
    pad: int


@dataclass(frozen=True)
class Al5Data:
    """Single AL5 data entry.

    Attributes:
      layer: Layer identifier.
      second: Second byte value (observed 0, 4, 8).
      third: Third byte value (observed 0 or 1).
    """

    layer: int
    second: int
    third: int


def _parse_al5_header(data: bytes, offset: int = 0) -> Tuple[Al5Header, int]:
    """Parse the AL5 header starting at the given offset.

    Validates the signature.

    Args:
      data: Binary buffer that contains the AL5 content.
      offset: Byte offset where the header starts.

    Returns:
      A tuple ``(header, new_offset)`` where ``header`` is the parsed
      :class:`Al5Header` and ``new_offset`` is the byte position immediately
      after the header.

    Throws:
      ValueError: If the buffer is too small to contain a full header.
      ValueError: If the signature is not one of the accepted values.
    """

    # Ensure there is enough data for the fixed-size header.
    if len(data) - offset < _AL5_HEADER_STRUCT.size:
        raise ValueError("Buffer too small for AL5 header")

    # Unpack the header fields from the binary buffer.
    signature, i1, i2, i3, i4, pad = _AL5_HEADER_STRUCT.unpack_from(
        data, offset
    )

    # Validate the signature for known acceptable values.
    if signature != b"VA50":
        raise ValueError("Invalid AL5 signature: %r" % (signature,))

    # Build the strongly-typed header object and advance the offset.
    header = Al5Header(signature=signature, int1=(i1, i2, i3, i4), pad=pad)
    return header, offset + _AL5_HEADER_STRUCT.size


def _parse_al5_data_until_eof(
    data: bytes, offset: int
) -> Tuple[Al5DataList, int]:
    """Parse AL5 data records starting at the given offset until EOF.

    Args:
      data: Binary buffer that contains the AL5 content.
      offset: Byte offset where the data records start.

    Returns:
      A tuple ``(items, new_offset)`` where ``items`` is the list of parsed
      :class:`Al5Data` entries and ``new_offset`` is the byte position after
      the last full record.
    """

    # Prepare iteration bounds for fixed-size records.
    items: Al5DataList = []
    size = _AL5_DATA_STRUCT.size
    end = len(data)

    # Iterate over full-sized records only; stop when a partial record remains.
    while offset + size <= end:
        layer, second, third = _AL5_DATA_STRUCT.unpack_from(data, offset)
        items.append(Al5Data(layer=layer, second=second, third=third))
        offset += size

    # If bytes remain, they are trailing; log for observability and return.
    trailing = end - offset
    if trailing:
        logger.debug("Trailing %d byte(s) after AL5 data table", trailing)

    return items, offset


def parse_al5(data: bytes) -> Tuple[Al5Header, Al5DataList]:
    """Parse an AL5 VA50 file from a bytes buffer.

    Args:
      data: Binary buffer that contains the AL5 content.

    Returns:
      A tuple ``(header, items)`` where ``header`` is the parsed header and
      ``items`` is the list of parsed data entries.

    Throws:
      ValueError: If the header is invalid or truncated.
    """

    # Parse the file header, then parse records until the end of the buffer.
    header, offset = _parse_al5_header(data, 0)
    items, _ = _parse_al5_data_until_eof(data, offset)
    return header, items


__all__ = ["Al5Header", "Al5Data", "parse_al5"]
