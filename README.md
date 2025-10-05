# mapsys

MapSys export and inspection tools for working with legacy MapSys projects.

MapSys is a Software solution created by GeoTop SRL in Odorheiul Secuiesc,
Romania. The official MapSys GIS functionality enables efficient generation
of digital plans and preparation, use and querying of spatial data using
specialized functions, with the goal of creating a relational data model
loaded with topologically validated information. Such data can be used in
MapSys or in any GIS/alfanumeric data management application.

This open-source repository is a small, unaffiliated utility that helps you
convert MapSys projects to DXF and explore their data structures. It is not a
replacement for the original MapSys application.

## What this project does (plain language)

- It looks for a MapSys "main" project file (usually a file like `*.pr5`) in
  a folder and reads the associated data files found next to it (points,
  polylines, texts, layers, etc.).
- It converts what it finds into a standard DXF drawing that you can open in
  CAD software (AutoCAD, BricsCAD, DraftSight, free viewers, etc.).
- It also contains building blocks for developers to read MapSys data files.

## Quick start for non-technical users

1) Install Python 3.11 or newer.

2) Create a virtual environment.

   On Linux/macOS:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows (PowerShell):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   To leave the environment later, run `deactivate`.

3) Install this tool inside the environment.

   With Make (recommended if available):

   ```bash
   make init
   ```

   Or with pip directly:

   ```bash
   python -m pip install -e .
   ```

4) Prepare a folder that contains your MapSys project. Place the "main"
   project file (e.g. `something.pr5`) and its companion files in the same
   directory.

5) Export to DXF using the provided template.

   ```bash
   mapsys to-dxf PATH/TO/YOUR/FOLDER \
     --dxf-template playground/template.dxf \
     --dxf PATH/TO/OUTPUT/your-project.dxf
   ```

   If everything goes well, a `your-project.dxf` file will be created that you
   can open in a CAD application.

## Command-line usage

Show the available commands and options:

```bash
mapsys --help
```

Export a single project from a directory that contains exactly one `.pr5`
file:

```bash
mapsys to-dxf /path/to/project \
  --dxf-template playground/template.dxf \
  --dxf /path/to/output.dxf
```

Export all projects found under a directory tree (one DXF per `.pr5` file):

```bash
mapsys to-dxf-dir /path/to/root \
  --dxf-template playground/template.dxf
```

Notes:

- The template must define at least a `POINT` block with attributes `NAME`,
  `SOURCE` and `Z` (the sample `playground/template.dxf` does this).
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
- `playground/`: Sample template and various sample assets for experiments.

## Troubleshooting

- DXF export fails immediately: ensure your folder contains exactly one `.pr5`
  main file and that you passed a valid `--dxf-template` path.
- On Windows, if you use `mdb_support.py` against Access databases, you may
  need the Microsoft Access Database Engine ODBC driver installed. On Linux,
  an alternative is `mdbtools` with unixODBC (`{MDBToolsODBC}` driver).
- If `mapsys` is not found, make sure your virtual environment is activated
  and that you installed the package with `pip install -e .`.

## Development (optional)

Install development tools and run checks:

```bash
make init-d     # install with dev extras
make test       # run mypy + pytest
make lint       # ruff linting
make delint     # ruff auto-fixes + format
```

## License and attribution

See `LICENSE` for licensing terms.

MapSys is a product of GeoTop SRL (Odorheiul Secuiesc, Romania). All
trademarks are the property of their respective owners. This project is a
community utility intended for interoperability and learning and is not
affiliated with GeoTop SRL.
