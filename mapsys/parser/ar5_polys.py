"""VS50/AR5 polylines index parser.

This module defines typed data structures for the VS50-based AR5 format and
provides a parser that reads the header and a sequence of ``Data`` records
until EOF, as described by the given ImHex pattern.

ImHex reference (little-endian):

- Header:
  - signature: char[4] == b"VS50"
  - int1: u32[4]
  - pad: u8
- File pad: u8[9]
- Data (repeated until EOF):
  - line_id: u32
  - line_nr: u32
  - unk1: u32  (always 0)
  - vertex_offset: u32  (offset into the ASS table)
  - vertex_count: u16   (number of points in the poly)
  - lay_rec: u32        The index of the layer info record in AL5 table.
  - layer_count: u8     (observed correlations with UI)
  - unk6: u32           (mostly unique; some duplicates)
  - unk7: u8            (0, 1, 2)
  - unk8: u8            (0, 1)
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


# Binary struct formats (little-endian, tightly packed, no implicit padding)
_AR5_HEADER_STRUCT = struct.Struct("<4s4I")
_AR5_DATA_STRUCT = struct.Struct("<BIIIIHIBIB")


@dataclass(frozen=True)
class Ar5Header:
    """AR5 file header.

    Attributes:
        signature: File signature, expected to be ``b"VS50"``.
        int1: Four 32-bit unsigned integers (purpose unknown).
        pad: Single 8-bit value (usually 0).
    """

    signature: bytes
    int1: Tuple[int, int, int, int]


@dataclass(frozen=True)
class Ar5Data:
    """One AR5 polyline index entry.

    Attributes:
        unk8: Small categorical value (0, 1).
        line_id: Identifier of the line.
        line_nr: Line number.
        unk1: Always 0 in observed files.
        vertex_offset: Offset inside the ASS table.
        vertex_count: Number of points in this polyline.
        lay_rec: Value unique across the file.
        layer_count: Layer counter/amount; correlates with UI observations.
        unk6: Mostly unique; some values may repeat.
        unk7: Small categorical value (0, 1, 2).
    """

    unk8: int
    line_id: int
    line_nr: int
    unk1: int
    vertex_offset: int
    vertex_count: int
    lay_rec: int
    layer_count: int
    unk6: int
    unk7: int


def _parse_ar5_header(data: bytes, offset: int = 0) -> Tuple[Ar5Header, int]:
    """Parse the AR5 header starting at ``offset``.

    Args:
        data: Entire file as bytes.
        offset: Offset where the header starts.

    Returns:
        Tuple of the parsed ``Ar5Header`` and the new offset after the header
        plus the file-level 9-byte pad that follows it in AR5 files.

    Raises:
        ValueError: If the buffer is too small or the signature is invalid.
    """

    # Ensure we have enough bytes for the header and subsequent 9-byte pad.
    minimum = _AR5_HEADER_STRUCT.size + 9
    if len(data) - offset < minimum:
        raise ValueError("Buffer too small for AR5 header + pad")

    # Unpack header fields.
    signature, i1, i2, i3, i4 = _AR5_HEADER_STRUCT.unpack_from(data, offset)

    # Validate signature.
    if signature != b"VA50":
        raise ValueError("Invalid AR5 signature: %r" % (signature,))

    # Build header dataclass.
    header = Ar5Header(signature=signature, int1=(i1, i2, i3, i4))

    # Skip header and fixed 9-byte pad following the header.
    new_off = offset + _AR5_HEADER_STRUCT.size + 9
    return header, new_off


def _parse_ar5_data_until_eof(
    data: bytes, offset: int
) -> Tuple[List[Ar5Data], int]:
    """Parse AR5 ``Data`` records from ``offset`` until EOF.

    Args:
        data: Entire file as bytes.
        offset: Starting offset of the first ``Data`` record.

    Returns:
        Tuple of (list of ``Ar5Data``, final offset).
    """

    # Prepare container and track sizes for the loop.
    items: List[Ar5Data] = []
    size = _AR5_DATA_STRUCT.size
    data_len = len(data)

    # Read as many whole records as possible.
    while offset + size <= data_len:
        (
            unk8,
            line_id,
            line_nr,
            unk1,
            vertex_offset,
            vertex_count,
            lay_rec,
            layer_count,
            unk6,
            unk7,
        ) = _AR5_DATA_STRUCT.unpack_from(data, offset)

        # Append immutable record.
        items.append(
            Ar5Data(
                line_id=line_id,
                line_nr=line_nr,
                unk1=unk1,
                vertex_offset=vertex_offset,
                vertex_count=vertex_count,
                lay_rec=lay_rec,
                layer_count=layer_count,
                unk6=unk6,
                unk7=unk7,
                unk8=unk8,
            )
        )

        # Advance to next record.
        offset += size

    # If trailing bytes remain that don't form a full record, log for insight.
    trailing = data_len - offset
    if trailing:
        logger.debug("Trailing %d byte(s) after AR5 data table", trailing)

    return items, offset


def parse_ar5(data: bytes) -> Tuple[Ar5Header, List[Ar5Data]]:
    """Parse an AR5 VS50 file from bytes.

    Args:
        data: File content as bytes.

    Returns:
        Tuple of (``Ar5Header``, list of ``Ar5Data`` records).
    """

    # Parse header and file-level pad.
    header, offset = _parse_ar5_header(data, 0)

    # Parse all data records until EOF.
    items, _ = _parse_ar5_data_until_eof(data, offset)

    return header, items


__all__ = ["Ar5Header", "Ar5Data", "parse_ar5"]
