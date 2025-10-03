import logging
import struct
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# Target coordinates (X, Y) known to exist in the project
TARGET_COORDS: Tuple[float, float] = (574261.870, 549855.240)


def _find_all(data: bytes, needle: bytes) -> List[int]:
    """Find all occurrences of needle in data, returning byte offsets."""
    hits: List[int] = []
    start = 0
    n = len(needle)
    if n == 0:
        return hits
    while True:
        idx = data.find(needle, start)
        if idx == -1:
            break
        hits.append(idx)
        start = idx + 1
    return hits


def _read_f64le(data: bytes, off: int) -> float | None:
    if 0 <= off and off + 8 <= len(data):
        return struct.unpack_from("<d", data, off)[0]
    return None


def scan_file_for_known_coords(
    file_path: Path | str,
    data: bytes,
    coords: Tuple[float, float] = TARGET_COORDS,
    pair_window: int = 1000,
) -> List[Dict[str, object]]:
    """Scan for known coordinates using f64-le and return all pairs/triples.

    Returns a list of dicts with keys like:
      - kind: 'pair' | 'triple'
      - x_off, y_off, delta
      - order: 'XY' | 'YX'
      - z_off (for triples) and z_val
    """
    fname = str(file_path)
    x_val, y_val = coords
    x_bytes = struct.pack("<d", x_val)
    y_bytes = struct.pack("<d", y_val)

    logger.debug(
        "Investigating %s for coords (f64-le) %.6f, %.6f", fname, x_val, y_val
    )

    x_offs = sorted(_find_all(data, x_bytes))
    y_offs = sorted(_find_all(data, y_bytes))

    if not x_offs and not y_offs:
        logger.debug("%s: no f64-le hits for the targets", fname)
        return []

    results: List[Dict[str, object]] = []

    # Produce all pairs with |dx| <= pair_window
    for xo in x_offs:
        # We could binary-search y_offs; simple sweep suffices for typical sizes
        for yo in y_offs:
            delta = yo - xo
            ad = abs(delta)
            if ad == 0:
                continue
            if ad <= pair_window:
                order = "XY" if xo < yo else "YX"
                results.append(
                    {
                        "kind": "pair",
                        "x_off": xo,
                        "y_off": yo,
                        "delta": ad,
                        "order": order,
                    }
                )

                # Try to account for a potential Z to form a triple
                start = min(xo, yo)
                end = max(xo, yo)
                diff = end - start
                # Case 1: exactly one f64 between X and Y
                if diff == 16:
                    z_off = start + 8
                    z_val = _read_f64le(data, z_off)
                    if z_val is not None:
                        results.append(
                            {
                                "kind": "triple",
                                "x_off": xo,
                                "y_off": yo,
                                "z_off": z_off,
                                "z_val": z_val,
                                "order": order,
                            }
                        )
                # Case 2: contiguous X and Y; Z may be adjacent before/after
                elif diff == 8:
                    # After
                    z_after = end + 8
                    zv = _read_f64le(data, z_after)
                    if zv is not None:
                        results.append(
                            {
                                "kind": "triple",
                                "x_off": xo,
                                "y_off": yo,
                                "z_off": z_after,
                                "z_val": zv,
                                "order": order + "+Zafter",
                            }
                        )
                    # Before
                    z_before = start - 8
                    zv = _read_f64le(data, z_before)
                    if zv is not None:
                        results.append(
                            {
                                "kind": "triple",
                                "x_off": xo,
                                "y_off": yo,
                                "z_off": z_before,
                                "z_val": zv,
                                "order": order + "+Zbefore",
                            }
                        )

    # Log a concise summary and return full list to caller for printing
    logger.info(
        "%s: Found %d candidate pairs/triples within %d bytes (f64-le)",
        fname,
        len(results),
        pair_window,
    )
    return results


