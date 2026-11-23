# Plan: Comment-Delimited Block Templating Engine for pydocmaker

**Status:** implementation-ready
**Scope:** new standalone-compilable, comment-delimited templating scheme (`pydocmaker:parameters` / `pydocmaker:body` blocks) for HTML, LaTeX, and Typst — running **alongside** the existing Jinja2 engine, selected by auto-detection with explicit override.

---

## 1. Goals & Non-Goals

### Goals
1. Plain `.html` / `.tex` / `.typ` files stay **valid and compilable standalone** (native compilers ignore/evaluate the parameter constructs; body placeholder content is visible).
2. pydocmaker can **render** such files by replacing the `body` block content with the generated document body and injecting parameter values — without ever modifying the file on disk during render.
3. pydocmaker can **scaffold** (insert missing blocks via inference) and **update** (write parameter values back) files, idempotently.
4. Existing Jinja2 callers see **zero behavior change**: `jinja2` remains a hard dependency; all existing tests pass unchanged.
5. Engine selection: `template_engine='auto'` (default; markers in source → block engine) with `'jinja2'` / `'blocks'` explicit overrides.

### Non-Goals (v1, documented)
- Markers inside code/verbatim regions (LaTeX `verbatim`, Typst raw blocks, HTML `<pre>`/`<script>`) are **not** escaped or masked — documented limitation.
- Jinja2 syntax inside block templates is **not** processed by the block engine (and vice versa). Mixing engines in one file is undefined.
- DOCX/Markdown/IPYNB backends are untouched (no comment markers defined for them).
- No migration/conversion tool from `.j2` templates to block templates.

---

## 2. Current-State Map (verified)

| Concern | Location | Notes |
|---|---|---|
| Jinja2 engine | `src/pydocmaker/templating.py` | `TemplateDirSource` (lists only `*.j2` via `_template_matches_engine`), `DocTemplate.render(**kw)` (merges `params` + kwargs, `util.remove_undefined`), `handle_template(template, default, tformat) -> (Template, attachments, template_str)` |
| Backend converters | `src/pydocmaker/backend/ex_html.py:115`, `ex_tex.py:151`, `ex_typst.py:344` | Each builds `body` via a formatter, merges `template_params` (asserts `body` not user-supplied), calls `template_obj.render(**kw)` |
| Doc API | `src/pydocmaker/core.py` (`Doc.to_html` ~L1696, `to_typst` ~L1736, `to_pdf` ~L1772, `get_template_from_meta` ~L992, `set_template_to_meta` ~L1044) | Resolves templates from metadata (`template_id`), merges params, forwards to backends |
| Engine detection | `templating.determine_engine_from_template` (L22) | Returns `'html' | 'typ' | 'tex'` from extension or content markers |
| Templates | `src/pydocmaker/templates/*.j2` (+ `<id>.params.json` convention, `<id>.assets/` folders) | `block_`-prefixed files are excluded from the jinja registry |
| CLI | none | no `[project.scripts]` in `pyproject.toml` |
| Tests | `tests/` (unittest style, sys.path bootstrap to `src/`) | `test_templating.py` etc.; PDF/typst tests already use availability-guarded patterns |

Key existing contract to preserve: **`body` is a reserved parameter name** (`assert not ('body' in kw)` in every backend); `handle_template` return tuple; `TemplateDirSource` jinja-only listing; params precedence `block/meta defaults < explicit kwargs`.

---

## 3. Marker & Grammar Specification (normative)

### 3.1 Generic rules
- All markers must be **alone on their line** (optional leading/trailing whitespace). This keeps them unambiguous and safe in all three languages.
- Section markers (case-sensitive):
  - `pydocmaker:parameters:begin` / `pydocmaker:parameters:end`
  - `pydocmaker:body:begin` / `pydocmaker:body:end`
- Parameter markers: `pydocmaker:param:<name>` on their own line, `<name>` matches `[A-Za-z_][A-Za-z0-9_]*`. The **native assignment** starts on the next line (or same line where noted per format).
- Comment syntax per format:

| Format | Section markers | Param marker |
|---|---|---|
| HTML | `<!-- pydocmaker:parameters:begin -->` | `<!-- pydocmaker:param:name -->` |
| LaTeX | `% pydocmaker:parameters:begin` (`%` = first non-ws char) | `% pydocmaker:param:name` |
| Typst | `// pydocmaker:parameters:begin` | `// pydocmaker:param:name` |

