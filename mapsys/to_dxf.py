"""DXF export utilities.

This module provides a function that converts parsed ``mapsys`` content into a
DXF file by using a template DXF. It inserts block references for all points
and generates polylines based on AR5/AS5 indices.

"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path

# Internal knowledge of NO5 structure sizes to decode AS5 offsets.
# Keep here to avoid importing private symbols from the parser module.
from struct import Struct
from typing import TYPE_CHECKING, Iterable

from ezdxf.document import Drawing

from mapsys.ar5_polys import Ar5Data
from mapsys.n05_points import No5Coord

if TYPE_CHECKING:
    from mapsys.content import Content


logger = logging.getLogger(__name__)


_NO5_HEADER_STRUCT = Struct("<4s6IB")
_NO5_COORD_STRUCT = Struct("<BIBIddfIB")

BLOCK_SOURCE = "MapSys"
BLOCK_ROTATION = 0.0
ATTRIB_HEIGHT = 0.25


def _offset_to_point_index(offset: int) -> int | None:
    """Translate a byte ``offset`` into a zero-based index in the NO5 table.

    The AS5 file stores byte offsets that point into the NO5 coordinates table.
    Those offsets are measured from the start of the NO5 file. The coordinates
    table starts immediately after the NO5 header. Each record has a fixed
    size, so the index can be computed by subtracting the header size and
    dividing by the record size.

    Args:
        offset: Byte offset inside the NO5 file.

    Returns:
        The zero-based record index, or ``None`` if the offset is invalid.
    """

    header_size = _NO5_HEADER_STRUCT.size
    record_size = _NO5_COORD_STRUCT.size

    # Guard against offsets smaller than the header.
    if offset < header_size:
        return None

    relative = offset - header_size

    # Ensure the offset aligns to the record boundary.
    if relative % record_size != 0:
        return None

    return relative // record_size


def _iter_poly_vertices(
    ar: Iterable[Ar5Data],
    as5_offsets: list[int],
    points: list[No5Coord],
) -> Iterable[list[tuple[float, float]]]:
    """Yield vertex lists for each polyline described by AR5/AS5 tables.

    Args:
        ar: Parsed AR5 entries (one per polyline).
        as5_offsets: Offsets table from AS5 (byte offsets into NO5 data).
        points: Parsed NO5 coordinates list.

    Yields:
        Lists of ``(x, y)`` pairs for each line that has at least two points.
    """

    num_offsets = len(as5_offsets)
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
        for off in as5_offsets[start:end]:
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
            yield vertices


def mapsys_to_dxf(
    mapsys: "Content",
    dxf_template: Path,
    *,
    dxf_path: Path | None = None,
    point_block: str = "POINT",
    point_name_attrib: str = "NAME",
    point_source_attrib: str = "SOURCE",
    point_z_attrib: str = "Z",
    block_scale: float = 1.0,
) -> Drawing:
    """Create a DXF document from parsed ``mapsys`` content.

    The function loads a template DXF, inserts a block reference for every
    point with its name (``point_name_attrib``) set to the point number, and
    draws polylines derived from the AR5/AS5 indices.

    Args:
        mapsys: Parsed content (``Content``) holding points and polyline data.
        dxf_template: Path to the template DXF file to load.
        dxf_path: Optional path to save the resulting DXF.
        point_block: Name of the block used for point symbols.
        point_name_attrib: Attribute tag used to store the point name/number.
        point_source_attrib: Attribute tag used to store the point source.
        point_z_attrib: Attribute tag used to store the point z.
    Returns:
        The in-memory DXF document instance.
    """

    # Load DXF template into memory.
    # Prefer recover.readfile() for robust loading of DXF files.
    from ezdxf import recover as _recover  # local import to appease linters

    # Use recover.readfile() for robust DXF loading.
    doc, _auditor = _recover.readfile(dxf_template.as_posix())
    msp = doc.modelspace()

    # Extract data from the content object using duck typing.
    points: list[No5Coord] = mapsys.points
    ar_list: list[Ar5Data] = mapsys.p_meta
    as5_offsets: list[int] = mapsys.v_offsets

    # Insert a block for each point with the NAME attribute set.
    block_exists = point_block in doc.blocks
    if not block_exists:
        logger.warning(
            (
                "Block '%s' not found in template; points will be drawn "
                "as circles"
            ),
            point_block,
        )
    else:
        attributes = set()
        for attdef in doc.blocks[point_block].query("ATTDEF"):
            attributes.add(attdef.dxf.tag)
        if point_name_attrib not in attributes:
            logger.warning(
                (
                    "Attribute '%s' not found in block '%s'; points will be "
                    "drawn with no name attribute"
                ),
                point_name_attrib,
                point_block,
            )
            point_name_attrib = ""
        if point_source_attrib not in attributes:
            logger.warning(
                (
                    "Attribute '%s' not found in block '%s'; points will be "
                    "drawn with no source attribute"
                ),
                point_source_attrib,
                point_block,
            )
            point_source_attrib = ""
        if point_z_attrib not in attributes:
            logger.warning(
                (
                    "Attribute '%s' not found in block '%s'; points will be "
                    "drawn with no z attribute"
                ),
                point_z_attrib,
                point_block,
            )
            point_z_attrib = ""
    for pt in points:
        insert = (float(pt.east), float(pt.north))
        if block_exists:
            br = msp.add_blockref(
                point_block,
                insert,
                dxfattribs={
                    "xscale": block_scale,
                    "yscale": block_scale,
                    "rotation": BLOCK_ROTATION,
                    "layer": f"Mapsys-{pt.layer}",
                },
            )
            to_set = {}
            if point_name_attrib:
                to_set[point_name_attrib] = str(pt.pt_nr)
            if point_source_attrib:
                to_set[point_source_attrib] = BLOCK_SOURCE
            if point_z_attrib:
                to_set[point_z_attrib] = f"{pt.z:.2f}"
            if to_set:
                br.add_auto_attribs(to_set)
        else:
            # Fallback symbol when the block is missing in the template.
            msp.add_circle(center=insert, radius=0.2)
            msp.add_text(
                str(pt.pt_nr),
                dxfattribs={"height": ATTRIB_HEIGHT, "insert": insert},
            )

    # Generate LWPolylines based on AR5/AS5 mapping to NO5 points.
    for verts in _iter_poly_vertices(ar_list, as5_offsets, points):
        try:
            closed = 0
            if len(verts) >= 2 and verts[0] == verts[-1]:
                closed = 1
                verts = verts[:-1]

            msp.add_lwpolyline(
                verts, format="xy", dxfattribs={"closed": closed}
            )
        except Exception as e:
            logger.exception(
                "Failed adding LWPolyline with %d vertices: %s",
                len(verts),
                e,
            )
            continue

    for text in mapsys.t_meta:
        string = mapsys.text_by_offset(text.offset)
        if string is None:
            logger.warning("Text not found for offset %d", text.offset)
            continue
        msp.add_text(
            string,
            dxfattribs={
                "height": text.height,
                "insert": (float(text.east), float(text.north)),
                "rotation": math.degrees(text.direction),
                "layer": f"Mapsys-{text.layer}",
                # "font": text.font,
                # "align": text.align_east,
                # "align2": text.align_north,
            },
        )

    # Save the result if a path was provided.
    if dxf_path is not None:
        doc.saveas(dxf_path.as_posix())
        os.startfile(dxf_path.as_posix())

    return doc