def scan_and_report(
    file_path: Path | str,
    data: bytes,
    coords: Tuple[float, float] = TARGET_COORDS,
    pair_window: int = 1000,
) -> None:
    """Run scan and print a readable list of all results."""
    res = scan_file_for_known_coords(
        file_path, data, coords=coords, pair_window=pair_window
    )
    if not res:
        return
    fname = str(file_path)
    print(f"{fname}: results (f64-le, window={pair_window})")
    for item in res:
        kind = item["kind"]
        if kind == "pair":
            order = item.get("order")
            xo = item["x_off"]
            yo = item["y_off"]
            delta = item["delta"]
            print(f"  pair {order}: X@{xo:#x}, Y@{yo:#x}, delta={delta}")
        elif kind == "triple":
            order = item.get("order")
            xo = item["x_off"]
            yo = item["y_off"]
            zo = item["z_off"]
            zv = item["z_val"]
            print(
                f"  triple {order}: X@{xo:#x}, Y@{yo:#x}, Z@{zo:#x} = {zv:.6f}"
            )

    # After finding at least one pair, try to infer structure sizes
    sizes = infer_structure_sizes(
        file_path,
        data,
        coords=coords,
        pair_window=pair_window,
        value_tol=1000.0,
    )
    if sizes:
        print(f"{fname}: inferred structure sizes (first-next pair stride)")
        for s in sizes:
            base = s["base_start"]
            nxt = s.get("next_start")
            stride = s.get("stride")
            order_b = s.get("base_order")
            order_n = s.get("next_order")
            note = "" if nxt is not None else " (next pair not found)"
            if nxt is not None and stride is not None:
                nx = s.get("next_x")
                ny = s.get("next_y")
                print(
                    f"  base@{base:#x} {order_b} -> next@{nxt:#x} {order_n} stride={stride} "
                    f"values=({nx:.3f}, {ny:.3f}){note}"
                )
            else:
                print(f"  base@{base:#x} {order_b}{note}")


def _find_candidate_pairs(
    data: bytes, coords: Tuple[float, float], pair_window: int
) -> List[Dict[str, int | str]]:
    x_val, y_val = coords
    x_bytes = struct.pack("<d", x_val)
    y_bytes = struct.pack("<d", y_val)
    x_offs = sorted(_find_all(data, x_bytes))
    y_offs = sorted(_find_all(data, y_bytes))
    pairs: List[Dict[str, int | str]] = []
    for xo in x_offs:
        for yo in y_offs:
            ad = abs(yo - xo)
            if ad == 0 or ad > pair_window:
                continue
            order = "XY" if xo < yo else "YX"
            start = min(xo, yo)
            pairs.append(
                {"start": start, "x_off": xo, "y_off": yo, "order": order}
            )
    pairs.sort(key=lambda p: int(p["start"]))
    # Deduplicate by start offset (keep first instance)
    dedup: Dict[int, Dict[str, int | str]] = {}
    for p in pairs:
        s = int(p["start"])
        if s not in dedup:
            dedup[s] = p
    return list(dedup.values())


def _near_pair(
    a: float, b: float, x: float, y: float, tol: float
) -> tuple[bool, str]:
    if abs(a - x) <= tol and abs(b - y) <= tol:
        return True, "XY"
    if abs(a - y) <= tol and abs(b - x) <= tol:
        return True, "YX"
    return False, ""


def infer_structure_sizes(
    file_path: Path | str,
    data: bytes,
    coords: Tuple[float, float],
    pair_window: int = 1000,
    value_tol: float = 1000.0,
) -> List[Dict[str, int | str | float | None]]:
    """For each located pair, scan forward byte-by-byte to next near pair.

    The returned list contains entries with keys:
      - base_start, base_order
      - next_start, next_order (if found)
      - stride (if found)
      - z_off, z_val (if triple adjacent to the next pair)
    """
    fname = str(file_path)
    pairs = _find_candidate_pairs(data, coords, pair_window)
    if not pairs:
        logger.debug("%s: no base pairs to infer structure size from", fname)
        return []

    x_val, y_val = coords
    results: List[Dict[str, int | str | float | None]] = []
    for p in pairs:
        base_start = int(p["start"])
        base_order = str(p["order"])
        found: Dict[str, int | str | float | None] | None = None
        pos = base_start + 1
        end_limit = len(data) - 16  # need at least two doubles
        while pos <= end_limit:
            a = _read_f64le(data, pos)
            b = _read_f64le(data, pos + 8)
            if a is None or b is None:
                break
            ok, order = _near_pair(a, b, x_val, y_val, value_tol)
            if ok:
                found = {
                    "base_start": base_start,
                    "base_order": base_order,
                    "next_start": pos,
                    "next_order": order,
                    "stride": pos - base_start,
                    "next_x": a if order == "XY" else b,
                    "next_y": b if order == "XY" else a,
                }
                # Try Z adjacent to the next pair
                z_off = pos + 16
                if z_off + 8 <= len(data):
                    z_val = _read_f64le(data, z_off)
                    if z_val is not None:
                        found["z_off"] = z_off
                        found["z_val"] = z_val
                break
            pos += 1

        if not found:
            found = {
                "base_start": base_start,
                "base_order": base_order,
                "next_start": None,
                "next_order": None,
                "stride": None,
            }
        results.append(found)

    return results
