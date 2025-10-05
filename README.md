# MapSys Extractor

[🇺🇸 English](README.md) | [🇷🇴 Română](README.ro.md)

MapSys export and inspection tools for working with MapSys projects.

MapSys is a Software solution created by GeoTop SRL in Odorheiul Secuiesc,
Romania. The official MapSys GIS functionality enables efficient generation
of digital plans and preparation, use and querying of spatial data using
specialized functions, with the goal of creating a relational data model
loaded with topologically validated information. Such data can be used in
MapSys or in any GIS/alfanumeric data management application.

This open-source repository is a small, *unaffiliated* utility that helps you
convert MapSys projects to DXF and explore their data structures. It is not a
replacement for the original MapSys application.

As the format of the files is not openly documented, their structure
had to be determined by examining the hex dump. The meaning for a lot of fields
is still unknown. Always check the output and file an issue if it does
not match the input.

## What this project does

- It looks for a MapSys "main" project file (usually a file like `*.pr5`) in
  a folder and reads the associated data files found next to it (points,
  polylines, texts, layers, etc.).
- It converts what it finds into a standard DXF drawing that you can open in
  CAD software (AutoCAD, BricsCAD, DraftSight, free viewers, etc.).
- It also contains building blocks for developers to read MapSys data files.

## Install

The steps below are written for beginners. They show how to:

1) Install Python
2) Create a private “virtual environment”
3) Get the project from GitHub
4) Install it into your environment and run it

You only need to do this once on your computer. After that, you can just
activate the environment and use the tool.

### 1) Install Python (version 3.11 or newer)

- Windows:
  - Go to the official Python website: `https://www.python.org/downloads/`
  - Download “Python 3.x” for Windows and run the installer.
  - Important: On the first screen, check the box “Add Python to PATH”,
    then click Install.
  - After install, open PowerShell and type:

    ```powershell
    python --version
    ```

    You should see something like `Python 3.11.8` (any 3.11+ is fine).

- macOS:
  - Visit `https://www.python.org/downloads/` and install the latest 3.x for macOS.
  - Open Terminal and type `python3 --version` to confirm.

- Linux (Ubuntu/Debian):
  - Open Terminal and run:

  ```bash
  sudo apt update && sudo apt install -y python3 python3-venv python3-pip
  ```

  - Confirm with: `python3 --version`

### 2) Create a virtual environment (keeps things clean)

Pick a folder where you want to keep this project (for example,
`D:\tools\mapsys-extractor` on Windows or `~/tools/mapsys-extractor` on
macOS/Linux). Then:

- Windows PowerShell:

  ```powershell
  python -m venv .venv
  . .venv\Scripts\Activate.ps1
  ```

- macOS/Linux Terminal:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

If activation worked, your prompt will show `(.venv)` at the start. While this
is active, anything you install stays private to this folder.

### 3) Get the project from GitHub

If you have Git installed, you can clone the repository. If not, you can click
the green “Code” button on GitHub and download the ZIP, then unzip it into your
chosen folder.

Using Git (recommended):

```bash
git clone https://github.com/pyl1b/mapsys-extractor.git
cd mapsys-extractor
```

### 4) Install the tool into your environment

With the virtual environment still active and inside the `mapsys-extractor` folder,
run:

- Windows PowerShell:

  ```powershell
  python -m pip install --upgrade pip
  python -m pip install -e .
  ```

- macOS/Linux:

  ```bash
  python3 -m pip install --upgrade pip
  python3 -m pip install -e .
  ```

This installs the library and the `mapsys-extractor` command.

### 5) Try it out

Show the help to confirm it’s installed:

```bash
mapsys-ex --help
```

Later, when you come back to use the tool again, just re-activate the
environment (step 2) and you’re ready.

### 6) Use it

Prepare a folder that contains your MapSys project. Place the "main"
project file (e.g. `something.pr5`) and its companion files in the same
directory.

Create a dxf file to use as template. This can have stuff in it or be empty;
we use it because the application can be configured to export the MapSys points
as blocks with attributes, in which case this template file should have that
block definition already present. See the help for the `to-dxf` command
(`mapsys to-dxf --help`) to get a list of arguments related to block export.

```bash
mapsys to-dxf PATH/TO/YOUR/FOLDER \
  --dxf-template template.dxf \
  --dxf PATH/TO/OUTPUT/your-project.dxf
```

If everything goes well, a `your-project.dxf` file will be created in the same
directory as the .pr5 file.

## Command-line usage

Show the available commands and options:

```bash
mapsys --help
```

All commands share logging flags: `--debug/--no-debug`, `--trace/--no-trace`,
and `--log-file` to redirect logs. Version is available via `--version`.

Export a single project from a directory that contains exactly one `.pr5`
file:

