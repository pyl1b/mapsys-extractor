"""Tests for mapsys.dxf.dxf_colors helpers."""

from __future__ import annotations

from typing import Any

import pytest

from mapsys.dxf.dxf_colors import (
    PALETTE_256,
    get_palette_rgb,
    set_entity_color_from_index,
    set_layer_color_from_index,
)


def _rgb_to_truecolor(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return (r << 16) + (g << 8) + b


class _DummyDXF:
    def __init__(self) -> None:
        self.true_color: int | None = None


class _DummyLayer:
    def __init__(self) -> None:
        self.dxf = _DummyDXF()


class _DummyEntity:
    def __init__(self) -> None:
        self.dxf = _DummyDXF()


class TestGetPaletteRGB:
    def test_valid_indices_boundary_and_middle(self) -> None:
        size = len(PALETTE_256)
        sample_indices = {0, size - 1, size // 2}
        for idx in sample_indices:
            assert get_palette_rgb(idx) == PALETTE_256[idx]

    def test_invalid_negative_index(self) -> None:
        with pytest.raises(ValueError):
            get_palette_rgb(-1)

    def test_invalid_index_equal_to_length(self) -> None:
        with pytest.raises(ValueError):
            get_palette_rgb(len(PALETTE_256))


class TestSetTrueColorHelpers:
    def test_set_layer_color_from_index_applies_true_color(self) -> None:
        layer = _DummyLayer()
        index = 12
        expected_rgb = PALETTE_256[index]
        layer_any: Any = layer
        returned_rgb = set_layer_color_from_index(layer_any, index)

        assert returned_rgb == expected_rgb
        assert isinstance(layer.dxf.true_color, int)
        assert layer.dxf.true_color == _rgb_to_truecolor(expected_rgb)

    def test_set_entity_color_from_index_applies_true_color(self) -> None:
        entity = _DummyEntity()
        index = 200
        expected_rgb = PALETTE_256[index]
        entity_any: Any = entity
        returned_rgb = set_entity_color_from_index(entity_any, index)

        assert returned_rgb == expected_rgb
        assert isinstance(entity.dxf.true_color, int)
        assert entity.dxf.true_color == _rgb_to_truecolor(expected_rgb)

    @pytest.mark.parametrize("bad_index", [-5, len(PALETTE_256)])
    def test_setters_raise_for_invalid_index(self, bad_index: int) -> None:
        layer = _DummyLayer()
        entity = _DummyEntity()

        layer_any: Any = layer
        with pytest.raises(ValueError):
            set_layer_color_from_index(layer_any, bad_index)

        entity_any: Any = entity
        with pytest.raises(ValueError):
            set_entity_color_from_index(entity_any, bad_index)
        # End of test module
