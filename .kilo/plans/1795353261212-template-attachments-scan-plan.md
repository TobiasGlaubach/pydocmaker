# Plan: Template attachments via source scanning (`-t` file references + `--assets`)

## Problem

`pydocmaker build README.md -t /path/to/tdd-template-report.tex` fails because the template references sibling files (`\includegraphics{MPIfR-Logo.png}`) that are not loaded into the document's attachments. Raw `-t` file templates are registered via `_register_raw_template_file` (src/pydocmaker/cli.py) into a throwaway template dir that contains only the template file itself. Registered template *ids* pull assets from a sibling `{stem}.assets/` folder, but nothing maps loose sibling files for raw `-t` paths.

The affected template references files two ways:
- static: `\includegraphics[...]{MPIfR-Logo.png}`
- macro-indirected: `\includegraphics{\pProjectLogo}` where `\providecommand{\pProjectLogo}{ MKE.png }` is a parameter default (note the surrounding spaces)

## Confirmed decisions

1. **Approach**: scan the template source for file references and load them as attachments; add a repeatable `-a/--assets PATH` flag (file or folder, recursive) as the explicit whole-folder fallback.
2. **Param file values**: string parameter values (from `--name value`, `-p` JSON, or template param defaults) that point at existing files are auto-loaded as attachments and the value is rewritten to the bare filename so template macros resolve in the build dir.
3. **Backend fixes**: include small `makedirs` guards in `pdf_maker_tex.py` and `ex_typst.py` so attachment keys with subpaths (`images/logo.png`) work.

All changes are in `src/pydocmaker/cli.py` plus the two backend guards; tests in `tests/test_cli.py`.

## Findings (verified in code)

- Attachment flow: `Doc.set_template_to_meta` b64-encodes attachments into `meta['files_to_upload']` (src/pydocmaker/core.py:1086); `get_template_from_meta` decodes them back (src/pydocmaker/core.py:1013-1015); exporters write them into the build dir. A manual merge into `meta['files_to_upload']` (bytes → `base64.b64encode(v).decode()`) is fully supported by existing machinery, including for `to_pdf`/`to_tex`.
- `TemplateDirSource.get_attachments` is flat-only (`os.listdir`) — bypass it; merge into meta directly so nested keys are possible.
- `pdf_maker_tex.py:217` writes attachments via `os.path.join(output_dir, filename)` with no parent-dir creation.
- `ex_typst.py:226-255` (`_compile` tempdir branch) writes `p / k` attachment files with no parent-dir creation.
- Scanning does **not** apply to template *ids* (`-t base`): ids keep the existing `.assets` folder convention. Param-value file resolution (decision 2) applies to ids and raw files alike.

## Tasks

### T1 — Reference scanner in `cli.py`

New helper `_find_template_file_references(source, tformat, base_dir)`:

- tex patterns: `\\includegraphics\*?(?:\[[^\]]*\])?\{([^{}]+)\}` and `\\(?:input|include|lstinputlisting|bibliography|addbibresource)\{([^{}]+)\}`
- typ patterns: `#image\(\s*"([^"]+)"`, `#include\s+"([^"]+)"`, `\bread\(\s*"([^"]+)"`, `#bibliography\(\s*"([^"]+)"` (also accept single quotes)
- block-template param defaults: `blocktmpl.parse(source).params_section` scalar values that are strings matching `^[^{}]+\.[A-Za-z0-9]{1,8}$` (strips surrounding spaces — catches ` MKE.png `)

Per candidate (after `strip()`), skip if it contains `\` (macro like `\pProjectLogo`), `{{`/`}}` (jinja), or starts with `http`. Resolve in order: as-is (absolute), `base_dir/ref`, `cwd/ref`. Attachment key = the reference as written, normalized to forward slashes. Emit an `_info` warning to stderr when a candidate has a file extension but no location exists (do not fail). Return `dict[key] = bytes` + list of unresolved refs.

### T2 — Param-value file resolution + rewrite

In `_apply_template_and_params`, before attaching the template: for each merged param `(name, value)` (from `-p` JSON and unknown-arg params) that is a `str` matching the filename-ish regex and resolving via the same order (template dir first, then cwd, then absolute): read bytes, add attachment under the file's **basename**, and set `params[name] = basename`. Warn on basename collisions (two different files with the same name; last wins).

### T3 — Attachment merge into meta

After `set_template_to_meta(...)` in the raw-file branch of `_apply_template_and_params` (and for `--assets` regardless of `-t`):

```python
meta = doc.get_meta({}).get('data', {})
ftu = meta.setdefault('files_to_upload', {})
for key, data in attachments.items():
    ftu[key] = base64.b64encode(data).decode()
