import logging
from pathlib import Path
from attrs import define
from functools import wraps
from enum import StrEnum
import csv
from mapsys.mdb_support import extract_access_db


logger = logging.getLogger(__name__)


class PrepModels(StrEnum):
    TEXT_LINES = "text-lines"
    VA50 = "va50"
    CSV = "csv"
    UNKNOWN = "unknown"
    MDB = "mdb"
    ASSIGN = "assign"


def preprocess(name: str, mode: str):
    """Preprocess a file."""

    def decorator(func):

        @wraps(func)
        def wrapper(self, content=None):
            logging.debug("Preprocessing %s in %s mode", name, mode)
            file_path = self.files.get(name.upper())
            if file_path is None:
                logging.error("File %s not found", name)
                return

            if mode == PrepModels.MDB:
                content = extract_access_db(file_path)
                return func(self, content)

            text_mode = mode in (
                PrepModels.TEXT_LINES,
                PrepModels.CSV,
                PrepModels.ASSIGN
            )

            with open(
                file_path,
                "r" if text_mode else "rb",
                encoding="utf-8" if text_mode else None
            ) as f:
                content = f.read()
            if len(content) == 0:
                logging.error("File %s is empty", name)
                return

            if mode == PrepModels.TEXT_LINES:
                content = content.splitlines()
            elif mode == PrepModels.CSV:
                content = csv.reader(content.splitlines())
            elif mode == PrepModels.VA50:
                pass
            elif mode == PrepModels.UNKNOWN:
                pass
            elif mode == PrepModels.MDB:
                content = extract_access_db(file_path)
            elif mode == PrepModels.ASSIGN:
                result = {}
                for ln in content.splitlines():
                    assert "=" in ln, \
                        f"Line {ln} does not contain an equal sign"
                    key, value = ln.split("=")
                    result[key] = value
                content = result

            return func(self, content)

        return wrapper
    return decorator


@define
class Content:
    """Content of a file."""

    main_file: Path
    files: dict[str, Path]

    @preprocess("al5", mode=PrepModels.VA50)
    def process_al5(self, content=None):
        logger.debug("Processing al5: %s", content)

    @preprocess("app", mode=PrepModels.TEXT_LINES)
    def process_app(self, content=None):
        logger.debug("Processing app: %s", content)

    @preprocess("ar5", mode=PrepModels.VA50)
    def process_ar5(self, content=None):
        logger.debug("Processing ar5: %s", content)

    @preprocess("as5", mode=PrepModels.VA50)
    def process_as5(self, content=None):
        logger.debug("Processing as5: %s", content)

    @preprocess("at5", mode=PrepModels.VA50)
    def process_at5(self, content=None):
        logger.debug("Processing at5: %s", content)

    @preprocess("crs", mode=PrepModels.TEXT_LINES)
    def process_crs(self, content=None):
        logger.debug("Processing crs: %s", content)

    @preprocess("csi", mode=PrepModels.CSV)
    def process_csi(self, content=None):
        """
        2,Krassovsky,6378245.000,6356863.019
        4,ANCPI-S-42,2,2.329,-147.042,-92.080,0.309248,-0.324822,-0.497299,5.689063
        1,Stereografic,1
        1,Stereografic 1970,1,46.000000000,25.000000000,500000.000000000,500000.000000000,0.999750000,0.000000000,0.000000000,0.000000000,0.000000000,0.000000000
        2,EGG97-European Gravimetric Geoid 1997
        2,Stereo 70
        2,Stereografic 1970 - ANCPI-S-42,2,3,4,1,2
        46.665934915,25.615484176,0.000,0.000,0.000,0.000
        """
        logger.debug("Processing csi: %s", content)

    @preprocess("del", mode=PrepModels.TEXT_LINES)
    def process_del(self, content=None):
        logger.debug("Processing del: %s", content)

    @preprocess("dts", mode=PrepModels.UNKNOWN)
    def process_dts(self, content=None):
        logger.debug("Processing dts: %s", content)

    @preprocess("ead", mode=PrepModels.TEXT_LINES)
    def process_ead(self, content=None):
        logger.debug("Processing ead: %s", content)

    @preprocess("ims", mode=PrepModels.TEXT_LINES)
    def process_ims(self, content=None):
        logger.debug("Processing ims: %s", content)

    @preprocess("jlk", mode=PrepModels.TEXT_LINES)
    def process_jlk(self, content=None):
        logger.debug("Processing jlk: %s", content)

    @preprocess("lgn", mode=PrepModels.TEXT_LINES)
    def process_lgn(self, content=None):
        logger.debug("Processing lgn: %s", content)

    @preprocess("lgs", mode=PrepModels.TEXT_LINES)
    def process_lgs(self, content=None):
        logger.debug("Processing lgs: %s", content)

    @preprocess("mdb", mode=PrepModels.MDB)
    def process_mdb(self, content=None):
        logger.debug("Processing mdb: %s", content)

    @preprocess("mei", mode=PrepModels.ASSIGN)
    def process_mei(self, content=None):
        logger.debug("Processing mei: %s", content)

    @preprocess("no5", mode=PrepModels.VA50)
    def process_no5(self, content=None):
        logger.debug("Processing no5: %s", content)

    @preprocess("ns5", mode=PrepModels.VA50)
    def process_ns5(self, content=None):
        logger.debug("Processing ns5: %s", content)

    @preprocess("ol5", mode=PrepModels.UNKNOWN)
    def process_ol5(self, content=None):
        logger.debug("Processing ol5: %s", content)

    @preprocess("pr5", mode=PrepModels.UNKNOWN)
    def process_pr5(self, content=None):
        logger.debug("Processing pr5: %s", content)

    @preprocess("prj", mode=PrepModels.TEXT_LINES)
    def process_prj(self, content=None):
        logger.debug("Processing prj: %s", content)

    @preprocess("pxt", mode=PrepModels.ASSIGN)
    def process_pxt(self, content=None):
        logger.debug("Processing pxt: %s", content)

    @preprocess("qs5", mode=PrepModels.VA50)
    def process_qs5(self, content=None):
        logger.debug("Processing qs5: %s", content)

    @preprocess("qt5", mode=PrepModels.VA50)
    def process_qt5(self, content=None):
        logger.debug("Processing qt5: %s", content)

    @preprocess("ral", mode=PrepModels.TEXT_LINES)
    def process_ral(self, content=None):
        logger.debug("Processing ral: %s", content)

    @preprocess("ref", mode=PrepModels.TEXT_LINES)
    def process_ref(self, content=None):
        logger.debug("Processing ref: %s", content)

    @preprocess("te5", mode=PrepModels.VA50)
    def process_te5(self, content=None):
        logger.debug("Processing te5: %s", content)

    @preprocess("thl", mode=PrepModels.TEXT_LINES)
    def process_thl(self, content=None):
        logger.debug("Processing thl: %s", content)

    @preprocess("ts5", mode=PrepModels.TEXT_LINES)
    def process_ts5(self, content=None):
        logger.debug("Processing ts5: %s", content)

    @classmethod
    def create(cls, main_file: Path) -> "Content | None":
        """Create a Content object from a main file."""
        main_key = main_file.stem.upper()
        collected = {}
        for file_path in main_file.parent.glob(f"{main_key}.*"):
            if file_path.is_file():
                if file_path.stat().st_size == 0:
                    logging.debug("Skipping empty file: %s", file_path)
                    continue
                collected[file_path.suffix[1:].upper()] = file_path
        if len(collected) == 0:
            logging.error("No files found for key: %s", main_key)
            return None
        logging.debug("Found %d files for key: %s", len(collected), main_key)

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
