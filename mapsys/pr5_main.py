"""PR5 (MapSys) binary structures and parser.

This module implements a typed parser for ``.pr5`` files following the
ImHex pattern provided. The file is little-endian and starts with the
signature ``b"MapSys\x00"``.

The layout (simplified) is:

- Header
- 256 ``Layer`` records
- 256 ``AfterLayers`` records
- 4 bytes of trailing data
- 256 bytes: ``all_characters``
- 256 bytes: ``ones``
- 20 ``FontEntry`` records
- Two 16-bit values and two padding zeros
- 256-byte ``mdb`` string buffer
- 256-byte zero buffer

All fixed-size C strings are stored as zero-terminated byte arrays.
This parser decodes string fields using Windows-1250, stripping any
trailing NUL (0x00) and whitespace. Unknown/opaque byte areas are kept
as ``bytes``.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


#
# Helpers
#


def _decode_c_string(buf: bytes) -> str:
    """Decode a fixed-size zero-terminated byte buffer to text.

    Args:
        buf: The raw bytes containing the string and possible padding.

    Returns:
        Decoded text with trailing NUL and whitespace removed.
    """

    try:
        end = buf.find(0)
        if end == -1:
            end = len(buf)
        return buf[:end].decode("windows-1250", errors="replace").strip()
    except Exception:
        logger.debug("Failed decoding PR5 string; using replacement")
        return buf.rstrip(b"\x00").decode("utf-8", errors="replace").strip()


#
# Data structures
#


@dataclass(frozen=True)
class FontEntry:
    """Single font table entry.

    Attributes:
        name: Font name decoded from a 12-byte buffer.
        raw: Original 13-byte block (12-byte name + final NUL).
    """

    name: str
    raw: bytes


@dataclass(frozen=True)
class LayerAttribute:
    """Per-layer attribute as described by the ImHex layout.

    Attributes:
        height: Text height.
        scale: Scale factor byte.
        color: Color index byte.
        content1: First opaque 3-byte area.
        content2: Second opaque 3-byte area.
        content3: Final opaque 1-byte area after color (as seen).
        d_x: Alignment/offset X.
        d_y: Alignment/offset Y.
    """

    height: float
    scale: int
    color: int
    content1: bytes
    content2: bytes
    content3: int
    d_x: float
    d_y: float


@dataclass(frozen=True)
class Layer:
    """One PR5 layer with title, style and 9 attributes."""

    first_four: Tuple[int, int, int, int]
    title: str
    color: int
    weight: int
    content1: bytes
    content2: bytes
    attribs: Tuple[LayerAttribute, ...]


@dataclass(frozen=True)
class TheNine:
    """Six bytes of unknown data, repeated nine times in the header."""

    b0: int
    b1: int
    b2: int
    b3: int
    b4: int
    b5: int


@dataclass(frozen=True)
class AfterLayers:
    """Record following the 256 layers."""

    first_four: int
    zero_two: int
    name: str
    has_value_1: int
    has_value_2: int
    unk: bytes


@dataclass(frozen=True)
class Header:
    """PR5 header.

    Attributes contain a mix of strings, small integers and doubles.
    Unknown byte fields are retained to preserve information.
    """

    signature: bytes
    zero: int
    unk_1_1: int
    unk_1_2: int
    unk_1_3: int
    file_path: str
    dir_path: str
    unk_2_1: int
    unk_2_2: int
    unk_2_3: int
    unk_3: Tuple[int, int, int, int, int, int]
    some_001: float
    east_500000: float
    north_500000: float
    a_zero: float
    a_one: float
    ff_pad: int
    east_min: float
    east_max: float
    north_min: float
    north_max: float
    two: int
    nine: Tuple[TheNine, ...]
    pad_again: int


@dataclass(frozen=True)
class Pr5File:
    """Entire parsed PR5 file."""

    head: Header
    layers: Tuple[Layer, ...]
    after: Tuple[AfterLayers, ...]
    some_final_stuff: bytes
    all_characters: bytes
    ones: bytes
    font_names: Tuple[FontEntry, ...]
    a_30_value: int
    a_5_value: int
    two_zeros: bytes
    mdb: str
    empty: bytes


#
# Binary formats (little-endian, packed)
#

_HEADER_PART1 = struct.Struct("<6sB3B256s256sHHH6B5dB4dH")
_THE_NINE = struct.Struct("<6B")

_LAYER_PREFIX = struct.Struct("<4B64s12sBB81s")
_LAYER_ATTR = struct.Struct("<f3xB3xBBff")

_AFTER_LAYERS = struct.Struct("<I H 64s B 2x B B 24s")

_FONT_ENTRY_RAW = struct.Struct("<13s")  # 12 name + 1 final NUL


def _parse_header(data: bytes, offset: int = 0) -> Tuple[Header, int]:
    """Parse the file header.

    Args:
        data: Entire file buffer.
        offset: Offset where the header starts.

    Returns:
        Tuple of the parsed header and new offset after the header.
    """

    if len(data) - offset < _HEADER_PART1.size + (_THE_NINE.size * 9) + 1:
        raise ValueError("Buffer too small for PR5 header")

    (
        signature,
        zero,
        u11,
        u12,
        u13,
        file_path_b,
        dir_path_b,
        u21,
        u22,
        u23,
        u31,
        u32,
        u33,
        u34,
        u35,
        u36,
        some_001,
        east_500000,
        north_500000,
        a_zero,
        a_one,
        ff_pad,
        east_min,
        east_max,
        north_min,
        north_max,
        two,
    ) = _HEADER_PART1.unpack_from(data, offset)

    offset += _HEADER_PART1.size

    nine_list: List[TheNine] = []
    for _ in range(9):
        b0, b1, b2, b3, b4, b5 = _THE_NINE.unpack_from(data, offset)
        nine_list.append(TheNine(b0, b1, b2, b3, b4, b5))
        offset += _THE_NINE.size

    # Single pad byte following the nine[] array
    if offset >= len(data):
        raise ValueError("Unexpected EOF after header nine[]")
    pad_again = data[offset]
    offset += 1

    # Validate signature
    if not (signature.startswith(b"MapSys") and len(signature) == 6):
        raise ValueError(f"Invalid PR5 signature: {signature!r}")

    header = Header(
        signature=signature,
        zero=zero,
        unk_1_1=u11,
        unk_1_2=u12,
        unk_1_3=u13,
        file_path=_decode_c_string(file_path_b),
        dir_path=_decode_c_string(dir_path_b),
        unk_2_1=u21,
        unk_2_2=u22,
        unk_2_3=u23,
        unk_3=(u31, u32, u33, u34, u35, u36),
        some_001=some_001,
        east_500000=east_500000,
        north_500000=north_500000,
        a_zero=a_zero,
        a_one=a_one,
        ff_pad=ff_pad,
        east_min=east_min,
        east_max=east_max,
        north_min=north_min,
        north_max=north_max,
        two=two,
        nine=tuple(nine_list),
        pad_again=pad_again,
    )

    return header, offset


def _parse_layer(data: bytes, offset: int) -> Tuple[Layer, int]:
    """Parse one ``Layer`` record."""

    (
        f1,
        f2,
        f3,
        f4,
        title_b,
        content1,
        color,
        weight,
        content2,
    ) = _LAYER_PREFIX.unpack_from(data, offset)
    offset += _LAYER_PREFIX.size

    attribs: List[LayerAttribute] = []
    for _ in range(9):
        (
            height,
            scale,
            color_attr,
            content3,
            d_x,
            d_y,
        ) = _LAYER_ATTR.unpack_from(data, offset)

        # Note: _LAYER_ATTR uses explicit padding (3x and 3x) to skip the two
        # opaque 3-byte blobs described by the ImHex script. We recover them
        # from the raw slice to retain the information.
        raw = data[offset : offset + _LAYER_ATTR.size]
        content1_blob = raw[4:7]
        content2_blob = raw[8:11]

        attribs.append(
            LayerAttribute(
                height=height,
                scale=scale,
                color=color_attr,
                content1=bytes(content1_blob),
                content2=bytes(content2_blob),
                content3=content3,
                d_x=d_x,
                d_y=d_y,
            )
        )
        offset += _LAYER_ATTR.size

    layer = Layer(
        first_four=(f1, f2, f3, f4),
        title=_decode_c_string(title_b),
        color=color,
        weight=weight,
        content1=content1,
        content2=content2,
        attribs=tuple(attribs),
    )
    return layer, offset


def _parse_after_layers(data: bytes, offset: int) -> Tuple[AfterLayers, int]:
    """Parse one ``AfterLayers`` record."""

    (
        first_four,
        zero_two,
        name_b,
        final_nul,  # kept implicitly by decoding
        has_value_1,
        has_value_2,
        unk,
    ) = _AFTER_LAYERS.unpack_from(data, offset)

    _ = final_nul  # field present in layout; content absorbed by name decoding
    offset += _AFTER_LAYERS.size

    rec = AfterLayers(
        first_four=first_four,
        zero_two=zero_two,
        name=_decode_c_string(name_b),
        has_value_1=has_value_1,
        has_value_2=has_value_2,
        unk=unk,
    )
    return rec, offset


def _parse_font_entry(data: bytes, offset: int) -> Tuple[FontEntry, int]:
    (raw13,) = _FONT_ENTRY_RAW.unpack_from(data, offset)
    offset += _FONT_ENTRY_RAW.size
    name = _decode_c_string(raw13[:12])
    return FontEntry(name=name, raw=raw13), offset


def parse_pr5(data: bytes) -> Pr5File:
    """Parse a PR5 file from bytes.

    Args:
        data: File content as bytes.

    Returns:
        Fully parsed :class:`Pr5File` instance.
    """

    # Header
    header, offset = _parse_header(data, 0)

    # 256 layers
    layers: List[Layer] = []
    for _ in range(256):
        layer, offset = _parse_layer(data, offset)
        layers.append(layer)

    # 256 AfterLayers
    after_list: List[AfterLayers] = []
    for _ in range(256):
        rec, offset = _parse_after_layers(data, offset)
        after_list.append(rec)

    # Final blocks
    if offset + 4 > len(data):
        raise ValueError("Unexpected EOF reading some_final_stuff")
    some_final_stuff = data[offset : offset + 4]
    offset += 4

    if offset + 256 > len(data):
        raise ValueError("Unexpected EOF reading all_characters")
    all_characters = data[offset : offset + 256]
    offset += 256

    if offset + 256 > len(data):
        raise ValueError("Unexpected EOF reading ones")
    ones = data[offset : offset + 256]
    offset += 256

    # 20 font entries
    fonts: List[FontEntry] = []
    for _ in range(20):
        font, offset = _parse_font_entry(data, offset)
        fonts.append(font)

    # Two u16 values and two zero bytes
    if offset + 2 * 2 + 2 > len(data):
        raise ValueError("Unexpected EOF reading trailer values")
    a_30_value, a_5_value = struct.unpack_from("<HH", data, offset)
    offset += 4
    two_zeros = data[offset : offset + 2]
    offset += 2

    # 256-byte MDB path-like buffer
    if offset + 256 > len(data):
        raise ValueError("Unexpected EOF reading mdb buffer")
    mdb_b = data[offset : offset + 256]
    offset += 256
    mdb = _decode_c_string(mdb_b)

    # Final 256 zero bytes
    if offset + 256 > len(data):
        raise ValueError("Unexpected EOF reading final zero buffer")
    empty = data[offset : offset + 256]
    offset += 256

    return Pr5File(
        head=header,
        layers=tuple(layers),
        after=tuple(after_list),
        some_final_stuff=some_final_stuff,
        all_characters=all_characters,
        ones=ones,
        font_names=tuple(fonts),
        a_30_value=a_30_value,
        a_5_value=a_5_value,
        two_zeros=two_zeros,
        mdb=mdb,
        empty=empty,
    )


__all__ = [
    "FontEntry",
    "LayerAttribute",
    "Layer",
    "TheNine",
    "AfterLayers",
    "Header",
    "Pr5File",
    "parse_pr5",
]
