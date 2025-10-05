# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic
Versioning.

## v0.0.1

### Added

- VA50/AR5 parser for polyline index (`mapsys.ar5_polys`) with unit tests.
- Access MDB/ACCDB extractor module docs and tests
  (`mapsys.parser.mdb_support` and `tests/test_mdb_support.py`).
- VA50/AS5 offsets parser tests (`mapsys.parser.as5_vertices`).
- VA50/TS5 text store parser tests (`mapsys.parser.ts5_text_store`).
- VA50/NO5 parser (`mapsys.parser.n05_points`) unit tests for header/coords and
  error cases.
- VA50/TE5 text metadata parser tests (`mapsys.parser.te5_text_meta`).

### Changed

- Improve and complete documentation for `mapsys.parser.ar5_polys` module
  (Google-style docstrings for module, classes, and functions).
- Complete documentation for `mapsys.parser.ts5_text_store` and fix signature
  validation bug.
- Complete Google-style docstrings and composed types in
  `mapsys.parser.n05_points`. Fix signature validation to `b"VA50"`.
- Complete Google-style docstrings for AS5 offsets parser
  (`mapsys.parser.as5_vertices`) and accept `b"VA50"`.
- Complete Google-style docstrings and composed types in
  `mapsys.parser.te5_text_meta`. Fix signature validation to `b"VA50"`.

### Documentation

- Add full Google-style docstrings to AL5 parser (`mapsys.parser.al5_poly_layer`).
- Add full Google-style docstrings to PR5 parser (`mapsys.parser.pr5_main`).
- Clarify decoding and offsets in TS5 text store docs.
- Add full Google-style docstrings to content loader (`mapsys.parser.content`).
- Add complete module and function docstrings for DXF colors utilities
  (`mapsys.dxf.dxf_colors`).
- Add full Google-style docstrings to DXF export builder
  (`mapsys.dxf.to_dxf`).

### Tests

- Add unit tests for AL5 parser (`tests/test_al5_poly_layer.py`).
- Add unit tests for AR5 parser (`tests/test_ar5_polys.py`) covering header,
  data records, invalid signature and short-buffer errors.
- Add unit tests for AS5 offsets parser (`tests/test_as5_vertices.py`).
- Add unit tests for PR5 parser (`tests/test_pr5_main.py`) covering header,
  layers, after-layers, final blocks and invalid header cases.
- Add unit tests for DXF colors helpers (`tests/test_dxf_colors.py`) covering
  valid/invalid indices and True Color application to layers and entities.
- Add unit tests for DXF export builder (`tests/test_to_dxf.py`), including
  entity insertion, layer naming, lineweight mapping and backup rotation.
- Add unit tests for content aggregation (`tests/test_content.py`) covering
  discovery, `get_poly_layer` and `text_by_offset`.

### Features

- XLSX export utility and CLI commands:
  - New module `mapsys/xl.py` with `export_to_xlsx(content, xlsx_path)` that
    writes one sheet per table and a `Headers` sheet; floats use 3 decimals.
  - New CLI commands: `to-xlsx` (single project) and `to-xlsx-dir` (tree).