- Regexes (format-generic, defined in `markers.py`):
  - section: `(?m)^[ \t]*(?:<!--|[%/]{1,2})[ \t]*pydocmaker:(parameters|body):(begin|end)[ \t]*(?:-->[ \t]*)?$`
  - param:  `(?m)^[ \t]*(?:<!--[ \t]*|[%/][ \t]*)pydocmaker:param:(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*(?:-->[ \t]*)?$`

### 3.2 Parameter value representation per format
The marker identifies the parameter; the **native assignment below the marker** stores the value. Scalar, dict, and list values map to native constructs:

**LaTeX** (macros are invisible standalone until used):
```
% pydocmaker:parameters:begin
% pydocmaker:param:title
\providecommand{\title}{My Report}
% pydocmaker:param:n_iter
\providecommand{\niter}{42}
% pydocmaker:param:acronyms
\newcommand{\acronyms}{%
\begin{description}
\item{SNR}{Signal-to-Noise Ratio}
\item{FFT}{Fast Fourier Transform}
\end{description}
}
% pydocmaker:param:events
\newcommand{\events}{%
\begin{itemize}
\item First item
\item Second item
\end{itemize}
}
% pydocmaker:parameters:end
```
- scalar → `\providecommand{\name}{value}` (per user decision; `\providecommand` never clashes with user-defined macros at standalone compile time).
- dict → `\newcommand{\name}{…\begin{description}\item{KEY}{VALUE}…\end{description}}` (exactly the user-specified syntax).
- list → `\newcommand{\name}{…\begin{itemize}\item VALUE…\end{itemize}}`.
- `bool`/`None` scalars: `true`/`false`/empty. Numbers emitted as `str(value)`.
- Assignment text is **rewritten wholesale** on update (no `\renewcommand` juggling): the engine regenerates the lines between a param marker and the next marker/section end. Since rewrites happen only inside the parameters block, standalone LaTeX never sees a duplicate definition (documented caveat: if the *user body* also defines the same macro, `\providecommand` no-ops silently).

**Typst** (native bindings, invisible standalone):
```
// pydocmaker:parameters:begin
// pydocmaker:param:title
#let title = "My Report"
// pydocmaker:param:acronyms
#let acronyms = (SNR: "Signal-to-Noise Ratio", FFT: "Fast Fourier Transform")
// pydocmaker:param:events
#let events = ("First item", "Second item")
// pydocmaker:parameters:end
```
- scalar str/int/float/bool/None → `"…"` / literal / `none`; dict → `(key: value, …)`; list → `(a, b, …)`. Nested dicts/lists allowed recursively (v1: one nesting level documented, recursion implemented generically).

**HTML** (invisible, valid in `<head>` and `<body>`):
```
<!-- pydocmaker:parameters:begin -->
<!-- pydocmaker:param:title -->
<meta name="pydocmaker:param:title" content="My Report">
<!-- pydocmaker:param:acronyms -->
<script type="application/json" data-pydocmaker-param="acronyms">{"SNR": "Signal-to-Noise Ratio"}</script>
<!-- pydocmaker:parameters:end -->
```
- scalar → `<meta name="pydocmaker:param:<name>" content="<HTML-escaped value>">`
- dict/list → `<script type="application/json" data-pydocmaker-param="<name>"><JSON></script>` (`</` inside JSON escaped as `<\/` to prevent `</script>` breakout).
- Parser additionally accepts `<span data-pydocmaker-param="<name>" hidden>…</span>` best-effort for scalars in body context (documented, not emitted).

### 3.3 Body blocks
```
% pydocmaker:body:begin            (LaTeX)
[any standalone-compilable placeholder content]
% pydocmaker:body:end
```
Same pattern with `<!-- … -->` / `// …`. Render semantics (user decision): content between markers is **replaced at render time**; the file on disk is never modified by rendering. Placeholder content stays visible on standalone compile.

### 3.4 Parameters-block free content
Everything inside a `parameters` block that is not a `param:` marker + assignment is **static content preserved verbatim** on scaffold/update (e.g. `\usepackage{...}`, extra CSS). Ordering of params and static lines is retained.

---

## 4. Architecture & Module Layout

New subpackage (isolates the feature; `templating.py` stays the Jinja2 module):

