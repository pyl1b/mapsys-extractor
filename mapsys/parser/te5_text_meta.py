"""TE5/VA50 text metadata structures and parser.

This module defines typed data structures for the VA50 (TE5) text metadata
format and provides a parser to read these structures from a ``bytes``
buffer.

The layout follows the ImHex pattern provided by the user:

Header (little-endian):
- signature: 4 bytes, must be ``b"VA50"``
- unk: 1 x ``u8`` (purpose unknown)
- pad: 6 x ``u32`` (padding, unknown values)

Coord record (repeated until EOF, little-endian):
- first_zero: ``u8`` (observed sometimes 1; may indicate deleted/invalid)
- text_id: ``u32``
- layer: ``u8`` (0-based, add 1 to map to UI layer)
- font: ``u8`` (0-based, add 1 to map to UI font)
- flags: ``u8`` (bit flags; 0x02 Text Frame, 0x20 TrueType Font)
- height: ``f32``
- direction: ``f32``
- east: ``f64``
- north: ``f64``
- align_east: ``f32``
- align_north: ``f32``
- z: ``f32``
- offset: ``u32`` (relative to the first text, not file start)
- length: ``u8`` (includes the terminating NUL; true length is ``length-1``)
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


#
# Binary struct formats (little-endian)
#
_TE5_HEADER_STRUCT = struct.Struct("<4sB6I")

#
# Order matches the ImHex Coord struct exactly.
# Size is 49 bytes without padding under the standard struct rules.
#
_TE5_COORD_STRUCT = struct.Struct("<BIBBBffddfffIB")


#
# Flag constants for the Coord.flags field.
#
FLAG_TEXT_FRAME = 0x02
FLAG_TRUE_TYPE_FONT = 0x20


# Composed types used in data classes
Te5PadSix = Tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class Te5Header:
    """TE5/VA50 header.

    Attributes:
        signature: File signature, expected to be ``b"VA50"``.
        unk: Single 8-bit value with unknown purpose.
        pad: Six 32-bit unsigned integers (padding/unknown fields).
    """

    signature: bytes
    unk: int
    pad: Te5PadSix


@dataclass(frozen=True)
class Te5TextMeta:
    """Single TE5 text metadata record.

    Attributes:
        first_zero: Observed as 0 or 1; potentially marks deleted/missing.
        text_id: Unique text identifier.
        layer: Zero-based layer index.
        font: Zero-based font index.
        flags: Bit flags (see ``FLAG_*`` constants).
        height: Text height.
        direction: Text direction (radians or degrees depending on dataset).
        east: X coordinate (meters).
        north: Y coordinate (meters).
        align_east: Alignment offset along east axis.
        align_north: Alignment offset along north axis.
        z: Elevation (meters).
        offset: Offset inside the text store, relative to the first text.
        length: Stored length including the final NUL terminator.
    """

    first_zero: int
    text_id: int
    layer: int
    font: int
    flags: int
    height: float
    direction: float
    east: float
    north: float
    align_east: float
    align_north: float
    z: float
    offset: int
    length: int

    def true_length(self) -> int:
        """Return the string length excluding the NUL terminator.

        Returns:
            The length value minus one, floored at zero.
        """

        if self.length <= 0:
            return 0
        return self.length - 1

    def absolute_text_offset(self, first_text_absolute_offset: int) -> int:
        """Compute absolute file offset of the referenced text.

        The TE5 ``offset`` is relative to the first text entry in the paired
        TS5 text store. To map it to an absolute file offset, provide the
        absolute offset of the first text.

        Args:
            first_text_absolute_offset: Absolute byte offset to the first
                text in the TS5 file.

        Returns:
            Absolute byte offset to the start of the string referenced by
            this metadata record.
        """

        return first_text_absolute_offset + self.offset

    def has_flag(self, flag_value: int) -> bool:
        """Check whether ``flag_value`` is set in ``flags``.

        Args:
            flag_value: Bit mask to test.

        Returns:
            True if all bits in ``flag_value`` are set, False otherwise.
        """

        return (self.flags & flag_value) == flag_value


def _parse_te5_header(data: bytes, offset: int = 0) -> Tuple[Te5Header, int]:
    """Parse the TE5 header starting at ``offset``.

    Args:
        data: Entire file as bytes.
        offset: Offset where the header starts.

    Returns:
        Tuple of the parsed ``Te5Header`` and the new offset after the header.

    Throws:
        ValueError: If the buffer is too small or the signature is invalid.
    """

    # Ensure enough bytes for the header.
    if len(data) - offset < _TE5_HEADER_STRUCT.size:
        raise ValueError("Buffer too small for TE5 header")

    # Unpack fields using the predefined struct.
    signature, unk, p1, p2, p3, p4, p5, p6 = _TE5_HEADER_STRUCT.unpack_from(
        data, offset
    )

    # Validate the signature.
    if signature != b"VA50":
        raise ValueError("Invalid TE5 signature: %r" % (signature,))

    # Sanity: all-zero padding with unk=0 is considered invalid header.
    if unk == 0 and (p1, p2, p3, p4, p5, p6) == (0, 0, 0, 0, 0, 0):
        raise ValueError("Invalid TE5 header values")

    # Build the header dataclass and return with new offset.
    header = Te5Header(
        signature=signature, unk=unk, pad=(p1, p2, p3, p4, p5, p6)
    )
    return header, offset + _TE5_HEADER_STRUCT.size


def _parse_text_meta_records(
    data: bytes, offset: int
) -> Tuple[List[Te5TextMeta], int]:
    """Parse TE5 Coord records until EOF.

    Args:
        data: Entire file as bytes.
        offset: Offset to the first record.

    Returns:
        Tuple of list of ``Te5TextMeta`` and the final offset (EOF).
    """

    # Prepare container for parsed records.
    records: List[Te5TextMeta] = []

    # Iterate while enough bytes remain for one full record.
    size = _TE5_COORD_STRUCT.size
    data_len = len(data)
    while offset + size <= data_len:
        (
            first_zero,
            text_id,
            layer,
            font,
            flags,
            height,
            direction,
            east,
            north,
            align_east,
            align_north,
            z,
            rel_offset,
            length,
        ) = _TE5_COORD_STRUCT.unpack_from(data, offset)

        # Create immutable record and append to results.
        records.append(
            Te5TextMeta(
                first_zero=first_zero,
                text_id=text_id,
                layer=layer,
                font=font,
                flags=flags,
                height=height,
                direction=direction,
                east=east,
                north=north,
                align_east=align_east,
                align_north=align_north,
                z=z,
                offset=rel_offset,
                length=length,
            )
        )

        # Advance to next record.
        offset += size

    # Warn if trailing bytes exist that don't form a full record.
    trailing = data_len - offset
    if trailing:
        logger.debug("Trailing %d bytes after TE5 text metadata", trailing)

    return records, offset


def parse_te5(data: bytes) -> Tuple[Te5Header, List[Te5TextMeta]]:
    """Parse a TE5/VA50 text metadata file from bytes.

    Args:
        data: File content as bytes.

    Returns:
        Tuple of (``Te5Header``, list of ``Te5TextMeta``).
    """

    # Parse the header first.
    header, offset = _parse_te5_header(data, 0)

    # Parse all text metadata records until EOF.
    records, _ = _parse_text_meta_records(data, offset)

    # Return structured result.
    return header, records


__all__ = [
    "Te5Header",
    "Te5TextMeta",
    "FLAG_TEXT_FRAME",
    "FLAG_TRUE_TYPE_FONT",
    "parse_te5",
]