```bash
mapsys to-dxf /path/to/project \
  --dxf-template template.dxf \
  --dxf /path/to/output.dxf
```

Export all projects found under a directory tree (one DXF per `.pr5` file):

```bash
mapsys to-dxf-dir /path/to/root \
  --dxf-template template.dxf
```

Notes:

- The template should define at least a `POINT` block with attributes `NAME`,
  `SOURCE` and `Z`.If it does a circle will be created for each point.
- The tool derives layer names and colors from your MapSys layers.
- When using `to-dxf`, the directory must contain exactly one `.pr5` file.

### XLSX export

Export a single project to an Excel workbook:

```bash
mapsys to-xlsx /path/to/project \
  --xlsx /path/to/output.xlsx
```

Export all projects to Excel under a directory tree:

```bash
mapsys to-xlsx-dir /path/to/root --max-depth -1 --exclude-backup
```

Details:

- Sheets: `NO5_points`, `TS5_texts`, `TE5_meta`, `AR5_polys`, `AS5_offsets`,
  `AL5_layers`, and if available `PR5_layers`, `PR5_after`, `PR5_fonts`.
- Columns: nested structures are flattened into multiple columns, and an
  `idx` column is added with the 0-based row index.
- Types: floats formatted to 3 decimals; unknowns written as text; bytes as
  hexadecimal strings.

## Project structure

High-level overview of the most relevant folders and files:

- `mapsys/cli.py`: Command-line interface (commands `to-dxf` and
  `to-dxf-dir`). Configures logging and loads environment variables.
- `mapsys/__main__.py`: Entry-point adapter that runs the CLI when you invoke
  `python -m mapsys` or the `mapsys` command.
- `mapsys/dxf/to_dxf.py`: DXF export builder. Contains the `Builder` that
  creates layers, inserts point blocks, writes polylines and texts, and saves
  the DXF file.
- `mapsys/dxf/dxf_colors.py`: Helpers for mapping MapSys colors and line
  weights to DXF values.
- `mapsys/parser/`: Parsers for MapSys/VA50 binary files used by projects:
  - `pr5_main.py`: Reads the "main" project metadata and layer definitions.
  - `al5_poly_layer.py`: Polyline-to-layer mapping.
  - `ar5_polys.py`: Polyline sequences and their attributes.
  - `as5_vertices.py`: Vertex indices used by polylines.
  - `n05_points.py`: Point coordinates.
  - `te5_text_meta.py`: Text placement and style metadata.
  - `ts5_text_store.py`: Text storage and decoding.
  - `content.py`: Convenience aggregator that ties the pieces together.
  - `mdb_support.py`: Optional Microsoft Access `.mdb/.accdb` table extractor
    via ODBC, for related data.
- `tests/`: Automated tests that verify the parsers and the DXF export.
  Includes tests for the XLSX export and CLI commands.

## Troubleshooting

- DXF export fails immediately: ensure your folder contains exactly one `.pr5`
  main file and that you passed a valid `--dxf-template` path.
- On Windows, if you use `mdb_support.py` against Access databases, you may
  need the Microsoft Access Database Engine ODBC driver installed. On Linux,
  an alternative is `mdbtools` with unixODBC (`{MDBToolsODBC}` driver).
- If `mapsys` is not found, make sure your virtual environment is activated
  and that you installed the package with `pip install -e .`.

## Development

Install development tools and run checks:

### Common tasks

```bash
# Format
make format

# Lint
make lint

# Tests (type-check + pytest)
make test

# Fix simple lint issues automatically
make delint
```

The CLI entry point is `mapsys.__main__:cli` and can be invoked as:

```bash
python -m mapsys --help
```

### Project conventions

- Typed code, small modules, clear names
- Prefer stdlib and a minimal set of dependencies
- Follow ruff formatting and linting configuration in `pyproject.toml`
- Keep public APIs stable; if you change them, update `CHANGELOG.md`

### Release

On the local machine create a package and test it.

```bash
pip install build twine
python -m build
twine check dist/*
```

Change `## [Unreleased]` to the name of the new version in `CHANGELOG.md`,
then create a commit, then create a new tag and push it to GitHub:

```bash
git add .
git commit -m "Release version 0.1.0"

git tag -a v0.1.0 -m "Release version 0.1.0"

git push origin v0.1.0
# or
git push origin --tags
```

In the GitHub repository page create a new Release. This will trigger the
workflow for publishing in PyPi.

## License and attribution

See `LICENSE` for licensing terms.

MapSys is a product of GeoTop SRL (Odorheiul Secuiesc, Romania). All
trademarks are the property of their respective owners. This project is a
community utility intended for interoperability and learning and is not
affiliated with GeoTop SRL.
