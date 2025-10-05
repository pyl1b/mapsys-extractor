"""NO5/VS50 binary structures and parser.

This module defines typed data structures for the VS50 (NO5) binary format
and provides a parser that can read these structures from a ``bytes`` object.

The layout is inspired by the ImHex pattern shown in the codebase:

Header (little-endian):
- signature: 4 bytes, must be ``b"VS50"``
- int1: 6 x ``u32`` values (purpose unknown)
- pad1: 1 x ``u8`` (usually 0)

Coord record (repeated until EOF, little-endian):
- type: ``u8`` (0 break point, 16 node, 5 special/unknown)
- id_nr: ``u32`` (database ID)
- layer: ``u8`` (0-based layer index)
- pt_nr: ``u32`` (user-editable point number)
- east: ``f64``
- north: ``f64``
- z: ``f32``
- uniq: ``u32`` (usually unique)
- connexion: ``u8`` (observed values 0, 1, 2)
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


# Binary struct formats (little-endian)
_HEADER_STRUCT = struct.Struct("<4s6IB")
_COORD_STRUCT = struct.Struct("<BIBIddfIB")


@dataclass(frozen=True)
class No5Header:
    """VS50/NO5 file header.

    Attributes:
        signature: File signature, expected to be ``b"VS50"``.
        int1: Six 32-bit unsigned integers with unknown purpose.
        pad1: Single 8-bit value (usually 0).
    """

    signature: bytes
    int1: Tuple[int, int, int, int, int, int]
    pad1: int


@dataclass(frozen=True)
class No5Coord:
    """Single coordinate record from a VS50/NO5 file.

    Attributes:
        type: Record type (0 break point, 16 node, 5 special/unknown).
        id_nr: Database ID number.
        layer: Zero-based layer number.
        pt_nr: User-editable point number.
        east: X coordinate (meters).
        north: Y coordinate (meters).
        z: Elevation (meters).
        uniq: Usually unique identifier.
        connexion: The number of lines that use that point. For isolated
            points it is 0.
    """

    type: int
    id_nr: int
    layer: int
    pt_nr: int
    east: float
    north: float
    z: float
    uniq: int
    connexion: int


def _parse_header(data: bytes, offset: int = 0) -> Tuple[No5Header, int]:
    """Parse the NO5 header starting at ``offset``.

    Args:
        data: Entire file as bytes.
        offset: Offset where the header starts.

    Returns:
        Tuple of the parsed ``No5Header`` and the new offset after the header.

    Raises:
        ValueError: If the buffer is too small or the signature is invalid.
    """

    # Ensure enough bytes for the header.
    if len(data) - offset < _HEADER_STRUCT.size:
        raise ValueError("Buffer too small for NO5 header")

    # Unpack fields using the predefined struct.
    signature, i1, i2, i3, i4, i5, i6, pad1 = _HEADER_STRUCT.unpack_from(
        data, offset
    )

    # Validate the signature.
    if signature != b"VA50":
        raise ValueError("Invalid NO5 signature: %r" % (signature,))

    # Build the header dataclass and return with new offset.
    header = No5Header(
        signature=signature,
        int1=(i1, i2, i3, i4, i5, i6),
        pad1=pad1,
    )
    return header, offset + _HEADER_STRUCT.size


def _parse_coords(data: bytes, offset: int) -> Tuple[List[No5Coord], int]:
    """Parse coordinate records until EOF.

    Args:
        data: Entire file as bytes.
        offset: Offset to the first coord record.

    Returns:
        Tuple of list of ``No5Coord`` and the final offset (EOF).
    """

    # Prepare container for parsed coordinates.
    coords: List[No5Coord] = []

    # Iterate while enough bytes remain for one full record.
    size = _COORD_STRUCT.size
    data_len = len(data)
    while offset + size <= data_len:
        (
            type_value,
            id_nr,
            layer,
            pt_nr,
            east,
            north,
            z,
            uniq,
            connexion,
        ) = _COORD_STRUCT.unpack_from(data, offset)

        # Create immutable record and append to results.
        coords.append(
            No5Coord(
                type=type_value,
                id_nr=id_nr,
                layer=layer,
                pt_nr=pt_nr,
                east=east,
                north=north,
                z=z,
                uniq=uniq,
                connexion=connexion,
            )
        )

        # Advance to next record.
        offset += size

    # Warn if trailing bytes exist that don't form a full record.
    trailing = data_len - offset
    if trailing:
        logger.debug("Trailing %d bytes after NO5 coords", trailing)

    return coords, offset


def parse_no5(data: bytes) -> Tuple[No5Header, List[No5Coord]]:
    """Parse a VS50/NO5 file from bytes.

    Args:
        data: File content as bytes.

    Returns:
        Tuple of (``No5Header``, list of ``No5Coord``).
    """

    # Parse the header first.
    header, offset = _parse_header(data, 0)

    # Parse all coordinate records until EOF.
    coords, _ = _parse_coords(data, offset)

    # Return structured result.
    return header, coords


__all__ = ["No5Header", "No5Coord", "parse_no5"]