doc.update_meta(meta)  # mirror set_template_to_meta's mutation pattern
```

Merge order (later wins): scanned refs → param-loaded files → `--assets`. Scanning runs for raw `-t` files only (including jinja `.j2` files — existence filter protects against false positives).

### T4 — `-a/--assets PATH` flag

Add `-a`/`--assets` (action `append`, repeatable) to the main parser (default `None`) and to the `example`, `show`, `build` subparsers (default `argparse.SUPPRESS`), same pattern as `-t`/`-p`. In the command handlers, pass collected paths into `_apply_template_and_params`/a new `_load_assets_paths(paths)`:

- file → key = basename
- directory → recursive walk, key = relpath (posix); exclude dirs `.git`/`__pycache__`/hidden and hidden files
- missing path → `CliError`

The argv pre-scan (`_collect_option_specs`) picks the new option up automatically.

### T5 — Backend `makedirs` guards

- `src/pydocmaker/backend/pdf_maker_tex.py` (~line 217): before `open(out_path, ...)`, if `os.path.dirname(filename)` is non-empty → `os.makedirs(os.path.dirname(out_path), exist_ok=True)`
- `src/pydocmaker/backend/ex_typst.py` (`_compile` tempdir branch, lines 226-255): before each `newpath.write_bytes(...)`, add `newpath.parent.mkdir(parents=True, exist_ok=True)`

### T6 — Docs

- Module docstring "Templating" section: document automatic attachment scanning, param file resolution, `-a/--assets`, merge order, and the id-vs-file distinction.
- Help texts/epilogs for `example`/`show`/`build`: mention `-a/--assets`.

### T7 — Tests (`tests/test_cli.py`)

- Scanner unit tests: tex `\includegraphics` (with options, with spaces, macro ref skipped), `\input`, typ `#image`/`read`, param-default ` MKE.png ` resolution, missing-ref warning, nested `images/logo.png` key.
- Integration: temp folder with `.typ` template + png → `build -f pdf` succeeds (typst engine available in venv); `--pProjectLogo alt.png` renders with the alt logo; tex template with `\includegraphics` → `build -f tex` zip contains `main.tex` + png, or pdf build if the tex engine is present.
- `-a` single file and folder (recursive + `.git`/hidden exclusions).
- Nested-key tex/typst build after T5.
- Existing suites must stay green (`tests/test_cli.py`, `tests/test_blocktmpl_cli.py`, `tests/test_pdf_typst.py`).

## Validation

1. `.venv/bin/python -m pytest tests/test_cli.py tests/test_blocktmpl_cli.py tests/test_pdf_typst.py -q`
2. End-to-end with the real template:
   - `pydocmaker build README.md -t /home/tglaubach/mpifr-tdd-document-templates/latex-typst/tdd-template-report.tex` → PDF with MPIfR/tdd logos and MKE.png (from the `pProjectLogo` default)
   - `pydocmaker build README.md -t <same> --pProjectLogo INAF-Logo.png` → alt logo rendered
   - `pydocmaker build README.md -a /home/tglaubach/mpifr-tdd-document-templates/latex-typst` → whole-folder variant
   - `pydocmaker example pdf -t <same>` for the example document

## Risks / limitations

- b64 in meta inflates attachment payload ~33%; large folders via `-a` can make builds slow-ish (local CLI, accepted; no size cap).
- Scanner is regex-based: `\graphicspath`, jinja-interpolated dynamic paths, and concatenated paths are not resolved — `-a` is the escape hatch. Documented as limitation.
- Scanned refs pointing at files that exist but are huge binaries are loaded as-is (no whitelist by extension beyond the reference patterns).
- `read("...")` pattern may over-match; mitigated by the existence check (nonexistent candidates only warn).

## Out of scope

- Scanning sources of registered template ids (ids keep the `.assets` convention)
- `\graphicspath` support, persistent registration of user template dirs, attachment deduplication across builds
