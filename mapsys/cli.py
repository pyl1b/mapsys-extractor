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
        format="[%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if trace:
        logging.debug("Trace mode is on")
    if debug:
        logging.debug("Debug mode is on")
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
def mapsys_to_dxf(
    root: str,
    dxf_path: Path,
    dxf_template: Path,
    point_block: str,
    point_name_attrib: str,
    point_source_attrib: str,
    point_z_attrib: str,
) -> None:
    """Rebuild the index for git-tracked Python files under ROOT.

    Args:
        root: Directory to scan recursively for repositories.
        dxf_path: Path to the DXF file to create.
        dxf_template: Path to the DXF template file to use.
        point_block: Name of the block used for point symbols.
        point_name_attrib: Attribute tag used to store the point name/number.
    """
    from mapsys.content import Content
    from mapsys.to_dxf import mapsys_to_dxf

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

    mapsys_to_dxf(
        content,
        dxf_template,
        dxf_path=dxf_path,
        point_block=point_block,
        point_name_attrib=point_name_attrib,
        point_source_attrib=point_source_attrib,
        point_z_attrib=point_z_attrib,
    )
    click.echo("Done")