```
src/pydocmaker/blocktmpl/
    __init__.py        # public API + BlockDocTemplate re-export
    markers.py         # constants, per-format comment wrappers, regexes, detect_block_template()
    model.py           # @dataclass: Parameter, BlockSection, BlockDocument
    parser.py          # generic line scanner + adapter dispatch -> BlockDocument
    inference.py       # insertion-point detection, scaffold() insertion logic
    values.py          # per-format escape/serialize/parse for scalar|dict|list
    adapter_base.py    # FormatAdapter ABC (comment style, closing-statement rules, value codecs)
    adapter_html.py
    adapter_tex.py
    adapter_typ.py
    render.py          # render(source, body, params, ...) + BlockDocTemplate
    cli.py             # optional CLI (Phase 6)
```

`FormatAdapter` interface (per format): `comment_wrap(text)`, `section_marker_re`, `param_marker_re`, `find_closing_insert_position(source) -> int`, `serialize_param(name, value) -> str`, `parse_param(raw_lines) -> (value, kind, consumed)`, `default_body_placeholder()`, `standalone_validate(source)` hooks.

### Integration points (minimal, duck-typed — user decision)
1. **`templating.handle_template(template, default_template, tformat=None, template_engine='auto')`**
   - After resolving `template_str`: if `template_engine == 'auto'` and `detect_block_template(template_str)` → return `(BlockDocTemplate(template_str, tformat=…), attachments, template_str)`.
   - `'blocks'` forces block engine (source scaffolded in-memory if unmarked); `'jinja2'` forces the legacy path (markers ignored → warning if present).
   - `get_template_source()` gains a fast path for `BlockDocTemplate` (returns its stored source string; no jinja loader access).
2. **`BlockDocTemplate`** (`blocktmpl/render.py`) — duck-types `DocTemplate`:
   - Attributes used by `core.py` and backends: `.template` (source str), `.params` (defaults parsed from the block), `.attachments`, `.tformat`, `.template_id`, `.env = None`.
   - `render(**kw)`: pops reserved `body`, merges `self.params < kw`, `util.remove_undefined`, returns `render(self.template, body=…, params=…, tformat=self.tformat)`. Raises on `body` in user params (same assert message as backends).
   - `DocTemplate.render` (jinja class) gains a guard: if `self.template` is a str containing block markers → delegate to `BlockDocTemplate.render` (catch-all for direct constructions).
3. **`TemplateDirSource`** extensions (jinja listing untouched):
   - `get_block_templates() -> dict[str, BlockDocTemplate]`: scans dirs for `*.html|*.tex|*.typ` whose source contains markers (skips `.j2`, `block_*`, `.params.json`, dotfiles; reuses existing exclusion logic).
   - `resolve_template_id`: **exact filename match wins first** (so `base.tex` can force the block file when `base.tex.j2` also exists); short-ID resolution prefers the `.j2` file (backward compat, documented).
   - `get_template_ids()`: union of jinja + block IDs (jinja priority).
   - `get_params()`: for block templates, params come from the parsed block (unless `<id>.params.json` exists, which stays authoritative — consistent with jinja behavior).
   - `DocTemplate.from_tid` / `DocTemplate.create` factory: resolved file is a block file → build `BlockDocTemplate` (params + attachments identical flow).
4. **Backend converters** (`ex_html.convert`, `ex_tex.convert`, `ex_typst.convert`): add `template_engine='auto'` kwarg, forwarded to `handle_template`. Because `BlockDocTemplate.render(**kw)` is signature-identical, **no other changes** are needed in the render call. `ex_typst`'s `expected_variables` lookup is engine-aware (block templates → params from parser; wrapped in the existing try/except anyway).
5. **`core.py`**: `Doc.to_html`, `Doc.to_typst`, `Doc.to_pdf` gain `template_engine='auto'` and pass it through; `get_template_from_meta` builds via the factory so metadata-stored raw templates with markers also route correctly. `determine_engine_from_template` unchanged.
6. **Exports**: `pydocmaker.blocktmpl` public functions; re-export `BlockDocTemplate`, `parse`, `scaffold`, `update_params`, `render`, `detect` from `pydocmaker.templating` and `pydocmaker/__init__.py`.
7. **`requirements.txt` / `pyproject.toml`**: unchanged dependencies (stdlib-only new code); optional `[project.scripts] pydocmaker-blocktmpl` in Phase 6.

