import csv
import logging
from enum import StrEnum
from functools import wraps
from pathlib import Path
from typing import Any

from attrs import define, field

from mapsys.ar5_polys import Ar5Data, parse_ar5
from mapsys.as5_vertices import parse_as5
from mapsys.mdb_support import extract_access_db
from mapsys.n05_points import No5Coord, parse_no5
from mapsys.te5_text_meta import Te5TextMeta, parse_te5
from mapsys.ts5_text_store import Ts5Text, parse_ts5

logger = logging.getLogger(__name__)


class PrepModels(StrEnum):
    TEXT_LINES = "text-lines"
    VA50 = "va50"
    CSV = "csv"
    UNKNOWN = "unknown"
    MDB = "mdb"
    ASSIGN = "assign"


def preprocess(name: str, mode: str) -> Any:
    """Preprocess a file.

    Args:
        name: The name of the file.
        mode: The mode of the file.
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
                content = extract_access_db(str(file_path))
                return func(self, content)

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
    """Content of a file."""

    main_file: Path
    files: dict[str, Path]

    points: list["No5Coord"] = field(factory=list)
    texts: list["Ts5Text"] = field(factory=list)
    t_meta: list["Te5TextMeta"] = field(factory=list)
    p_meta: list["Ar5Data"] = field(factory=list)
    v_offsets: list[int] = field(factory=list)

    offset_to_text: dict[int, str] = field(factory=dict, init=False)

    def text_by_offset(self, offset: int) -> str | None:
        """Get the text by its offset in the TS5 file."""
        if not self.offset_to_text:
            for text in self.texts:
                self.offset_to_text[text.offset] = text.text
        return self.offset_to_text.get(offset, None)

    @preprocess("al5", mode=PrepModels.VA50)
    def process_al5(self, content: Any = None) -> None:
        """The data section seems to be a list of 3-byte records.

        Does not seem to corelate with the number of points, texts or
        poly-lines.

        ```
        #pragma endian little
        #pragma magic [56 53 35 30] @ 0x00  // "VS50" at offset 0

        import std.mem;

        struct Header {
            char signature[4];      // "VS50"
            u32  int1[4];  int1[1] is always 768.
            u8 pad;
        };

        struct Data {
            u8 first;
            u8 second;
            u8 third;
        };

        struct VS50File {
            Header head;
            Data data[while (!std::mem::eof())];
        };

        VS50File file @ 0x00;
        ```
        """
        pass

    @preprocess("app", mode=PrepModels.TEXT_LINES)
    def process_app(self, content: Any = None) -> None:
        """Was always empty."""
        pass

    @preprocess("ar5", mode=PrepModels.VA50)
    def process_ar5(self, content: Any = None) -> None:
        if isinstance(content, (bytes, bytearray)):
            _, self.p_meta = parse_ar5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("as5", mode=PrepModels.VA50)
    def process_as5(self, content: Any = None) -> None:
        """The offset of each point of the polylines. The start and length are
        stored in the AR table.

        #pragma endian little
        #pragma magic [56 53 35 30] @ 0x00  // "VS50" at offset 0

        import std.mem;

        struct Header {
            char signature[4];      // "VS50"
            u32  int1[5];
            u8 pad;
        };

        struct VS50File {
            Header head;
            u32 data[while (!std::mem::eof())];
        };

        VS50File file @ 0x00;
        """
        if isinstance(content, (bytes, bytearray)):
            _, self.v_offsets = parse_as5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("at5", mode=PrepModels.VA50)
    def process_at5(self, content: Any = None) -> None:
        """The data section seems to be a list of 3-byte records.

        ```
        #pragma endian little
        #pragma magic [56 53 35 30] @ 0x00  // "VS50" at offset 0

        import std.mem;

        struct Data {
            u8 first; // 0, 2, 9, 255
            u8 second; // 0-255
            u8 third; // 0-255
        };


        struct Header {
            char signature[4];      // "VS50"
            u8 unk;
            u32 pad[4];
        };

        struct VS50File {
            Header head;
            Data data[while (!std::mem::eof())];
        };

        VS50File file @ 0x00;
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
        """Points."""
        if isinstance(content, (bytes, bytearray)):
            _, self.points = parse_no5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("ns5", mode=PrepModels.VA50)
    def process_ns5(self, content: Any = None) -> None:
        pass

    @preprocess("ol5", mode=PrepModels.UNKNOWN)
    def process_ol5(self, content: Any = None) -> None:
        pass

    @preprocess("pr5", mode=PrepModels.UNKNOWN)
    def process_pr5(self, content: Any = None) -> None:
        pass

    @preprocess("prj", mode=PrepModels.TEXT_LINES)
    def process_prj(self, content: Any = None) -> None:
        pass

    @preprocess("pxt", mode=PrepModels.ASSIGN)
    def process_pxt(self, content: Any = None) -> None:
        pass

    @preprocess("qs5", mode=PrepModels.VA50)
    def process_qs5(self, content: Any = None) -> None:
        pass

    @preprocess("qt5", mode=PrepModels.VA50)
    def process_qt5(self, content: Any = None) -> None:
        pass

    @preprocess("ral", mode=PrepModels.TEXT_LINES)
    def process_ral(self, content: Any = None) -> None:
        pass

    @preprocess("ref", mode=PrepModels.TEXT_LINES)
    def process_ref(self, content: Any = None) -> None:
        pass

    @preprocess("te5", mode=PrepModels.VA50)
    def process_te5(self, content: Any = None) -> None:
        if isinstance(content, (bytes, bytearray)):
            _, self.t_meta = parse_te5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @preprocess("thl", mode=PrepModels.TEXT_LINES)
    def process_thl(self, content: Any = None) -> None:
        pass

    @preprocess("ts5", mode=PrepModels.VA50)
    def process_ts5(self, content: Any = None) -> None:
        """Text storage."""
        if isinstance(content, (bytes, bytearray)):
            _, self.texts = parse_ts5(bytes(content))
        else:
            assert False, f"Unknown content type: {type(content).__name__}"

    @classmethod
    def create(cls, main_file: Path) -> "Content | None":
        """Create a Content object from a main file."""
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
