"""AS5/VS50 offsets table parser.

The AS5 table stores only 32-bit offsets (little-endian) pointing into the
vertices list used by polylines. There is no per-record structure beyond the
offset values.

Layout (little-endian, per observed ImHex pattern):

- Header: ``<4s5IB``
  - signature: ``b"VS50"``
  - int1: 5 x ``u32`` (unknown purpose)
  - pad: 1 x ``u8``

- Data: sequence of ``u32`` values until EOF

"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


_AS5_HEADER_STRUCT = struct.Struct("<4s5IB")
_U32_STRUCT = struct.Struct("<I")


@dataclass(frozen=True)
class As5Header:
    """AS5 file header.

    Attributes:
        signature: File signature, expected to be ``b"VS50"``.
        int1: Five 32-bit unsigned integers with unknown purpose.
        pad: Single 8-bit value (usually 0).
    """

    signature: bytes
    int1: Tuple[int, int, int, int, int]
    pad: int


def _parse_as5_header(data: bytes, offset: int = 0) -> Tuple[As5Header, int]:
    """Parse the AS5 header starting at ``offset``.

    Returns the parsed header and the new offset after the header.
    """

    if len(data) - offset < _AS5_HEADER_STRUCT.size:
        raise ValueError("Buffer too small for AS5 header")

    signature, i1, i2, i3, i4, i5, pad = _AS5_HEADER_STRUCT.unpack_from(
        data, offset
    )

    if signature != b"VA50":
        raise ValueError("Invalid AS5 signature: %r" % (signature,))

    header = As5Header(signature=signature, int1=(i1, i2, i3, i4, i5), pad=pad)
    return header, offset + _AS5_HEADER_STRUCT.size


def _parse_offsets(data: bytes, offset: int) -> Tuple[List[int], int]:
    """Parse ``u32`` offsets until EOF, starting at ``offset``.

    Returns the list of offsets and the final offset.
    """

    offsets: List[int] = []
    size = _U32_STRUCT.size
    data_len = len(data)

    while offset + size <= data_len:
        (value,) = _U32_STRUCT.unpack_from(data, offset)
        offsets.append(value)
        offset += size

    trailing = data_len - offset
    if trailing:
        logger.debug("Trailing %d byte(s) after AS5 offsets", trailing)

    return offsets, offset


def parse_as5(data: bytes) -> Tuple[As5Header, List[int]]:
    """Parse a VS50/AS5 file from bytes, returning header and offsets list."""

    header, offset = _parse_as5_header(data, 0)
    offsets, _ = _parse_offsets(data, offset)
    return header, offsets


__all__ = ["As5Header", "parse_as5"]