### Public API (v1)
```python
blocktmpl.parse(source, tformat=None) -> BlockDocument          # tformat None => auto-detect
blocktmpl.scaffold(source, tformat=None, params=None, body=None) -> str   # insert missing blocks
blocktmpl.update_params(source, tformat=None, params: dict) -> str        # write values back, idempotent
blocktmpl.render(source, body, params=None, tformat=None, template_engine='auto', strict=True) -> str
blocktmpl.detect(source, tformat=None) -> bool
blocktmpl.BlockDocTemplate(template, params=None, attachments=None, tformat=None, template_id=None)
```
`tformat` values: `'html' | 'tex' | 'typ'` (aligned with `VALID_ENGINES`).

---

## 5. Data Model

```python
@dataclass
class Parameter:
    name: str                      # [A-Za-z_][A-Za-z0-9_]*
    value: Any = None              # str|int|float|bool|dict|list|None (None = declared, unset)
    kind: str = 'scalar'           # 'scalar'|'dict'|'list'|'raw'
    raw: str = ''                  # verbatim assignment text (raw fallback / round-trip)

@dataclass
class BlockSection:
    kind: str                      # 'parameters'|'body'
    begin_span: tuple              # (line_start, line_end) char spans
    end_span: tuple | None         # None => unclosed (error/lenient)
    params: dict[str, Parameter]   # insertion-ordered; body section: {}
    static_lines: list[str]        # preserved verbatim (parameters block only)

@dataclass
class BlockDocument:
    tformat: str                   # 'html'|'tex'|'typ'
    source: str
    params_section: BlockSection | None
    body_section: BlockSection | None
    had_markers: bool              # False => parser ran in inferred/scaffold mode
    warnings: list[str]
```

Parsing strategy: single left-to-right line scan (regex on `(?m)` boundaries) recording char spans — enables **span surgery** (replace/insert) without re-serializing untouched regions (whitespace/comments/CRLF preserved). LaTeX assignment consumption uses a brace-depth scanner aware of `\{`/`\}` escapes; Typst assignment consumption scans until balanced `()`/quotes end; HTML consumes the single element line (script blocks: until `</script>`).

---

## 6. Per-Format Rules

