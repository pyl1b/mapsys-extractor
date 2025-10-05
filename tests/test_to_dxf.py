import math
from pathlib import Path
from typing import Any, Dict, List

import pytest

from mapsys.dxf.to_dxf import Builder
from mapsys.parser.ar5_polys import Ar5Data
from mapsys.parser.n05_points import No5Coord
from mapsys.parser.te5_text_meta import Te5TextMeta
from mapsys.parser.ts5_text_store import Ts5Text


class DummyMapsys:
    points: List[No5Coord]
    p_meta: List[Ar5Data]
    v_offsets: List[int]
    t_meta: List[Te5TextMeta]
    texts: List[Ts5Text]
    offset_to_text: Dict[int, str]
    p_layers: List[Any]
    pr5: Any

    def __init__(self) -> None:
        # Points: two points on layer 1 and one on layer 2

        self.points = [
            No5Coord(
                type=16,
                id_nr=1,
                layer=1,
                pt_nr=101,
                east=0.0,
                north=0.0,
                z=1.5,
                uniq=1,
                connexion=0,
            ),
            No5Coord(
                type=16,
                id_nr=2,
                layer=1,
                pt_nr=102,
                east=1.0,
                north=0.0,
                z=2.5,
                uniq=2,
                connexion=0,
            ),
            No5Coord(
                type=16,
                id_nr=3,
                layer=2,
                pt_nr=201,
                east=0.0,
                north=1.0,
                z=3.5,
                uniq=3,
                connexion=0,
            ),
        ]

        # Polylines: one line with the two first points, using AS5 offsets
        self.p_meta = [
            Ar5Data(
                unk8=0,
                line_id=1,
                line_nr=1,
                unk1=0,
                vertex_offset=0,
                vertex_count=2,
                lay_rec=0,
                layer_count=1,
                unk6=0,
                unk7=0,
            )
        ]

        # AS5 offsets map to points indices [0, 1]
        self.v_offsets = [0, 1]

        # Text metadata: one text
        self.t_meta = [
            Te5TextMeta(
                first_zero=0,
                text_id=1,
                layer=2,
                font=0,
                flags=0,
                height=0.5,
                direction=math.pi / 2,
                east=0.0,
                north=1.0,
                align_east=0.0,
                align_north=0.0,
                z=0.0,
                offset=0,
                length=4,
            )
        ]

        # TS5 texts storage through content API expected by Builder
        self.texts = []
        self.offset_to_text = {0: "TXT"}

        # Poly layer mapping uses AL5 mapping; map first poly to layer 1
        class PLayer:
            def __init__(
                self, layer: int, title: str, color: int, weight: int
            ) -> None:
                self.layer = layer
                self.title = title
                self.color = color
                self.weight = weight

        self.p_layers = [PLayer(layer=1, title="", color=10, weight=5)]

        # PR5 object with layers used for names/colors/weights
        class MapLayer:
            def __init__(self, title: str, color: int, weight: int) -> None:
                self.title = title
                self.color = color
                self.weight = weight

        class PR5:
            def __init__(self) -> None:
                self.layers = [
                    MapLayer("L0", 1, 1),
                    MapLayer("Roads", 10, 5),
                    MapLayer("Text", 20, 3),
                ]

        self.pr5 = PR5()

    def text_by_offset(self, offset: int):
        return self.offset_to_text.get(offset)

    def get_poly_layer(self, p_meta):
        # Route to AL5 mapping
        return self.p_layers[p_meta.lay_rec].layer


def _make_minimal_template(tmp_path: Path) -> Path:
    # Create a minimal DXF template containing a POINT block with NAME,SOURCE,Z
    import ezdxf

    doc = ezdxf.new(setup=True)
    blk = doc.blocks.new("POINT")
    blk.add_attdef("NAME", insert=(0, 0), height=0.2)
    blk.add_attdef("SOURCE", insert=(0, 0), height=0.2)
    blk.add_attdef("Z", insert=(0, 0), height=0.2)
    path = tmp_path / "template.dxf"
    doc.saveas(path.as_posix())
    return path


def test_builder_convert_creates_entities_and_layers(tmp_path: Path):
    mapsys = DummyMapsys()
    template = _make_minimal_template(tmp_path)

    doc = Builder.convert(
        mapsys,  # type: ignore[arg-type]
        template,
        dxf_path=None,
        segregate_by_object_type=True,
        random_colors=False,
    )

    msp = doc.modelspace()
    # Expect 3 inserts for points + 1 LWPOLYLINE + 1 TEXT = 5 entities
    assert len(msp) == 5

    # Check that layers exist and are named with suffixes
    layer_names = {ly.dxf.name for ly in doc.layers}
    assert any(
        (name.startswith("MapSys-1-") and name.endswith("points"))
        for name in layer_names
    )
    assert any(
        (name.startswith("MapSys-1-") and name.endswith("lines"))
        for name in layer_names
    )
    assert any(
        (name.startswith("MapSys-2-") and name.endswith("text"))
        for name in layer_names
    )


def test_layer_name_includes_title_when_available(tmp_path: Path):
    mapsys = DummyMapsys()
    _ = _make_minimal_template(tmp_path)
    b = Builder(mapsys)  # type: ignore[arg-type]
    # pr5 layer 1 has title "Roads"
    name = b.layer_name(1, suffix="points")
    assert name == "MapSys-1-Roads-points"


@pytest.mark.parametrize(
    "value,expected_index",
    [
        (0, 1),
        (1, 1),
        (2, 4),
        (3, 8),
        (4, 9),  # first bucket after custom mapping
        (
            255,
            9
            + (255 - 4)
            * (
                len(__import__("ezdxf").lldxf.const.VALID_DXF_LINEWEIGHTS[9:])
                // 253
            ),
        ),
    ],
)
def test_lineweight_from_mapsys_valid(value: int, expected_index: int):
    # We validate that returned value is one of VALID_DXF_LINEWEIGHTS and
    # that for small values it matches the documented mapping.
    from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS

    lw = Builder.lineweight_from_mapsys(value)
    assert lw in VALID_DXF_LINEWEIGHTS
    if value in (0, 1, 2, 3):
        assert lw == VALID_DXF_LINEWEIGHTS[expected_index]


@pytest.mark.parametrize("bad", [-1, 256])
def test_lineweight_from_mapsys_out_of_range_raises(bad: int):
    with pytest.raises(ValueError):
        Builder.lineweight_from_mapsys(bad)


def test_lineweight_from_mapsys_type_error():
    with pytest.raises(TypeError):
        Builder.lineweight_from_mapsys("3")  # type: ignore[arg-type]


def test_rotate_dxf_backups(tmp_path: Path):
    target = tmp_path / "out.dxf"
    # Create three generations
    target.write_text("v1")
    Builder._rotate_dxf_backups(target, max_backups=3)
    target.write_text("v2")
    Builder._rotate_dxf_backups(target, max_backups=3)
    target.write_text("v3")
    Builder._rotate_dxf_backups(target, max_backups=3)

    # After three rotations and no save, we expect .bak1..bak3 present
    assert (tmp_path / "out.bak1").exists()
    assert (tmp_path / "out.bak2").exists()
    assert (tmp_path / "out.bak3").exists()
