"""High-level content loader for MapSys companion files.

This module orchestrates loading and preprocessing of the various files that
share the same base name as the selected MapSys file. It provides a
``Content`` value object that aggregates parsed data from multiple VA50
binary tables (e.g., NO5 points, TS5 text store, TE5 text metadata, AR5/AL5
polyline tables) as well as a few text- and CSV-based sidecar files.

Design overview:

- The ``preprocess`` decorator encapsulates the common boilerplate of
  locating the companion file, reading it in the appropriate mode, and
  adapting the raw bytes or text lines to the handler's expected input.
- Each ``process_*`` method parses a specific file type and stores the
  results on the ``Content`` instance.
- ``Content.create`` collects all non-empty sibling files that share the same
  stem with ``main_file`` and invokes all processors in a fixed order.

Logging is used throughout to keep the code side-effect free while still
surfacing diagnostics (missing files, empty files, decoding problems, etc.).

The loader favors robustness and isolation: individual processors are allowed
to fail without taking down the entire loading pipeline. For example, if an
optional sidecar is missing, the decorator will log and return early rather
than raising.
"""

import csv
import logging
from enum import StrEnum
from functools import wraps
from pathlib import Path
from typing import Any

from attrs import define, field

from mapsys.parser.al5_poly_layer import Al5Data, parse_al5
from mapsys.parser.ar5_polys import Ar5Data, parse_ar5
from mapsys.parser.as5_vertices import parse_as5
from mapsys.parser.mdb_support import extract_access_db
from mapsys.parser.n05_points import No5Coord, parse_no5
from mapsys.parser.pr5_main import Pr5File, parse_pr5
from mapsys.parser.te5_text_meta import Te5TextMeta, parse_te5
from mapsys.parser.ts5_text_store import Ts5Text, parse_ts5

logger = logging.getLogger(__name__)


class PrepModels(StrEnum):
    """Input modes understood by the ``preprocess`` decorator."""

    TEXT_LINES = "text-lines"
    VA50 = "va50"
    CSV = "csv"
    UNKNOWN = "unknown"
    MDB = "mdb"
    ASSIGN = "assign"


def preprocess(name: str, mode: str) -> Any:
    """Decorator that injects companion file content into a handler.

    The decorator looks up a sibling file based on ``name`` (e.g., ``"no5"``),
    reads it using a strategy determined by ``mode``, and then calls the
    wrapped ``process_*`` method with the prepared content.

    - ``TEXT_LINES``: open as UTF-8 text and pass a list of lines
    - ``CSV``: open as UTF-8 text and pass a CSV row iterator
    - ``ASSIGN``: open as UTF-8 text and pass a ``dict`` built from ``k=v``
      lines
    - ``VA50``: open as binary and pass raw bytes
    - ``UNKNOWN``: open as binary and pass raw bytes unchanged
    - ``MDB``: call ``extract_access_db`` and pass a ``dict`` of tables

    Args:
        name: Lowercase file key without dot (e.g., ``"no5"``).
        mode: One of :class:`PrepModels` determining how the file is read.

    Returns:
        A decorator that wraps a ``process_*`` method to auto-supply content.

    Throws:
        No exception is raised for missing or empty files; these are logged
        and the wrapped function is not called. For MDB extraction, any
        exception from the extractor is logged and suppressed as well.
    """

    def decorator(func: Any) -> Any:
        @wraps(func)
        def wrapper(self: "Content", content: Any = None) -> None:
            logger.debug("Preprocessing %s in %s mode", name, mode)
            file_path = self.files.get(name.upper())
            if file_path is None:
                logger.error("File %s not found", name)
                return

            if mode == PrepModels.MDB:
                try:
                    content = extract_access_db(str(file_path))
                    return func(self, content)
                except Exception:
                    logger.exception(
                        "Failed to extract content from %s", file_path
                    )
                    return

            text_mode = mode in (
                PrepModels.TEXT_LINES,
                PrepModels.CSV,
                PrepModels.ASSIGN,
            )

            with open(
                file_path,
                "r" if text_mode else "rb",
                encoding="utf-8" if text_mode else None,
            ) as f:
                content = f.read()
            if len(content) == 0:
                logger.error("File %s is empty", name)
                return

            if mode == PrepModels.TEXT_LINES:
                content = content.splitlines()
            elif mode == PrepModels.CSV:
                content = csv.reader(content.splitlines())
            elif mode == PrepModels.VA50:
                # Pass raw bytes to the handler for VA50 formats (e.g., NO5)
                pass
            elif mode == PrepModels.UNKNOWN:
                # Unknown: pass raw bytes and let the handler decide
                pass
            elif mode == PrepModels.ASSIGN:
                result = {}
                for ln in content.splitlines():
                    assert "=" in ln, (
                        f"Line {ln} does not contain an equal sign"
                    )
                    key, value = ln.split("=")
                    result[key] = value
                content = result
            else:
                assert False, f"Unknown mode: {mode}"

            return func(self, content)

        return wrapper

    return decorator


