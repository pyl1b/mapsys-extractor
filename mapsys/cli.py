import logging
from pathlib import Path
from typing import Optional, Tuple

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


@cli.command(name="rebuild-index")
@click.argument(
    "root", type=click.Path(file_okay=False, dir_okay=True, exists=True)
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(
        file_okay=True, dir_okay=False, writable=True, path_type=Path
    ),
    default=Path(".mapsys/index.sqlite3"),
    show_default=True,
    help="Path to the SQLite index database.",
)
@click.option(
    "--ext",
    "exts",
    multiple=True,
    help=(
        "File extension to include (repeatable). "
        "May be given with or without leading dot. Default: py"
    ),
)
def cli_rebuild_index(root: str, db_path: Path, exts: Tuple[str, ...]) -> None:
    """Rebuild the index for git-tracked Python files under ROOT.

    Args:
        root: Directory to scan recursively for repositories.
        db_path: Path to the SQLite database to (re)build.
        exts: One or more file extensions to include.
    """
    from mapsys.content import Content

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

    click.echo(f"Done: {content}")
