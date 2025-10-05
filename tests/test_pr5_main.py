"""Tests for the PR5 MapSys parser (mapsys.parser.pr5_main)."""

from __future__ import annotations

import struct

import pytest

from mapsys.parser.pr5_main import (
    AfterLayers,
    FontEntry,
    Header,
    Layer,
    LayerAttribute,
    Pr5File,
    _decode_c_string,
    parse_pr5,
)


def _pack_c_string(text: str, size: int) -> bytes:
    b = text.encode("windows-1250", errors="replace") + b"\x00"
    return b + (b"\x00" * (size - len(b)))


def _build_header_bytes(
    *,
    signature: bytes = b"MapSys",
) -> bytes:
    header_struct = struct.Struct("<6sB3B256s256sHHH6B5dB4dH")
    file_path = _pack_c_string("C:/mapsys/file.pr5", 256)
    dir_path = _pack_c_string("C:/mapsys", 256)

    # Integers and doubles are filled with simple values.
    payload = header_struct.pack(
        signature,
        0,  # zero
        1,
        2,
        3,
        file_path,
        dir_path,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        0.001,
        500000.0,
        500000.0,
        0.0,
        1.0,
        255,
        -10.0,
        10.0,
        -20.0,
        20.0,
        2,
    )

    nine_struct = struct.Struct("<6B")
    nine = b"".join(nine_struct.pack(1, 2, 3, 4, 5, 6) for _ in range(9))
    pad = b"\x00"
    return payload + nine + pad


def _build_layer_bytes(i: int) -> bytes:
    prefix = struct.Struct("<4B64s12sBB81s")
    attr = struct.Struct("<f3xB3xBBff")

    title = _pack_c_string(f"Layer {i}", 64)
    content1 = b"\x00" * 12
    content2 = b"\x00" * 81

    rec = prefix.pack(1, 2, 3, 4, title, content1, 7, 2, content2)

    # Nine attributes with distinct content3 and small floats.
    for j in range(9):
        rec += attr.pack(1.0 + j, 5, 8, j, 0.25 * j, 0.5 * j)
    return rec


def _build_after_layers_bytes(i: int) -> bytes:
    al = struct.Struct("<I H 64s B 2x B B 24s")
    name = _pack_c_string(f"AL{i}", 64)
    return al.pack(1234, 0, name, 0, 1, 0, b"\x00" * 24)


def _build_font_entry_bytes(i: int) -> bytes:
    # 12-char name plus final NUL (total 13 bytes)
    name = f"F{i:02d}".encode("ascii") + b"\x00" * 10 + b"\x00"
    font = struct.Struct("<13s")
    return font.pack(name)


def _build_pr5_bytes() -> bytes:
    data = _build_header_bytes()

    # 256 layers
    for i in range(256):
        data += _build_layer_bytes(i)

    # 256 after-layers
    for i in range(256):
        data += _build_after_layers_bytes(i)

    # Final blocks
    data += b"\xaa\xbb\xcc\xdd"  # some_final_stuff (4 bytes)
    data += b"\x00" * 256  # all_characters
    data += b"\x01" * 256  # ones

    # 20 font entries
    for i in range(20):
        data += _build_font_entry_bytes(i)

    # Two u16 values and two zero bytes
    data += struct.pack("<HH", 30, 5)
    data += b"\x00\x00"

    # mdb buffer and final zeros
    data += _pack_c_string("C:/db/sample.mdb", 256)
    data += b"\x00" * 256

    return data


def test_decode_c_string_basic_and_truncation() -> None:
    assert _decode_c_string(b"abc\x00def\x00") == "abc"
    # No NUL present -> entire buffer decoded
    assert _decode_c_string(b"xyz") == "xyz"


def test_parse_pr5_header_only_invalid_signature_raises() -> None:
    bad = _build_header_bytes(signature=b"BAD!!!")
    with pytest.raises(ValueError):
        parse_pr5(bad)


def test_parse_pr5_buffer_too_small_header() -> None:
    with pytest.raises(ValueError):
        parse_pr5(b"\x00" * 10)


def test_parse_pr5_end_to_end_minimal_valid() -> None:
    blob = _build_pr5_bytes()
    pr5 = parse_pr5(blob)

    assert isinstance(pr5, Pr5File)

    # Header
    h = pr5.head
    assert isinstance(h, Header)
    assert h.signature == b"MapSys"
    assert h.nine and len(h.nine) == 9

    # Layers
    assert len(pr5.layers) == 256
    first_layer = pr5.layers[0]
    assert isinstance(first_layer, Layer)
    assert first_layer.title.startswith("Layer ")
    assert len(first_layer.attribs) == 9
    la0 = first_layer.attribs[0]
    assert isinstance(la0, LayerAttribute)

    # After-layers
    assert len(pr5.after) == 256
    assert isinstance(pr5.after[0], AfterLayers)

    # Final blocks and fonts
    assert pr5.some_final_stuff == b"\xaa\xbb\xcc\xdd"
    assert len(pr5.all_characters) == 256
    assert len(pr5.ones) == 256
    assert len(pr5.font_names) == 20
    assert isinstance(pr5.font_names[0], FontEntry)
    assert pr5.a_30_value == 30
    assert pr5.a_5_value == 5
    assert pr5.mdb.endswith("sample.mdb")
    assert len(pr5.empty) == 256
