"""VA50/TS5 text storage parser.

This module parses a VA50 container that stores a sequence of
null-terminated strings after a simple header. Texts are decoded using
Windows-1250 by default; if decoding fails, UTF-8 with replacement is used.

Header (little-endian):
- signature: 4 bytes, must be b"VA50"
- int1: 4 x u32 (purpose unknown)
- pad: 1 x u8 (usually 0)

Following the header, the file contains a sequence of C-strings until EOF.
Each string is stored as bytes terminated by a single NUL (0x00). For each
string we report the string-block-relative byte offset where the string
starts (i.e. offset 0 corresponds to the first string after the header).
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


_TS5_HEADER_STRUCT = struct.Struct("<4s4IB")
# Composed types used in data classes
Ts5IntQuad = Tuple[int, int, int, int]


@dataclass(frozen=True)
class Ts5Header:
    """TS5 file header.

    Attributes:
        signature: File signature, expected to be b"VA50".
        int1: Four 32-bit unsigned integers with unknown purpose.
        pad: Single 8-bit value (usually 0).
    """

    signature: bytes
    int1: Ts5IntQuad
    pad: int


@dataclass(frozen=True)
class Ts5Text:
    """A single text entry extracted from a TS5 file.

    Attributes:
        offset: The byte offset where the string starts in the file.
        text: The decoded string content (without the terminating NUL).
    """

    offset: int
    text: str


def _parse_ts5_header(data: bytes, offset: int = 0) -> Tuple[Ts5Header, int]:
    """Parse the TS5 header starting at ``offset``.

    Args:
        data: Entire file as bytes.
        offset: Offset where the header starts.

    Returns:
        Tuple of the parsed ``Ts5Header`` and the new offset after the header.

    Raises:
        ValueError: If the buffer is too small or the signature is invalid.
    """

    if len(data) - offset < _TS5_HEADER_STRUCT.size:
        raise ValueError("Buffer too small for TS5 header")

    signature, i1, i2, i3, i4, pad = _TS5_HEADER_STRUCT.unpack_from(
        data, offset
    )
    if signature != b"VA50":
        raise ValueError("Invalid TS5 signature: %r" % (signature,))

    header = Ts5Header(signature=signature, int1=(i1, i2, i3, i4), pad=pad)
    return header, offset + _TS5_HEADER_STRUCT.size


def _parse_cstrings_until_eof(
    data: bytes, offset: int
) -> Tuple[List[Ts5Text], int]:
    """Parse null-terminated strings until EOF.

    For each string, record its starting offset relative to the string block
    and decode using Windows-1250 by default. If decoding fails, fall back to
    UTF-8 with replacement for invalid sequences.
    """
    original_o = offset
    texts: List[Ts5Text] = []
    end = len(data)

    while offset < end:
        start = offset

        # Find NUL terminator; if not found, consume the rest as last string.
        try:
            nul_index = data.index(0, start, end)
            raw = data[start:nul_index]
            offset = nul_index + 1
        except ValueError:
            raw = data[start:end]
            offset = end

        # Decode as Windows-1250 (common for these files). Empty strings ok.
        try:
            text = raw.decode("windows-1250")
        except UnicodeDecodeError:
            logger.debug(
                "Invalid Windows-1250 sequence in TS5 at %d; using UTF-8 repl",
                start,
            )
            text = raw.decode("utf-8", errors="replace")

        texts.append(Ts5Text(offset=start - original_o, text=text))

    return texts, offset


def parse_ts5(data: bytes) -> Tuple[Ts5Header, List[Ts5Text]]:
    """Parse a VA50/TS5 file from bytes.

    Args:
        data: File content as bytes.

    Returns:
        Tuple of (``Ts5Header``, list of ``Ts5Text``).

    Raises:
        ValueError: If the header is invalid or the buffer is too small.
    """

    header, offset = _parse_ts5_header(data, 0)
    texts, _ = _parse_cstrings_until_eof(data, offset)
    return header, texts


__all__ = ["Ts5Header", "Ts5Text", "parse_ts5"]