| Aspect | HTML | LaTeX | Typst |
|---|---|---|---|
| Comment prefix | `<!-- … -->` (one line) | `%` at first non-ws char | `//` after leading ws |
| Scalar serialization | `<meta name="pydocmaker:param:N" content="…">` (HTML-escape `&<>"'`) | `\providecommand{\N}{…}` (escape `\ & % $ # _ { } ~ ^`, minimal internal `_latex_escape` — no hard dep on the optional `latex` package) | `#let N = "…"` (escape `\`, `"`, newline → existing `to_typst_string` style) |
| Dict serialization | `<script type="application/json" data-pydocmaker-param="N">{JSON}` | `\newcommand{\N}{%\n\begin{description}\n\item{K}{V}…\end{description}\n}` | `#let N = (k: v, …)` |
| List serialization | same script tag with JSON array | `\newcommand{\N}{%\n\begin{itemize}\n\item V…\end{itemize}\n}` | `#let N = (v, v, …)` |
| Parse-back | meta content → str; script → `json.loads` | brace-match macro body; `\begin{description}` → dict via `\item{K}{V}`; `\begin{itemize}` → list; else scalar unescape | parse `#let N = <literal>` subset (string/num/bool/none/dict/array, 1-level nesting; tolerant of whitespace) |
| Unsupported value | falls back to `raw` (verbatim preserved, not typed) + warning | same | same |
| Closing statement (inference) | `</body>` → `</html>` → EOF | `\end{document}` (regex `(?m)^\s*\\end\{document\}`, last occurrence) → EOF | none (linear) → EOF |
| Standalone behavior | meta/script invisible; JSON script inert | `\providecommand`/`\newcommand` define macros; used only if document references them | `#let` bindings inert unless referenced |

**HTML params placement rule (spec refinement, documented):** when *scaffolding*, the parameters block is inserted into `<head>…</head>` if present (validity of `<meta>`), else immediately before the body block position (before `</body>`). Body block always goes before `</body>` → `</html>` → EOF. The parser accepts a parameters block anywhere.

---

## 7. Inference & Edge-Case Rules (normative)

1. **Both sections missing** → insert `parameters` block then `body` block immediately before the closing statement (params first: at render time macros/bindings are defined before body references them). Typst: at EOF. HTML: params in `<head>` (if any), body before `</body>`.
2. **Only body exists** → insert `parameters` block immediately **before** the body block (keeps them adjacent; HTML: if the body block sits in `<body>`, params go adjacent using body-safe grammar).
3. **Only parameters exists** → insert `body` block immediately after the parameters block's `end` marker (no second closing-statement search — avoids splitting the "near the end" intent).
4. **No explicit closing statement** → insert at EOF; append a warning to `BlockDocument.warnings` and (in `scaffold`) emit a log warning. LaTeX special case: `\begin{document}` present but `\end{document}` missing → insert before EOF, warning explicitly says the file will not compile standalone as-is.
5. **Unclosed section (`begin` without `end`)** → `strict=True` (default): raise `MalformedBlockError` (message includes line number + format). `strict=False`: treat begin→EOF as the section, add warning.
6. **Stray `end` without `begin`** → strict: raise; lenient: ignore line, warn.
7. **Duplicate top-level sections of the same kind** → strict: raise; lenient: first wins, later duplicates treated as static content + warning.
8. **Param marker with no assignment** → `Parameter(value=None, kind='scalar')`; at render it is dropped by `remove_undefined` (consistent with jinja `Undefined` behavior); marker preserved on write-back.
9. **Assignment text that cannot be typed-parsed** → `kind='raw'`, value `None`, preserved verbatim; never destroyed by `update_params` unless an explicit value for that name is supplied.
10. **Unknown param names passed to `update_params`/`render`** → appended as new params (update) / passed through (render inserts them at end of the parameters block, scaffolding one if absent). `body` in params → `BodyReservedError` (same message text as existing backends).
11. **Line endings & BOM**: detect `\r\n` vs `\n`, preserve; read with `utf-8-sig`, write BOM back if present.
12. **Empty file / no format detectable** → `parse(tformat=None)` raises `UnsupportedFormatError`; explicit `tformat` always wins.

---

## 8. Phased Implementation & Acceptance Criteria

### Phase 1 — Markers, model, parser (foundation)
- Files: `blocktmpl/markers.py`, `model.py`, `parser.py`, `adapter_base.py`, `adapter_typ.py` (simplest first).
- Deliverables: `parse()`, `detect()`, section/param span extraction, lenient/strict modes, `Parameter`/`BlockSection`/`BlockDocument`.
- Tests (`tests/test_blocktmpl_parser.py`): all four markers per format; alone-on-line rule (leading ws, trailing ws); `detect()` true/false matrix; strict vs lenient for cases 5–7; param without assignment; CRLF + BOM round-trip.
- **Accept:** `pytest tests/test_blocktmpl_parser.py` green; existing suite untouched.

### Phase 2 — Value codecs (per-format serialization/parsing)
- Files: `values.py`, complete `adapter_tex.py`, `adapter_html.py`.
- Deliverables: scalar/dict/list serialize+parse per Section 3.2/6 table; escaping; `raw` fallback; `Parameter.kind` typing.
- Tests (`tests/test_blocktmpl_values.py`): round-trip matrix `{str,int,float,bool,None,dict,list}` × 3 formats; escaping cases (LaTeX `%&#_`, Typst `"\`, HTML `&<>"'</script>`); idempotent `update_params` (values updated in place, markers/static lines/order preserved; second run == first run output byte-identical); user example from this planning session (LaTeX `acronyms`/`events` macros) round-trips exactly.
- **Accept:** round-trip `parse(serialize(v)) == v` for all cells of the matrix.

### Phase 3 — Inference & scaffold
- Files: `inference.py`, `blocktmpl/scaffold` API.
- Deliverables: closing-statement detection per format; rules 1–4 + 11–12 of Section 7; `scaffold()` with optional initial `params`/`body` placeholder; LaTeX body insertion lands inside the document environment.
- Tests (`tests/test_blocktmpl_inference.py`): for each format × {both missing, body only, params only, no closing statement, empty file}: correct insert position (assert exact rendered document text), warnings recorded, scaffold idempotency (re-scaffold = no-op), HTML `<head>` preference.
- **Accept:** byte-exact expected outputs in fixtures for the 15-case matrix.

### Phase 4 — Render path + Jinja2-parallel integration (the critical phase)
- Files: `blocktmpl/render.py`, `blocktmpl/__init__.py`; edits: `templating.py` (`handle_template`, `get_template_source`, `DocTemplate.render` guard, `TemplateDirSource` block methods + factory), `core.py` (3 kwargs + `get_template_from_meta` factory), `backend/ex_html.py`, `ex_tex.py`, `ex_typst.py` (one kwarg pass-through each), `pydocmaker/__init__.py` exports.
- Deliverables: `render()` (replace body-block content, inject params, undefined params dropped, unknown params appended per rule 10), `BlockDocTemplate` duck-typing, auto-detection dispatch, template-dir resolution/params for block files, exact-name-over-short-id priority rule.
- Tests (`tests/test_blocktmpl_render.py`, `tests/test_blocktmpl_integration.py`):
  - Per format: end-to-end `Doc().add_text(...).to_html/to_typst/to_pdf(skip-if-no-compiler)` with a block template; assert generated body replaced the placeholder and params appear; **file on disk unchanged**.
  - Selection: marked file + `template_engine='auto'` → block path; same + `'jinja2'` → jinja path (markers pass through untouched); `'blocks'` on an unmarked file → in-memory scaffold render; both `base.tex.j2` + `base.tex` present → short ID resolves jinja, exact name resolves block.
  - `body`-reserved error; params precedence (block default < explicit kwarg); `template_params` from meta merge unaffected.
  - Standalone compile checks: `typst.compile` (guarded, pattern already used in `test_pdf_typst.py`), LaTeX compile guarded on `config_latex_compiler_testset`, HTML validated via `bs4` parse + no regression of `{{`/`{%` handling.
- **Accept:** full existing suite passes **without modification**; `jinja2` still imported in `templating.py` (no lazy-optional fallback).

### Phase 5 — Docs & examples
- `README.md` (new "Block templates" section with the three format examples from Section 3), `docs/blocktemplating.rst` + `docs/index.rst` toctree entry, one example file each under `src/pydocmaker/templates/` (`base.tex`, `base.html`, `base.typ` — note: `.j2` short-ID priority keeps existing behavior; block versions resolve by exact name), changelog entry in README/docs, version bump `2.7.0 → 2.8.0`.
- **Accept:** docs build (`sphinx`) unaffected; example block templates compile standalone (typst/latex guarded checks).

### Phase 6 (optional) — CLI
- `blocktmpl/cli.py` + `[project.scripts] pydocmaker-blocktmpl`:
  `scaffold <file> [--format auto] [--param k=v …]`, `update <file> --params params.json`, `inspect <file>` (prints parsed params table), `render <file> --body-file f [--params params.json] [-o out]`.
- Tests: CLI smoke tests via `subprocess` on temp files.

---

## 9. Error Handling

- Exception hierarchy in `blocktmpl/model.py`: `BlockTemplatingError(Exception)` → `MalformedBlockError`, `UnsupportedFormatError`, `BodyReservedError` (message text mirrors the existing backend assert), `ParameterTypeError`.
- Strictness: `strict=True` default for `parse`; `render`/`scaffold` expose `strict` pass-through. All lenient paths append to `BlockDocument.warnings` **and** `log.warning` via `pydocmaker.util.log`.
- Every error message includes: format, marker name, 1-based line number, and a one-line remedy hint.

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LaTeX brace matching in nested macro bodies | depth scanner with `\{`/`\}` awareness + unit tests for nested braces; unmatched → `raw` fallback, never data loss |
| User-authored structured LaTeX outside our grammar | `raw` kind preserves it verbatim; only engine-emitted grammar is guaranteed parseable (documented) |
| `TemplateDirSource` behavior drift | jinja listing/filter logic untouched; block listing is a separate method; existing `test_templating.py` must pass byte-identically |
| `<meta>` outside `<head>` | documented; `<head>` preferred at scaffold; parser tolerant; JSON-script grammar valid anywhere |
| Jinja/block marker collision | documented non-goal; `detect()` requires the full `pydocmaker:` marker prefix, so plain jinja/LaTeX sources cannot false-positive |
| Encoding/line-ending corruption | span surgery never rewrites untouched regions; CRLF/BOM preservation tested |

## 11. Validation Plan (final gate)
1. `python -m pytest tests/ -x` — full suite green (existing tests unmodified).
2. New suites: `test_blocktmpl_parser.py`, `test_blocktmpl_values.py`, `test_blocktmpl_inference.py`, `test_blocktmpl_render.py`, `test_blocktmpl_integration.py`.
3. Manual smoke: scaffold → standalone compile (typst + pdflatex if available + browser-open HTML) → `update_params` → recompile → `Doc.to_pdf` render — all without touching the original file bytes except via explicit `scaffold`/`update`.

## 12. Open Questions
None blocking — the four design decisions were resolved with the user: (1) auto-detect + `template_engine` override, (2) LaTeX structured params via `\newcommand` + description/itemize native constructs (user-specified syntax), (3) duck-typed `BlockDocTemplate` integration through `handle_template`, (4) replace-body-at-render semantics.
