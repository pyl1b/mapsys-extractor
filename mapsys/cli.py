import logging
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv  # type: ignore[import-not-found]

# Initialize Colorama to ensure ANSI codes work on Windows terminals
# Import dynamically to avoid type-stub issues in linting environments
try:  # pragma: no cover
    import importlib

    _cm = importlib.import_module("colorama")
    Fore = _cm.Fore  # type: ignore[assignment]
    Style = _cm.Style  # type: ignore[assignment]
    colorama_init = _cm.init  # type: ignore[assignment]
except Exception:  # pragma: no cover

    class _NoColor:
        def __getattr__(self, _: str) -> str:
            return ""

    Fore = _NoColor()  # type: ignore[assignment]
    Style = _NoColor()  # type: ignore[assignment]

    # Keep signature simple to satisfy linters formatting
    def colorama_init(*_: object, **__: object) -> None:
        return None


from mapsys.__version__ import __version__


@click.group()
@click.option(
    "--debug/--no-debug", default=False, help="Enable verbose debug logging."
)
@click.option(
    "--trace/--no-trace", default=False, help="Enable trace level logging."
)
@click.option(
    "--log-file",
    type=click.Path(file_okay=True, dir_okay=False),
    envvar="mapsys_LOG_FILE",
    help=("Path to write log output to instead of stderr."),
)
@click.version_option(__version__, prog_name="mapsys")
def cli(debug: bool, trace: bool, log_file: Optional[str] = None) -> None:
    """Configure logging and load environment variables."""
    # Ensure Colorama is initialized so ANSI colors render on Windows
    try:
        colorama_init(autoreset=True)
    except Exception:
        pass
    if trace:
        level = 1
    elif debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        filename=log_file,
        level=level,
        format="[%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if trace:
        logging.debug("Trace mode is on")
    if debug:
        logging.debug("Debug mode is on")

    if debug or trace:
        # Silence ezdxf loggers to avoid excessive noise.
        logging.getLogger("ezdxf").setLevel(logging.INFO)
    load_dotenv()


@cli.command(name="to-dxf")
@click.argument(
    "root", type=click.Path(file_okay=False, dir_okay=True, exists=True)
)
@click.option(
    "--dxf",
    "dxf_path",
    type=click.Path(
        file_okay=True, dir_okay=False, writable=True, path_type=Path
    ),
    default=Path("mapsys.dxf"),
    show_default=True,
    help="Path to the DXF file to create.",
)
@click.option(
    "--dxf-template",
    "dxf_template",
    type=click.Path(
        file_okay=True, dir_okay=False, path_type=Path, exists=True
    ),
    default=Path("mapsys.dxf"),
    show_default=True,
    help="Path to the DXF template file to use.",
)
@click.option(
    "--point-block",
    "point_block",
    type=str,
    default="POINT",
    show_default=True,
)
@click.option(
    "--point-name-attrib",
    "point_name_attrib",
    type=str,
    default="NAME",
    show_default=True,
)
@click.option(
    "--point-source-attrib",
    "point_source_attrib",
    type=str,
    default="SOURCE",
    show_default=True,
)
@click.option(
    "--point-z-attrib",
    "point_z_attrib",
    type=str,
    default="Z",
    show_default=True,
)
@click.option(
    "--open-after-save/--no-open-after-save",
    "open_after_save",
    default=True,
    show_default=True,
)
def mapsys_to_dxf(
    root: str,
    dxf_path: Path,
    dxf_template: Path,
    point_block: str,
    point_name_attrib: str,
    point_source_attrib: str,
    point_z_attrib: str,
    open_after_save: bool,
) -> None:
    """Rebuild the index for git-tracked Python files under ROOT.

    Args:
        root: Directory to scan recursively for repositories.
        dxf_path: Path to the DXF file to create.
        dxf_template: Path to the DXF template file to use.
        point_block: Name of the block used for point symbols.
        point_name_attrib: Attribute tag used to store the point name/number.
    """
    from mapsys.parser.content import Content
    from mapsys.dxf.to_dxf import Builder

    root_path = Path(root)

    # Iterate over all files in the root path recursively.
    main_file = None
    for file_path in root_path.glob("*.pr5"):
        if file_path.is_file():
            if main_file is not None:
                logging.error(
                    "Multiple main files found: %s and %s",
                    main_file,
                    file_path,
                )
                return
            main_file = file_path
    if main_file is None:
        click.echo("No main file found.", err=True)
        return
    logging.debug("Found main file: %s", main_file)

    content = Content.create(main_file)
    if content is None:
        click.echo("No content found.", err=True)
        return

    Builder.convert(
        content,
        dxf_template,
        dxf_path=dxf_path,
        point_block=point_block,
        point_name_attrib=point_name_attrib,
        point_source_attrib=point_source_attrib,
        point_z_attrib=point_z_attrib,
        open_after_save=open_after_save,
    )
    click.echo("Done")


