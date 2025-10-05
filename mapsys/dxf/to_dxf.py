"""DXF export utilities.

This module converts parsed ``mapsys`` content into a DXF document by using
an existing DXF template as a base. It inserts block references for all
points, generates polylines based on AR5/AS5 indices and writes text
entities from TE5/TS5.

The main entry-point is :meth:`Builder.convert` which loads the template,
invokes the individual insert operations, applies colors and line weights,
and optionally saves the resulting document to disk.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from attrs import define
from ezdxf import zoom
from ezdxf.document import Drawing
from ezdxf.layouts.layout import Layout
from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS

from mapsys.dxf.dxf_colors import set_layer_color_from_index
from mapsys.parser.ar5_polys import Ar5Data
from mapsys.parser.n05_points import No5Coord

if TYPE_CHECKING:
    from ezdxf.sections.table import LayerTable

    from mapsys.parser.content import Content

logger = logging.getLogger(__name__)

BLOCK_SOURCE = "MapSys"
BLOCK_ROTATION = 0.0
ATTRIB_HEIGHT = 0.25

LAYER_PREFIX = "MapSys"
POINT_SUFFIX = "points"
LINE_SUFFIX = "lines"
TEXT_SUFFIX = "text"


@define
class Builder:
    """Builds DXF documents from parsed MapSys content.

    This builder loads a DXF template and writes points, polylines
    and texts into layers named after the source MapSys
    structure.

    Attributes:
        mapsys: Parsed content container with points, polylines, texts,
            and metadata used for layers and styling.
        point_block: Name of the block to insert for points.
        point_name_attrib: ATTDEF tag that stores the point number.
        point_source_attrib: ATTDEF tag that stores the data source.
        point_z_attrib: ATTDEF tag that stores the elevation (Z) value.
        block_scale: Uniform scale applied to point block inserts.
        open_after_save: If True, open the saved DXF after writing.
        random_colors: If True, assign random colors to MapSys layers
            instead of MapSys-defined colors.
        segregate_by_object_type: If True, suffix layer names with the
            object type (points/lines/text) to split content by type.
    """

    mapsys: "Content"
    point_block: str = "POINT"
    point_name_attrib: str = "NAME"
    point_source_attrib: str = "SOURCE"
    point_z_attrib: str = "Z"
    block_scale: float = 1.0
    open_after_save: bool = False
    random_colors: bool = False
    segregate_by_object_type: bool = True

    @classmethod
    def convert(
        cls,
        mapsys: "Content",
        dxf_template: Path,
        *,
        dxf_path: Path | None = None,
        point_block: str = "POINT",
        point_name_attrib: str = "NAME",
        point_source_attrib: str = "SOURCE",
        point_z_attrib: str = "Z",
        block_scale: float = 1.0,
        open_after_save: bool = False,
        random_colors: bool = False,
        segregate_by_object_type: bool = True,
    ) -> Drawing:
        """Construct a Builder and run the conversion.

        Args:
            mapsys: Parsed content holding points, polylines and texts.
            dxf_template: Path to the template DXF file to load.
            dxf_path: Optional path to save the resulting DXF.
            point_block: Name of the block to insert for points.
            point_name_attrib: ATTDEF tag that stores the point number.
            point_source_attrib: ATTDEF tag that stores the data source.
            point_z_attrib: ATTDEF tag that stores the elevation (Z) value.
            block_scale: Uniform scale applied to point block inserts.
            open_after_save: If True, attempt to open the saved DXF.
            random_colors: If True, assign random colors to layers.
            segregate_by_object_type: If True, suffix layer names with the
                object type (``points``/``lines``/``text``).

        Returns:
            The in-memory DXF document instance.
        """
        builder = cls(
            mapsys=mapsys,
            point_block=point_block,
            point_name_attrib=point_name_attrib,
            point_source_attrib=point_source_attrib,
            point_z_attrib=point_z_attrib,
            block_scale=block_scale,
            open_after_save=open_after_save,
            random_colors=random_colors,
            segregate_by_object_type=segregate_by_object_type,
        )
        return builder.to_dxf(
            dxf_template=dxf_template,
            dxf_path=dxf_path,
        )

    def layer_name(self, layer: int, suffix: str = "") -> str:
        """Get the name of a layer for the current content.

        Note that we rely on this pattern to detect mapsys layers in the DXF
        file.

        Args:
            layer: The layer index.
            suffix: The suffix to add to the layer name.

        Returns:
            The name of the layer. It may consist to up to 4 parts separated
            by "-": LAYER_PREFIX, layer index, layer title, suffix. The title
            is only added if it is not empty. The suffix is only added if it is
            not empty.
        """
        parts = [LAYER_PREFIX, str(layer)]
        while True:
            if self.mapsys.pr5 is None:
                break
            if layer < 0 or layer >= len(self.mapsys.pr5.layers):
                break

            map_layer = self.mapsys.pr5.layers[layer]
            if not map_layer.title:
                break

            parts.append(map_layer.title)
            break

        if suffix:
            parts.append(suffix)
        return "-".join(parts)

    @staticmethod
    def _rotate_dxf_backups(dxf_path: Path, max_backups: int = 10) -> None:
        """Rotate existing DXF backups for ``dxf_path`` up to ``max_backups``.

        If the target file exists, it is renamed to ``.bak1`` and older backups
        are shifted up (``.bak1`` -> ``.bak2`` etc.). The oldest backup
        exceeding the limit is removed.

        Args:
            dxf_path: The destination DXF path that may be overwritten.
            max_backups: Maximum number of backup copies to keep.
        """

        try:
            # Guard: nothing to rotate when file does not exist.
            if not dxf_path.exists():
                return

            # Backups use the base file name without extension, e.g. out.bak1
            backup_base = dxf_path.with_name(dxf_path.stem)

            # Delete the oldest backup if it exists to make room.
            oldest = backup_base.with_suffix(f".bak{max_backups}")
            if oldest.exists():
                try:
                    oldest.unlink()
                except Exception:
                    logger.exception(
                        "Failed removing oldest backup: %s", oldest
                    )

            # Shift backups in descending order to avoid overwriting.
            for idx in range(max_backups - 1, 0, -1):
                src = backup_base.with_suffix(f".bak{idx}")
                dst = backup_base.with_suffix(f".bak{idx + 1}")
                if src.exists():
                    try:
                        src.rename(dst)
                    except Exception:
                        logger.exception(
                            "Failed rotating backup %s -> %s", src, dst
                        )

            # Finally rename the current file to first backup
            # (e.g. out -> out.bak1).
            try:
                dxf_path.rename(backup_base.with_suffix(".bak1"))
            except Exception:
                logger.exception(
                    "Failed creating first backup for %s", dxf_path
                )
        except Exception:
            # Never fail the export because of backup problems.
            logger.exception(
                "Unexpected error during backup rotation for %s", dxf_path
            )

    @staticmethod
    def _iter_poly_vertices(
        ar: Iterable[Ar5Data],
        verticels: list[int],
        points: list[No5Coord],
    ) -> Iterable[tuple[Ar5Data, list[tuple[float, float]]]]:
        """Yield vertex lists for each polyline described by AR5/AS5 tables.

        Args:
            ar: Parsed AR5 entries (one per polyline).
            verticels: Offsets table from AS5 (byte offsets into NO5 data).
            points: Parsed NO5 coordinates list.

        Yields:
            polyline metadata entry and the lists of ``(x, y)`` pairs for each
            line that has at least two points.
        """

        num_offsets = len(verticels)
        num_points = len(points)

        for entry in ar:
            start = entry.vertex_offset
            count = entry.vertex_count

            # Validate start/count against the offsets table size.
            if start < 0 or count <= 0:
                logger.warning(
                    "Start %d or count %d is invalid",
                    start,
                    count,
                )
                continue
            if start >= num_offsets:
                logger.warning(
                    "Start %d is out of range for %d offsets",
                    start,
                    num_offsets,
                )
                continue

            end = min(start + count, num_offsets)
            vertices: list[tuple[float, float]] = []

            # Build vertices by mapping offsets to point indices.
            for off in verticels[start:end]:
                if off >= num_points:
                    logger.warning(
                        "Offset %d is out of range for %d points",
                        off,
                        num_points,
                    )
                    continue
                point = points[off]
                vertices.append((float(point.east), float(point.north)))

            # Only lines with at least two vertices are meaningful in DXF.
            if len(vertices) >= 2:
                yield entry, vertices

    def to_dxf(
        self,
        dxf_template: Path,
        *,
        dxf_path: Path | None = None,
    ) -> Drawing:
        """Create a DXF document from parsed ``mapsys`` content.

        The function loads a template DXF, inserts a block reference for every
        point with its name (``point_name_attrib``) set to the point number,
        draws polylines derived from the AR5/AS5 indices and writes text
        entities when available.

        Args:
            dxf_template: Path to the template DXF file to load.
            dxf_path: Optional path to save the resulting DXF.

        Returns:
            The in-memory DXF document instance.
        """
        added_layers = set()

        # Load DXF template into memory.
        # Prefer recover.readfile() for robust loading of DXF files.
        # Local import to appease linters
        from ezdxf import recover as _recover

        doc, _auditor = _recover.readfile(dxf_template.as_posix())
        msp = doc.modelspace()

        # Insert a block for each point with the NAME attribute set.
        block_exists = self.point_block in doc.blocks
        if not block_exists:
            logger.warning(
                (
                    "Block '%s' not found in template; points will be drawn "
                    "as circles"
                ),
                self.point_block,
            )
        else:
            attributes = set()
            for attdef in doc.blocks[self.point_block].query("ATTDEF"):
                attributes.add(attdef.dxf.tag)
            for a_name in (
                self.point_name_attrib,
                self.point_source_attrib,
                self.point_z_attrib,
            ):
                if a_name not in attributes:
                    logger.warning(
                        (
                            "Attribute '%s' not found in block '%s'; "
                            "points will have no %s attribute"
                        ),
                        a_name,
                        self.point_block,
                        a_name,
                    )

        added_layers.update(self.insert_points(block_exists, msp))

        added_layers.update(self.insert_lines(msp))
        added_layers.update(self.insert_texts(msp))

        # Get the layer table
        for ly in added_layers:
            doc.layers.add(ly)

        if self.random_colors:
            self.set_random_colors(doc.layers)
        else:
            self.set_mapsys_colors(doc.layers)
        self.set_line_weights(doc.layers)

        # Zoom to extents to make the content visible by default.
        zoom.extents(msp)

        # Save the result if a path was provided.
        if dxf_path is not None:
            # Rotate existing DXF backups before overwriting the file.
            self._rotate_dxf_backups(dxf_path, max_backups=10)
            doc.saveas(dxf_path.as_posix())
            if self.open_after_save:
                os.startfile(dxf_path.as_posix())

        return doc

    def insert_points(self, block_exists: bool, msp: "Layout") -> set[str]:
        """Insert points into the DXF file.

        Args:
            block_exists: Whether the point block exists in the template.
            msp: The modelspace.

        Returns:
            The set of added layer names.
        """
        added_layers = set()
        for pt in self.mapsys.points:
            insert = (float(pt.east), float(pt.north))
            if block_exists:
                ly_name = self.layer_name(
                    pt.layer,
                    suffix=(
                        POINT_SUFFIX if self.segregate_by_object_type else ""
                    ),
                )
                added_layers.add(ly_name)
                br = msp.add_blockref(
                    self.point_block,
                    insert,
                    dxfattribs={
                        "xscale": self.block_scale,
                        "yscale": self.block_scale,
                        "rotation": BLOCK_ROTATION,
                        "layer": ly_name,
                    },
                )
                to_set = {}
                if self.point_name_attrib:
                    to_set[self.point_name_attrib] = str(pt.pt_nr)
                if self.point_source_attrib:
                    to_set[self.point_source_attrib] = BLOCK_SOURCE
                if self.point_z_attrib:
                    to_set[self.point_z_attrib] = f"{pt.z:.2f}"
                if to_set:
                    br.add_auto_attribs(to_set)
            else:
                # Fallback symbol when the block is missing in the template.
                msp.add_circle(center=insert, radius=0.2)
                msp.add_text(
                    str(pt.pt_nr),
                    dxfattribs={"height": ATTRIB_HEIGHT, "insert": insert},
                )
        return added_layers

    def insert_lines(self, msp: "Layout") -> set[str]:
        """Insert poly-lines into the DXF file.

        Args:
            msp: The modelspace.

        Returns:
            The set of added layer names.
        """
        added_layers = set()
        ar_list: list[Ar5Data] = self.mapsys.p_meta
        verticels: list[int] = self.mapsys.v_offsets
        points: list[No5Coord] = self.mapsys.points

        # Generate LWPolylines based on AR5/AS5 mapping to NO5 points.
        for ar, verts in self._iter_poly_vertices(ar_list, verticels, points):
            try:
                closed = 0
                if len(verts) >= 2 and verts[0] == verts[-1]:
                    closed = 1
                    verts = verts[:-1]

                # Get the layer.
                ly_index = self.mapsys.get_poly_layer(ar)
                ly_name = self.layer_name(
                    ly_index,
                    suffix=LINE_SUFFIX
                    if self.segregate_by_object_type
                    else "",
                )
                added_layers.add(ly_name)

                # Add the polyline.
                msp.add_lwpolyline(
                    verts,
                    format="xy",
                    dxfattribs={
                        "closed": closed,
                        "layer": ly_name,
                    },
                )
            except Exception as e:
                logger.exception(
                    "Failed adding LWPolyline with %d vertices: %s",
                    len(verts),
                    e,
                )
                continue
        return added_layers

    def insert_texts(self, msp: "Layout") -> set[str]:
        """Insert text entities into the DXF file.

        Args:
            msp: The modelspace.

        Returns:
            The set of added layer names.
        """
        added_layers = set()

        for text in self.mapsys.t_meta:
            string = self.mapsys.text_by_offset(text.offset)
            if string is None:
                logger.warning("Text not found for offset %d", text.offset)
                continue

            ly_name = self.layer_name(
                text.layer,
                suffix=TEXT_SUFFIX if self.segregate_by_object_type else "",
            )
            added_layers.add(ly_name)
            msp.add_text(
                string,
                dxfattribs={
                    "height": text.height,
                    "insert": (float(text.east), float(text.north)),
                    "rotation": math.degrees(text.direction),
                    "layer": ly_name,
                },
            )

        return added_layers

    @staticmethod
    def set_random_colors(layers: "LayerTable") -> None:
        """Set the color of the DXF layers to random colors.

        Args:
            layers: The layer table.
        """
        # Define a list of AutoCAD color indices to use (1–255 range)
        # We'll skip grayscale-like colors and neutral tones.
        # Common bright, distinct colors.
        valid_colors = [
            1,
            2,
            3,
            4,
            5,
            6,
            10,
            12,
            14,
            21,
            23,
            25,
            30,
            33,
            41,
            43,
            50,
            52,
            60,
            70,
            80,
            90,
            100,
            110,
            120,
            130,
            140,
            150,
            160,
            170,
            180,
            190,
            200,
            210,
            220,
            230,
            240,
            250,
            253,
            254,
            255,
        ]

        # We'll reuse colors from the list if we run out.
        available_colors = valid_colors.copy()

        for layer in layers:
            if layer.dxf.name == "0":
                continue

            if not available_colors:  # Refill if we run out
                available_colors = valid_colors.copy()

            color = available_colors.pop(0)  # Take next color
            layer.dxf.color = color
            if hasattr(layer.dxf, "true_color"):
                layer.dxf.true_color = None

    def set_mapsys_colors(self, layers: "LayerTable") -> None:
        """Set the color for each layer from the MapSys PR5 data.

        Args:
            layers: The layer table.
        """
        for layer in layers:
            if not layer.dxf.name.startswith(f"{LAYER_PREFIX}-"):
                continue
            parts = layer.dxf.name.split("-")
            src_layer = int(parts[1])
            assert self.mapsys.pr5 is not None
            if src_layer < 0 or src_layer >= len(self.mapsys.pr5.layers):
                logger.warning("Invalid source layer index: %d", src_layer)
                continue
            set_layer_color_from_index(
                layer, self.mapsys.pr5.layers[src_layer].color
            )

    def set_line_weights(self, layers: "LayerTable") -> None:
        """Set the lineweight for each layer from the MapSys PR5 data.

        Args:
            layers: The layer table.
        """
        for layer in layers:
            if not layer.dxf.name.startswith(f"{LAYER_PREFIX}-"):
                continue

            parts = layer.dxf.name.split("-")
            src_layer = int(parts[1])
            assert self.mapsys.pr5 is not None
            if src_layer < 0 or src_layer >= len(self.mapsys.pr5.layers):
                logger.warning("Invalid source layer index: %d", src_layer)
                continue

            # Source weight is in range 0-255
            layer.dxf.lineweight = self.lineweight_from_mapsys(
                self.mapsys.pr5.layers[src_layer].weight
            )

    @staticmethod
    def lineweight_from_mapsys(value: int) -> int:
        """Map a MapSys line-weight in [0, 255] range to a DXF constant.

        Args:
            value: MapSys line-weight in [0, 255] range.

        Returns:
            The corresponding DXF lineweight constant.

        Throws:
            TypeError: If ``value`` is not an ``int``.
            ValueError: If ``value`` is outside the ``[0, 255]`` range.
        """
        if not isinstance(value, int):
            raise TypeError(
                f"value must be int in [0, 255], got {type(value).__name__}"
            )
        if value < 0 or value > 255:
            raise ValueError(f"value must be in [0, 255], got {value}")

        if 0 <= value <= 1:
            return VALID_DXF_LINEWEIGHTS[1]
        elif value == 2:
            return VALID_DXF_LINEWEIGHTS[4]
        elif value == 3:
            return VALID_DXF_LINEWEIGHTS[8]
        else:
            value -= 4
            to_split = VALID_DXF_LINEWEIGHTS[9:]

            n = len(to_split)
            bin_index = (value * n) // 253
            return to_split[bin_index]