@define
class Content:
    """Aggregated content parsed from MapSys companion files.

    Attributes:
        main_file: The user-selected file used to derive the file stem.
        files: Mapping of uppercase extensions (e.g., ``"NO5"``) to paths of
            discovered non-empty sibling files.
        points: Parsed NO5 point records.
        texts: Parsed TS5 text entries.
        t_meta: Parsed TE5 text metadata entries.
        p_meta: Parsed AR5 polyline metadata entries.
        v_offsets: Parsed AS5 vertex offsets list.
        p_layers: Parsed AL5 per-poly layer records.
        pr5: Parsed PR5 file structure if present, otherwise ``None``.
        offset_to_text: Internal cache mapping TS5 offsets to strings used by
            :meth:`text_by_offset`.
    """

    main_file: Path
    files: dict[str, Path]

    points: list["No5Coord"] = field(factory=list)
    texts: list["Ts5Text"] = field(factory=list)
    t_meta: list["Te5TextMeta"] = field(factory=list)
    p_meta: list["Ar5Data"] = field(factory=list)
    v_offsets: list[int] = field(factory=list)
    p_layers: list["Al5Data"] = field(factory=list)
    pr5: "Pr5File | None" = field(default=None)

    offset_to_text: dict[int, str] = field(factory=dict, init=False)

    def text_by_offset(self, offset: int) -> str | None:
        """Return the TS5 string stored at ``offset``.

        Builds a cache on first use from ``self.texts``. Offsets are relative
        to the beginning of the TS5 string block (i.e., right after the TS5
        header), matching the values referenced by TE5 metadata.

        Args:
            offset: String-block-relative byte offset.

        Returns:
            The decoded string if present, otherwise ``None``.
        """
        if not self.offset_to_text:
            for text in self.texts:
                self.offset_to_text[text.offset] = text.text
        return self.offset_to_text.get(offset, None)

    def get_poly_layer(self, p_meta: "Ar5Data") -> int:
        """Resolve the display layer for an AR5 polyline record.

        Falls back to ``0`` if the ``lay_rec`` index is outside the bounds of
        the available AL5 records. Otherwise returns the ``layer`` value from
        the corresponding AL5 entry.

        Args:
            p_meta: One AR5 record.

        Returns:
            Layer index (0..255). Values are asserted to be in range.
        """
        if p_meta.lay_rec < 0 or p_meta.lay_rec >= len(self.p_layers):
            return 0
        result = self.p_layers[p_meta.lay_rec].layer
        assert 0 <= result <= 255, f"Invalid poly layer index: {result}"
        return result

    @preprocess("al5", mode=PrepModels.VA50)
    def process_al5(self, content: Any = None) -> None:
        """AL5: per-poly layer table with 3-byte records.

        Args:
            content: Raw bytes of an AL5 VA50 file.

        Returns:
            None. Populates ``self.p_layers``.
        """
        if isinstance(content, (bytes, bytearray)):
            _, items = parse_al5(bytes(content))
            self.p_layers = items
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("app", mode=PrepModels.TEXT_LINES)
    def process_app(self, content: Any = None) -> None:
        """Was always empty."""
        pass

    @preprocess("ar5", mode=PrepModels.VA50)
    def process_ar5(self, content: Any = None) -> None:
        """AR5: polyline table.

        Args:
            content: Raw bytes of an AR5 VA50 file.

        Returns:
            None. Populates ``self.p_meta``.
        """
        if isinstance(content, (bytes, bytearray)):
            _, self.p_meta = parse_ar5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("as5", mode=PrepModels.VA50)
    def process_as5(self, content: Any = None) -> None:
        """The offset of each point of the polylines. The start and length are
        stored in the AR table.

        #pragma endian little
        #pragma magic [56 53 35 30] @ 0x00  // "VA50" at offset 0

        import std.mem;

        struct Header {
            char signature[4];      // "VA50"
            u32  int1[5];
            u8 pad;
        };

        struct VA50File {
            Header head;
            u32 data[while (!std::mem::eof())];
        };

        VA50File file @ 0x00;

        Args:
            content: Raw bytes of an AS5 VA50/VA50 file.

        Returns:
            None. Populates ``self.v_offsets``.
        """
        if isinstance(content, (bytes, bytearray)):
            _, self.v_offsets = parse_as5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("at5", mode=PrepModels.VA50)
    def process_at5(self, content: Any = None) -> None:
        """The data section seems to be a list of 3-byte records.

        In a small file it was header-only.

        ```
        #pragma endian little
        #pragma magic [56 53 35 30] @ 0x00  // "VA50" at offset 0

        import std.mem;

        struct Data {
            u8 first; // 0, 2, 9, 255
            u8 second; // 0-255
            u8 third; // 0-255
        };


        struct Header {
            char signature[4];      // "VA50"
            u8 unk;
            u32 pad[4];
        };

        struct VA50File {
            Header head;
            Data data[while (!std::mem::eof())];
        };

        VA50File file @ 0x00;
        ```
        """
        pass

    @preprocess("crs", mode=PrepModels.TEXT_LINES)
    def process_crs(self, content: Any = None) -> None:
        """The one that I've found looked like this:

        2018-02-09 15:37 Stereografic 1970 - ANCPI-S-42, Creare Lucrare
        """
        pass

    @preprocess("csi", mode=PrepModels.CSV)
    def process_csi(self, content: Any = None) -> None:
        """
        2,Krassovsky,6378245.000,6356863.019
        4,ANCPI-S-42,2,2.329,-147.042,-92.080,0.309248,-0.324822,-0.497299,5.689063
        1,Stereografic,1
        1,Stereografic 1970,1,46.000000000,25.000000000,
        500000.000000000,500000.000000000,0.999750000,0.000000000,
        0.000000000,0.000000000,0.000000000,0.000000000
        2,EGG97-European Gravimetric Geoid 1997
        2,Stereo 70
        2,Stereografic 1970 - ANCPI-S-42,2,3,4,1,2
        46.665934915,25.615484176,0.000,0.000,0.000,0.000
        """
        pass

    @preprocess("del", mode=PrepModels.TEXT_LINES)
    def process_del(self, content: Any = None) -> None:
        pass

    @preprocess("dts", mode=PrepModels.UNKNOWN)
    def process_dts(self, content: Any = None) -> None:
        pass

    @preprocess("ead", mode=PrepModels.TEXT_LINES)
    def process_ead(self, content: Any = None) -> None:
        pass

    @preprocess("ims", mode=PrepModels.TEXT_LINES)
    def process_ims(self, content: Any = None) -> None:
        pass

    @preprocess("jlk", mode=PrepModels.TEXT_LINES)
    def process_jlk(self, content: Any = None) -> None:
        pass

    @preprocess("lgn", mode=PrepModels.TEXT_LINES)
    def process_lgn(self, content: Any = None) -> None:
        pass

    @preprocess("lgs", mode=PrepModels.TEXT_LINES)
    def process_lgs(self, content: Any = None) -> None:
        pass

    @preprocess("mdb", mode=PrepModels.MDB)
    def process_mdb(self, content: Any = None) -> None:
        pass

    @preprocess("mei", mode=PrepModels.ASSIGN)
    def process_mei(self, content: Any = None) -> None:
        pass

    @preprocess("no5", mode=PrepModels.VA50)
    def process_no5(self, content: Any = None) -> None:
        """NO5: points table.

        Args:
            content: Raw bytes of a NO5 VA50 file.

        Returns:
            None. Populates ``self.points``.
        """
        if isinstance(content, (bytes, bytearray)):
            _, self.points = parse_no5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("ns5", mode=PrepModels.VA50)
    def process_ns5(self, content: Any = None) -> None:
        """Either a four-byte list of numbers or a 4-byte structure.

        In a small file there were 6 records, all of them 1.

        In a large file all but the fourth byte were non-null.
        """
        pass

    @preprocess("ol5", mode=PrepModels.UNKNOWN)
    def process_ol5(self, content: Any = None) -> None:
        pass

    @preprocess("pr5", mode=PrepModels.UNKNOWN)
    def process_pr5(self, content: Any = None) -> None:
        """PR5: main project file.

        Args:
            content: Raw bytes of a PR5 file.

        Returns:
            None. Populates ``self.pr5``.
        """
        if isinstance(content, (bytes, bytearray)):
            self.pr5 = parse_pr5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("prj", mode=PrepModels.TEXT_LINES)
    def process_prj(self, content: Any = None) -> None:
        pass

    @preprocess("pxt", mode=PrepModels.ASSIGN)
    def process_pxt(self, content: Any = None) -> None:
        pass

    @preprocess("qs5", mode=PrepModels.VA50)
    def process_qs5(self, content: Any = None) -> None:
        """Array of two value. First is a byte that can be 1, 2 or 4.
        Second is 32 bit integer that may be an offset or ID. Starts at 1
        and same value can show up multiple times, but the combination seems
        to be unique.
        """
        pass

    @preprocess("qt5", mode=PrepModels.VA50)
    def process_qt5(self, content: Any = None) -> None:
        """
        In a short file the table contained 6 records.

        Each record seems to be 14 bytes long. The data seem to have
        a double pair at the top but other than that found few real numbers.
        The bytes 9+10 seem to form an ever increasing number. The difference
        between these values are between 0 and 121. There are, however, quite a
        few numbers that appear two or more times, with the differentiator
        being the first byte.

        ```
        #pragma endian little
        #pragma magic [56 53 35 30] @ 0x00  // "VA50" at offset 0

        import std.mem;

        struct Header {
            char signature[4];      // "VA50"
            u32  int1[4];
            u8 pad;
            char signature2[5];      // "QT50"
            u8 pad2[15];
        };


        struct Data {
            u8 unk01; // 0 - 255
            u8 unk02; // Not all values used, possibly flags
            u8 unk03; // Not all values used, possibly flags
            u8 unk04; // Not all values used, possibly flags
            u8 unk05; // 0 - 255

            u8 unk06; // 0, 1, 2, 4, 7, 8, 15, 16, 31, 32, 33, 63, 64
            u8 unk07; // 0 - 255
            u8 unk08; // 0, 1, 2, 4, 7, 8, 15, 16, 31, 32, 33, 63, 64
            u16 unk09; // 0 - 255, increasing
            // u8 unk10; // 0 - 255
            u8 unk11; // 0, 1, 2, 5, 114
            u8 unk12; // Vast majority 0. Saw a 2.
            u8 unk13; // 0 - 254
            u8 unk14; // 0 or 1. Vast majority 0
        };


        struct VA50File {
            Header head;
            Data data[while (!std::mem::eof())];
        };

        VA50File file @ 0x00;
        ```
        """
        pass

    @preprocess("ral", mode=PrepModels.TEXT_LINES)
    def process_ral(self, content: Any = None) -> None:
        pass

    @preprocess("ref", mode=PrepModels.TEXT_LINES)
    def process_ref(self, content: Any = None) -> None:
        pass

    @preprocess("te5", mode=PrepModels.VA50)
    def process_te5(self, content: Any = None) -> None:
        """TE5: text metadata without the actual string.

        Args:
            content: Raw bytes of a TE5 VA50 file.

        Returns:
            None. Populates ``self.t_meta``.
        """
        if isinstance(content, (bytes, bytearray)):
            _, self.t_meta = parse_te5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("thl", mode=PrepModels.TEXT_LINES)
    def process_thl(self, content: Any = None) -> None:
        pass

    @preprocess("ts5", mode=PrepModels.VA50)
    def process_ts5(self, content: Any = None) -> None:
        """TS5: text storage.

        Args:
            content: Raw bytes of a TS5 VA50 file.

        Returns:
            None. Populates ``self.texts``.
        """
        if isinstance(content, (bytes, bytearray)):
            _, self.texts = parse_ts5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @classmethod
    def create(cls, main_file: Path) -> "Content | None":
        """Create and populate a ``Content`` instance for ``main_file``.

        The function discovers all non-empty files that share the same stem as
        ``main_file`` and stores them in ``files`` keyed by uppercase
        extension (e.g., ``{"NO5": Path(...)}"). It then calls all
        ``process_*`` methods to populate the structured fields. Missing files
        are logged and skipped.

        Args:
            main_file: Path to any file in the MapSys set; only its stem is
                used for discovery.

        Returns:
            A populated :class:`Content` or ``None`` if no sibling files were
            found.
        """
        main_key = main_file.stem.upper()
        collected = {}
        for file_path in main_file.parent.glob(f"{main_key}.*"):
            if file_path.is_file():
                if file_path.stat().st_size == 0:
                    logger.debug("Skipping empty file: %s", file_path)
                    continue
                collected[file_path.suffix[1:].upper()] = file_path
        if len(collected) == 0:
            logger.error("No files found for key: %s", main_key)
            return None
        logger.debug("Found %d files for key: %s", len(collected), main_key)

        result = cls(main_file=main_file, files=collected)

        result.process_al5()
        result.process_app()
        result.process_ar5()
        result.process_as5()
        result.process_at5()
        result.process_crs()
        result.process_csi()
        result.process_del()
        result.process_dts()
        result.process_ead()
        result.process_ims()
        result.process_jlk()
        result.process_lgn()
        result.process_lgs()
        result.process_mdb()
        result.process_mei()
        result.process_no5()
        result.process_ns5()
        result.process_ol5()
        result.process_pr5()
        result.process_prj()
        result.process_pxt()
        result.process_qs5()
        result.process_qt5()
        result.process_ral()
        result.process_ref()
        result.process_te5()
        result.process_thl()
        result.process_ts5()

        return result