@cli.command(name="to-dxf-dir")
@click.argument(
    "root", type=click.Path(file_okay=False, dir_okay=True, exists=True)
)
@click.option(
    "--max-depth",
    type=int,
    default=-1,
    show_default=True,
    help=(
        "Maximum recursion depth (-1 for unlimited). "
        "Root directory is depth 0."
    ),
)
@click.option(
    "--include-backup/--exclude-backup",
    "include_backup",
    default=False,
    show_default=True,
    help=("Include directories named BACKUP during traversal when enabled."),
)
@click.option(
    "--dxf-template",
    "dxf_template",
    type=click.Path(
        file_okay=True, dir_okay=False, path_type=Path, exists=True
    ),
    default=Path("mapsys.dxf"),
    show_default=True,
    help="Path to the DXF template file to use.",
)
@click.option(
    "--point-block",
    "point_block",
    type=str,
    default="POINT",
    show_default=True,
)
@click.option(
    "--point-name-attrib",
    "point_name_attrib",
    type=str,
    default="NAME",
    show_default=True,
)
@click.option(
    "--point-source-attrib",
    "point_source_attrib",
    type=str,
    default="SOURCE",
    show_default=True,
)
@click.option(
    "--point-z-attrib",
    "point_z_attrib",
    type=str,
    default="Z",
    show_default=True,
)
def mapsys_dir_to_dxf(
    root: str,
    max_depth: int,
    include_backup: bool,
    dxf_template: Path,
    point_block: str,
    point_name_attrib: str,
    point_source_attrib: str,
    point_z_attrib: str,
) -> None:
    """Convert all ``.pr5`` files under ROOT into DXF files.

    The DXF is written next to each ``.pr5`` file with the same base name.
    Traversal respects ``--max-depth`` and skips ``BACKUP`` directories unless
    ``--include-backup`` is set.

    Directories are processed only if they contain at least one ``.pr5`` file.
    """

    from mapsys.parser.content import Content
    from mapsys.dxf.to_dxf import Builder

    root_path = Path(root)

    # Breadth-first traversal to honor max depth and BACKUP skipping.
    queue: list[tuple[Path, int]] = [(root_path, 0)]
    processed_count = 0
    converted_count = 0

    while queue:
        current, depth = queue.pop(0)

        # Skip directories named BACKUP unless explicitly included.
        if not include_backup and current.name.upper() == "BACKUP":
            logging.debug("Skipping BACKUP directory: %s", current)
            continue

        # Process current directory if it has at least one .pr5 file.
        pr5_files = [p for p in current.glob("*.pr5") if p.is_file()]
        if pr5_files:
            processed_count += 1
            logging.info(
                "Processing directory %s with %d .pr5 files",
                current,
                len(pr5_files),
            )
            for pr5 in pr5_files:
                dxf_out = pr5.with_suffix(".dxf")

                try:
                    content = Content.create(pr5)
                    if content is None:
                        logging.error("Failed to parse content for %s", pr5)
                        continue
                except Exception:
                    logging.exception("Failed to parse content for %s", pr5)
                    continue

                try:
                    Builder.convert(
                        content,
                        dxf_template,
                        dxf_path=dxf_out,
                        point_block=point_block,
                        point_name_attrib=point_name_attrib,
                        point_source_attrib=point_source_attrib,
                        point_z_attrib=point_z_attrib,
                        open_after_save=False,
                    )
                    converted_count += 1
                    click.echo(f"{dxf_out} was created")
                except Exception as exc:  # pragma: no cover
                    logging.exception(
                        "Failed converting %s to DXF: %s", pr5, exc
                    )

        # Enqueue children if depth allows.
        if max_depth < 0 or depth < max_depth:
            try:
                for child in current.iterdir():
                    if child.is_dir():
                        queue.append((child, depth + 1))
            except Exception:  # pragma: no cover
                logging.exception("Failed listing children of %s", current)

    click.echo(
        (
            f"Done. Processed {processed_count} directories, converted "
            f"{converted_count} files."
        )
    )
