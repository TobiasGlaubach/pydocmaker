"""Command line gateway to the pydocmaker library (the ``pydocmaker`` executable).

This module turns the most common pydocmaker workflows into small shell commands
("groups") so documents can be created, converted, validated and templated
without writing any python code. It is registered as the ``pydocmaker`` console
script in ``pyproject.toml`` (``[project.scripts]``) and can equivalently be run
as a module via ``python -m pydocmaker.cli``.

Usage
-----
The general call syntax is::

    pydocmaker <command> [arguments]

Use ``pydocmaker <command> --help`` to see the full argument reference of a
single command. All commands write the produced *document data* to stdout (or
the file given with ``-o``) while progress/status messages go to stderr, so
stdout stays clean for piping and redirection.

Commands
--------

``example`` -- write the built-in example document
    Writes the document returned by ``Doc.get_example()`` in a given format
    either to the file given after ``-o`` or to stdout (when ``-o`` is omitted
    or empty)::

        pydocmaker example md                     # markdown to stdout
        pydocmaker example pdf -o example.pdf      # pdf to a file
        pydocmaker example -o out.html             # format from the extension

``show`` -- display a document on the terminal
    Shows a document using ``Doc.show()``. The document is either read from the
    given input file or, when no input file is given, the built-in example
    document is used. The format selects the show engine, e.g. ``html``,
    ``md``/``markdown``, ``tex``/``latex``, ``typ``/``typst``, ``rich`` or
    ``auto`` (default; picks a sensible engine for the environment)::

        pydocmaker show rich                      # example document, rich console output
        pydocmaker show html my_document.json     # show an input file as html

``build`` / ``convert`` -- convert documents into another format
    Reads one or more documents and exports each of them into a target format
    (pdf by default); inputs are never merged -- every file is built
    individually. The output file name defaults to the input file name with
    the file extension exchanged (``README.md`` -> ``README.pdf``); use
    ``-o`` to set an explicit output path. Readable inputs are: json
    pydocmaker files (``Doc.save``/``Doc.load``), html pydocmaker files
    (``html_loader.py``), notebooks (``.ipynb``), markdown (``.md``), latex
    (``.tex``), typst (``.typ``) and any other non-binary text document
    (added via ``Doc.add_text``). Typst files can be built to PDF on their
    own. Use ``--nocode`` when building notebooks to exclude all code cells::

        pydocmaker build README.md               # -> README.pdf
        pydocmaker build my_report.tex            # -> my_report.pdf
        pydocmaker build my_report.typ            # -> my_report.pdf
        pydocmaker build notes.md -f html         # -> notes.html
        pydocmaker build notebook.ipynb --nocode   # -> notebook.pdf (no code)

    Plain latex (``.tex``) files built to pdf are treated as complete
    standalone documents: they are compiled with the latex engine (not the
    configured default engine) and rendered verbatim, without the pydocmaker
    default preamble -- unless a template is given via ``-t``, which wraps
    the input like any other document body.

    An input may be a glob pattern (``abc*.tex``); every file matched by the
    pattern is built individually (as if the command was run once per file,
    each writing its own output next to the input). Unquoted patterns which
    the shell has already expanded into several arguments are handled
    identically. ``-o/--out`` cannot be combined with multiple inputs::

        pydocmaker build "abc*.tex"

Verbosity
---------
``build``/``convert`` and ``example`` accept ``-v/--verbosity`` to control how
much progress and backend detail is printed to stderr (default 1). The level
is passed through to the pdf, tex and typst export engines: 0 = quiet,
1 = normal status messages, 2 = more details, 3+ = full backend output::

    pydocmaker build report.tex -v 3

``check`` -- validate a document or template file
    Checks the syntax of an input file and reports whether it is OK. Supported
    inputs are json pydocmaker files, html pydocmaker files
    (``html_loader.py``) and "blocktemplate" files of html, tex or typ (the
    comment-delimited ``pydocmaker:`` marker templates). For blocktemplates
    the blocks are analyzed, correctness problems are reported and the found
    parameters are printed as JSON::

        pydocmaker check my_document.json
        pydocmaker check base.typ

``extract`` -- print template parameters as JSON
    Extracts the parameters from a given template file and prints them as a
    JSON mapping to stdout. Blocktemplates yield the parameter values declared
    in their parameters block; jinja2 templates yield their undeclared
    variables (value ``null``)::

        pydocmaker extract base.html

``template`` -- copy a document template
    Copies one of the registered pydocmaker document templates either to the
    file given after ``-o`` or to stdout (when ``-o`` is omitted or empty).
    The input string can be a bare format (``html``, ``tex`` or ``typ`` -- in
    which case the base template ``base.XXX`` is used), a bare template id
    (``base``, ``report``) or a full template file name (``base.html``)::

        pydocmaker template html                  # base.html to stdout
        pydocmaker template typ -o my_report.typ  # base.typ to a file
        pydocmaker template base.tex -o tmpl.tex

``templates`` -- list the registered templates
    Prints every template file found in the registered template directories
    (the package templates plus user registered ones) with its full path,
    grouped by directory, to stdout::

        pydocmaker templates

Templating
----------
``example``, ``show`` and ``build``/``convert`` accept a document template via
``-t/--template`` and template parameters via ``-p/--parameters``. The template
can be the path of a template file or a template id like ``base`` or
``base.tex`` which is resolved from the registered template directories. For
template ids the per-format variant matching the output format is used, so
``-t base`` renders html, latex and typst exports each with their own
``base.XXX`` template. The parameters are either a JSON object string, a path
to a JSON file (or ``@file.json``) or -- most conveniently -- additional
unknown ``--name value`` command line arguments::

    pydocmaker example pdf -t base --pAuthor "me" --pTitle "My Report"
    pydocmaker build README.md -t base.tex --pTitle "Readme"
    pydocmaker show html doc.json -t my_custom.html --pTitle "Doc"
    pydocmaker build doc.md -p params.json
    pydocmaker build doc.md -p '{"pTitle": "From JSON"}'

Unknown long options (``--name value``, ``--name=value`` or a bare ``--flag``
which becomes ``true``) are collected as template parameters as long as a
templating command (example, show, build, convert) is used. Their values are
JSON-parsed when possible (``--n 5`` -> ``5``) and otherwise kept as strings.
Parameters given via ``--name value`` override values from ``-p``.

Template options are only accepted where they have an effect: the
non-templating commands (``check``, ``extract``, ``template``, ``templates``)
reject ``-t``/``-p``/``-a`` with an error, and the direct typst build
(``build my_report.typ``) rejects both a template and template parameters
with an error instead of silently ignoring them::

    pydocmaker build my_report.typ --pTitle "T"   # error: no template parameters
    pydocmaker check my_document.json -t base     # error: no template options

Attachments
~~~~~~~~~~~
Templates often reference sibling files (logos, images, bibliography
files). Templates given as *file paths* via ``-t`` get those references
loaded automatically: the template source is scanned for file references
(``\\includegraphics{...}``, ``\\input{...}`` etc. for latex;
``#image("...")``, ``#include "..."`` etc. for typst) and block-template
parameter defaults that look like file names (`` MKE.png ``). Every
reference that exists -- as given, next to the template file or in the
working directory -- is attached to the document and written into the build
directory of pdf/tex/typst exports. Unresolved references only produce a
warning. Registered template *ids* keep the existing ``{name}.assets``
folder convention instead (their sources are not scanned).

String template parameter values that point at existing files (searched
next to the template first, then in the working directory, then as absolute
paths) are loaded as attachments as well and rewritten to their bare file
name, so ``--pProjectLogo INAF-Logo.png`` renders the alternative logo::

    pydocmaker build README.md -t report.tex --pProjectLogo INAF-Logo.png

Additional attachments can be given explicitly (and repeatable) via
``-a/--assets`` with either a file (attached under its file name) or a
folder (attached recursively, with the file's path relative to the folder
as key; hidden files and directories are skipped)::

    pydocmaker build README.md -t report.tex -a ./assets -a extra_logo.png

When several sources attach the same file name the later one wins; the
merge order is scanned template references, then parameter-loaded files,
then ``-a/--assets``. Note that the source scan is regex based and cannot
resolve ``\\graphicspath``, jinja-interpolated dynamic paths or concatenated
paths -- ``-a/--assets`` is the escape hatch for those cases.

Directly built ``.tex``/``.latex`` and ``.typ``/``.typst`` input files (pdf
builds) get the same treatment: their file references are scanned and
attached automatically, resolving each reference as given, next to the
input file and in the working directory. This lets ``pydocmaker build
report.tex`` find ``logo.png`` next to ``report.tex`` even when the command
runs from a different working directory.

Output formats
--------------
``example``, ``build`` and ``convert`` accept the formats (and aliases)
``pdf``, ``md``/``markdown``, ``html``, ``typ``/``typst``, ``tex``/``latex``,
``json``, ``docx``/``word``, ``ipynb``, ``textile`` and ``pydoc``/``pyd``
(the lossless pydocmaker html round-trip format written by ``Doc.save``).
The formats ``pdf`` and ``docx`` are binary; they require an output file
(give ``-o`` or pipe stdout into a file).

Exit codes
----------
``0`` success, ``1`` a check failed (e.g. invalid syntax), ``2`` a usage or
runtime error occurred (bad arguments, unreadable input, ...).
"""

import argparse
import base64
import glob
import json
import os
import re
import sys

try:  # normal import (installed package or ``python -m pydocmaker.cli``)
    from pydocmaker import __version__
    from pydocmaker import blocktmpl
    from pydocmaker.core import Doc
    from pydocmaker.templating import (get_available_template_ids,
                                       get_registered_template_dirs,
                                       resolve_template_id)
except Exception:  # pragma: no cover - executed directly as a script file
    from . import __version__
    from . import blocktmpl
    from .core import Doc
    from .templating import (get_available_template_ids,
                             get_registered_template_dirs,
                             resolve_template_id)


# --------------------------------------------------------------------------- #
# format tables
# --------------------------------------------------------------------------- #

#: canonical output format for every accepted format name (lower case)
FORMAT_ALIASES = {
    'pdf': 'pdf',
    'md': 'md', 'markdown': 'md',
    'html': 'html', 'htm': 'html',
    'typ': 'typst', 'typst': 'typst',
    'tex': 'tex', 'latex': 'tex',
    'json': 'json',
    'docx': 'docx', 'word': 'docx',
    'ipynb': 'ipynb', 'notebook': 'ipynb',
    'textile': 'textile',
    'pydoc': 'pydoc', 'pyd': 'pydoc', 'pydocmaker': 'pydoc',
}

#: file extension written for every canonical output format
FORMAT_EXTENSIONS = {
    'pdf': '.pdf',
    'md': '.md',
    'html': '.html',
    'typst': '.typ',
    'tex': '.tex',
    'json': '.json',
    'docx': '.docx',
    'ipynb': '.ipynb',
    'textile': '.textile.zip',
    'pydoc': '.pyd',
}

#: canonical formats whose payload is binary (cannot be printed as text)
BINARY_FORMATS = frozenset({'pdf', 'docx'})

#: file suffix (longest first) to canonical format, used to infer the output
#: format from an output file name
SUFFIX_FORMATS = [
    ('.textile.zip', 'textile'),
    ('.pdf', 'pdf'),
    ('.md', 'md'), ('.markdown', 'md'),
    ('.html', 'html'), ('.htm', 'html'),
    ('.typ', 'typst'),
    ('.tex', 'tex'), ('.latex', 'tex'),
    ('.json', 'json'),
    ('.docx', 'docx'),
    ('.ipynb', 'ipynb'),
    ('.pyd', 'pydoc'), ('.pydoc', 'pydoc'),
]

#: file extensions of the lossless pydocmaker document formats (Doc.save/load)
PYDOCMAKER_DOC_EXTS = ('.json', '.html', '.htm', '.pyd', '.pydoc', '.ipynb')

#: engine names accepted by ``Doc.show()`` (mapped to the engine argument)
SHOW_ENGINE_ALIASES = {
    'auto': 'auto',
    'html': 'html',
    'md': 'md', 'markdown': 'md',
    'tex': 'tex', 'latex': 'tex',
    'typ': 'typst', 'typst': 'typst',
    'rich': 'rich', 'console': 'console', 'terminal': 'terminal', 'plain': 'plain',
}

#: bare template format names (for the ``template`` command) to file extension
TEMPLATE_FORMAT_EXTS = {'html': '.html', 'htm': '.html', 'tex': '.tex',
                       'latex': '.tex', 'typ': '.typ', 'typst': '.typ'}

#: file extensions recognized as (direct or jinja2) template files
TEMPLATE_FILE_EXTS = ('.html', '.tex', '.typ', '.j2', '.jinja', '.jinja2', '.j')

#: file extensions of legacy jinja2 template files (kept verbatim, not baked)
JINJA_TEMPLATE_EXTS = ('.j2', '.jinja', '.jinja2', '.j')

#: matches strings that look like a file name (``something.ext`` with an
#: alphanumeric extension of 1-8 characters and no braces)
FILENAME_LIKE_RE = re.compile(r'^[^{}]+\.[A-Za-z0-9]{1,8}$')

#: latex source patterns that reference external files (group 1 = the reference)
TEX_FILE_REF_RES = (
    re.compile(r'\\includegraphics\*?(?:\[[^\]]*\])?\{([^{}]+)\}'),
    re.compile(r'\\(?:input|include|lstinputlisting|bibliography|addbibresource)\{([^{}]+)\}'),
)

#: typst source patterns that reference external files (group 1 = the
#: reference; single and double quotes are accepted). The function calls
#: appear with or without a leading ``#`` (inside content blocks), so only a
#: word boundary is required.
TYP_FILE_REF_RES = (
    re.compile(r'\b(?:image|bibliography|json|yaml|csv|toml|xml)\(\s*["\']([^"\']+)["\']'),
    re.compile(r'\bread\(\s*["\']([^"\']+)["\']'),
    re.compile(r'\binclude\s+["\']([^"\']+)["\']'),
)

#: matches the latex macro defined by a template parameter assignment
#: (e.g. ``\providecommand{\pProjectLogo}{...}`` -> ``pProjectLogo``)
TEX_MACRO_DEF_RE = re.compile(
    r'\\(?:providecommand|newcommand|renewcommand|gdef|edef|xdef|def|let)\*?'
    r'\s*(?:\[[^\]]*\])?\s*\{\s*\\([A-Za-z]+)\s*\}')


class CliError(Exception):
    """A user facing error which is reported without a python traceback."""


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def _info(msg):
    """Print a status message to stderr.

    stdout is strictly reserved for document data (so commands can be piped),
    therefore all informational messages go to stderr.

    Args:
        msg (str): the message to print.
    """
    print(msg, file=sys.stderr)


def _parse_param_value(text):
    """Parse a template parameter value given on the command line.

    ``None`` (a bare flag like ``--pFlag``) becomes ``True``; otherwise the
    value is JSON-parsed when possible (``5`` -> 5, ``true`` -> True,
    ``{"a": 1}`` -> dict) and kept as a string otherwise (``me`` -> "me").

    Args:
        text (str | None): the raw value string or None for a bare flag.

    Returns:
        object: the parsed parameter value.
    """
    if text is None:
        return True
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text


def _load_params_json_file(path):
    """Load a template parameters JSON object from a file.

    Args:
        path (str): path of the JSON file; its top level content must be a
            JSON object (mapping).

    Returns:
        dict: the loaded parameters.

    Raises:
        CliError: when the file is missing, unreadable or not a JSON object.
    """
    if not os.path.isfile(path):
        raise CliError(f'parameters file not found: {path}')
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except (OSError, ValueError) as err:
        raise CliError(f'could not read parameters file {path!r}: {err}')
    if not isinstance(data, dict):
        raise CliError(f'parameters file {path!r} must contain a JSON object (mapping), '
                       f'got {type(data).__name__}')
    return data


def _load_parameters(spec):
    """Parse the value of ``-p/--parameters``.

    Accepted inputs are a JSON object string (``'{"pTitle": "X"}'``), a path
    to a JSON file (``params.json``) or an explicitly marked file
    (``@params.json``).

    Args:
        spec (str | None): the raw ``--parameters`` value.

    Returns:
        dict: the template parameters.

    Raises:
        CliError: when the value is neither valid JSON nor an existing file,
        or when it is not a JSON object.
    """
    if not spec or not str(spec).strip():
        return {}
    text = str(spec).strip()
    if text.startswith('@'):
        return _load_params_json_file(text[1:])
    try:
        data = json.loads(text)
    except ValueError:
        if os.path.isfile(text):
            return _load_params_json_file(text)
        raise CliError(
            '--parameters expects a JSON object string or a JSON file; '
            f'{spec!r} is neither valid JSON nor an existing file')
    if not isinstance(data, dict):
        raise CliError(f'--parameters must be a JSON object (mapping), '
                       f'got {type(data).__name__}')
    return data


def _verbosity(args):
    """Read the verbosity level given via ``-v/--verbosity``.

    Args:
        args (argparse.Namespace): the parsed arguments namespace.

    Returns:
        int: the verbosity level (0 = quiet, 1 = normal status messages,
        2 = more details, 3+ = full backend output; default 1).
    """
    try:
        return max(0, int(getattr(args, 'verbosity', 0)))
    except (TypeError, ValueError):
        return 0


def _merged_params(args):
    """Combine the parameters from ``-p/--parameters`` and unknown arguments.

    The parameters collected from unknown command line arguments (see
    ``_extract_template_params``) override the values from the ``-p`` JSON.

    Args:
        args (argparse.Namespace): the parsed arguments namespace.

    Returns:
        dict: the merged template parameters.
    """
    params = _load_parameters(getattr(args, 'parameters', None))
    params.update(getattr(args, 'cli_params', None) or {})
    return params


def _looks_like_option(token):
    """Check whether a token looks like an option (not a parameter value).

    Negative numbers (``-2``, ``-.5``) are considered values so they can be
    used as template parameter values.

    Args:
        token (str): the command line token to inspect.

    Returns:
        bool: True when the token should be treated as an option.
    """
    if not token.startswith('-') or len(token) <= 1:
        return False
    return not token[1:2].isdigit() and token[1:2] != '.'


def _match_known_option(token, spec):
    """Match an option token against the known options of one parser context.

    Mirrors argparse's behavior: exact matches win, otherwise a unique prefix
    (abbreviation) of a known long option is accepted.

    Args:
        token (str): the option token (e.g. ``'--template'``).
        spec (tuple): the (value_options, flag_options) sets of the context.

    Returns:
        str | None: 'value' when the option consumes a value, 'flag' when it
        does not and None when the option is unknown or ambiguous.
    """
    value_opts, flag_opts = spec
    if token in value_opts:
        return 'value'
    if token in flag_opts:
        return 'flag'
    if token.startswith('--'):
        matches = {o for o in (value_opts | flag_opts)
                   if o.startswith('--') and o.startswith(token)}
        if len(matches) == 1:
            match = next(iter(matches))
            return 'value' if match in value_opts else 'flag'
    return None


def _collect_option_specs(parser):
    """Collect the known option strings of a parser and its subcommands.

    Used by ``_extract_template_params`` to decide which command line
    arguments are unknown (and therefore template parameters).

    Args:
        parser (argparse.ArgumentParser): the parser to inspect.

    Returns:
        dict: maps the context name ('' for the top level parser, the
        subcommand name otherwise) to a (value_options, flag_options) tuple.
    """
    value_opts, flag_opts = set(), set()
    subs = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subs = action.choices
            continue
        if not action.option_strings:
            continue  # positionals
        if action.nargs == 0:
            flag_opts.update(action.option_strings)  # store_true / help / version
        else:
            value_opts.update(action.option_strings)
    specs = {'': (value_opts, flag_opts)}
    if subs:
        for name, sub in subs.items():
            for ctx, spec in _collect_option_specs(sub).items():
                specs[name if ctx == '' else f'{name} {ctx}'] = spec
    return specs


def _extract_template_params(argv, specs):
    """Split unknown ``--name value`` arguments out of an argument list.

    This runs *before* argparse so that additional (unknown) long options can
    be used as template parameters without argparse rejecting them. A token
    starting with ``--`` that is not a known option (nor a unique abbreviation
    of one) in the current context is collected as a parameter; its value is
    the following token (when it does not look like an option), an inline
    ``--name=value`` value or ``True`` for a bare flag. Known options and
    their values are passed through to argparse untouched.

    Extraction only happens for the templating commands (example, show,
    build, convert) and before the subcommand is known; once a non-templating
    command (check, extract, template) is seen, everything else passes through
    so argparse reports its usual argument errors.

    Args:
        argv (list[str]): the raw command line arguments.
        specs (dict): the parser option specs from ``_collect_option_specs``.

    Returns:
        tuple[list, dict]: the cleaned argument list for argparse and the
        collected template parameters.
    """
    templating_cmds = ('example', 'show', 'build', 'convert')
    params = {}
    clean = []
    context = ''
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == '--':
            clean.extend(argv[i:])
            break
        if token.startswith('--'):
            body = token[2:]
            if '=' in body:
                name, value, has_eq = body.split('=', 1)[0], body.split('=', 1)[1], True
            else:
                name, value, has_eq = body, None, False
            matched = _match_known_option('--' + name, specs.get(context, (set(), set())))
            if matched == 'value' and not has_eq and i + 1 < len(argv):
                # known option: pass it and its value through untouched
                clean.append(token)
                i += 1
                clean.append(argv[i])
            elif matched is not None:
                clean.append(token)
            elif context == '' or context in templating_cmds:
                # unknown long option -> template parameter
                if not has_eq and i + 1 < len(argv) and not _looks_like_option(argv[i + 1]):
                    i += 1
                    value = argv[i]
                params[name] = _parse_param_value(value)
            else:
                clean.append(token)
        elif _looks_like_option(token):
            # unknown single-dash options are left to argparse (which reports
            # them as errors); known ones (with their value) pass through
            spec = specs.get(context, (set(), set()))
            clean.append(token)
            if token in spec[0] and i + 1 < len(argv):
                i += 1
                clean.append(argv[i])
        else:
            clean.append(token)
            if context == '' and token in specs:
                context = token
        i += 1
    return clean, params


def _norm_format(fmt, what='format'):
    """Normalize a user given format name to its canonical form.

    Args:
        fmt (str | None): the format name as given by the user (case
            insensitive, a leading dot is ignored). ``None``/'' pass through as
            ``None`` so callers can apply their own defaults.
        what (str): how the value is called in error messages.

    Returns:
        str | None: the canonical format name (see ``FORMAT_ALIASES``).

    Raises:
        CliError: when the name is not a known format.
    """
    if fmt is None:
        return None
    key = str(fmt).strip().lower().lstrip('.')
    if not key:
        return None
    if key not in FORMAT_ALIASES:
        supported = ', '.join(sorted(set(FORMAT_ALIASES)))
        raise CliError(f'unknown {what} {fmt!r}. supported {what}s: {supported}')
    return FORMAT_ALIASES[key]


def _format_from_path(path):
    """Infer the canonical output format from a file name's extension.

    Args:
        path (str | os.PathLike): the file name to inspect.

    Returns:
        str | None: the canonical format or None when the extension is not
        recognized.
    """
    p = str(path).lower()
    for suffix, fmt in SUFFIX_FORMATS:
        if p.endswith(suffix):
            return fmt
    return None


def _read_text_file(path):
    """Read a file as utf-8 text, raising friendly errors for binary files.

    Args:
        path (str): path of the file to read.

    Returns:
        str: the decoded file content (a utf-8 BOM is stripped).

    Raises:
        CliError: when the file does not exist, cannot be read or is binary.
    """
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except FileNotFoundError:
        raise CliError(f'input file not found: {path}')
    except OSError as err:
        raise CliError(f'cannot read input file {path!r}: {err}')
    except UnicodeDecodeError as err:
        raise CliError(f'{path} is not a text file (binary content cannot be read): {err}')
    if '\x00' in content:
        raise CliError(f'{path} appears to be a binary file; only text documents can be read')
    return content


def _load_input_doc(path, nocode=False):
    """Load any supported input document into a ``Doc``.

    The loader dispatches on the file extension:

    * ``.json`` / ``.html`` / ``.htm`` / ``.pyd`` / ``.pydoc`` / ``.ipynb`` --
      lossless pydocmaker documents read via ``Doc.load`` (see ``Doc.save``
      and ``html_loader.py`` / ``ipynb_loader.py``).
    * ``.md`` / ``.markdown`` -- the file content is added as a markdown part
      (``Doc.add_md``).
    * ``.tex`` / ``.latex`` -- the file content is added as a latex part
      (``Doc.add_tex``).
    * ``.typ`` / ``.typst`` -- the file content is added as a typst part and
      marked for typst compilation.
    * anything else -- the file is read as plain (non-binary) text and added
      via ``Doc.add_text``.

    Args:
        path (str): path of the input document.
        nocode (bool): if True and the input is an ipynb file, exclude code
            cells from the loaded document.

    Returns:
        Doc: the loaded document.

    Raises:
        CliError: when the file is missing, binary or not a valid pydocmaker
        document.
    """
    ext = os.path.splitext(str(path))[1].lower()
    if ext in PYDOCMAKER_DOC_EXTS:
        try:
            doc = Doc.load(path)
            # If the loaded document is a notebook (has notebook metadata) and
            # nocode is set, reload it through the notebook loader with nocode=True
            if nocode and ext == '.ipynb':
                from pydocmaker.io.ipynb_loader import load_notebook
                doc = load_notebook(path, nocode=True)
            return doc
        except Exception as err:
            raise CliError(f'could not load pydocmaker document {path!r}: {err}')
    text = _read_text_file(path)
    if ext in ('.md', '.markdown'):
        return Doc().add_md(text)
    if ext in ('.tex', '.latex'):
        return Doc().add_tex(text)
    if ext in ('.typ', '.typst'):
        doc = Doc()
        doc.add_text(text)
        doc.set_meta({"_raw_typst_file": text})
        return doc
    return Doc().add_text(text)


def _expand_input_pattern(path):
    """Expand a single ``build``/``convert`` input argument into file paths.

    Arguments containing glob wildcards (``*``, ``?`` or ``[``) are expanded
    with ``glob.glob`` (``**`` works recursively) and the matches are sorted
    for a deterministic order; only existing files are kept. A pattern that
    matches nothing (or only directories) raises an error. Plain paths are
    returned unchanged (their existence is checked later by the loader).

    Args:
        path (str): the raw input argument (a file path or a glob pattern).

    Returns:
        list[str]: the input file paths to build (one or more).

    Raises:
        CliError: when a pattern does not match any file.
    """
    path = str(path)
    if not any(ch in path for ch in '*?['):
        return [path]
    matches = sorted(m for m in glob.glob(path, recursive=True) if os.path.isfile(m))
    if not matches:
        raise CliError(f'the input pattern {path!r} did not match any files')
    return matches


def _warn_template_ignored(template_arg, what):
    """Warn that a given template has no effect for a target format.

    Args:
        template_arg (str | None): the template as given by the user.
        what (str): description of the target (e.g. 'md output').
    """
    if template_arg:
        _info(f'warning: the template {template_arg!r} has no effect for {what}')


def _is_docx_template(template_arg):
    """Check whether the template argument is a path to an existing .docx file.

    Args:
        template_arg (str | None): the template as given by the user.

    Returns:
        bool: True when the template is a usable docx template file path.
    """
    return bool(template_arg) and os.path.isfile(template_arg) \
        and str(template_arg).lower().endswith('.docx')


def _export_doc_to_file(doc, out_path, fmt, template_arg=None, files_to_upload=None, verb=0, pdf_engine=None, pdf_template=None):
    """Write a document to a file path in a given canonical format.

    Text templates (html/tex/typ) are applied beforehand via the document
    metadata (see ``_apply_template_and_params``); a docx template file is
    forwarded to the docx exporter here. ``files_to_upload`` (attachment
    bytes keyed by reference) is only used for pdf exports, where the
    compile runs in an isolated directory. ``verb`` is the verbosity level
    passed through to the export backends that support it (pdf, tex and
    typst; 0 = quiet, 1 = normal status messages, 2+ = debug output).
    ``pdf_engine`` optionally forces the pdf engine (e.g. 'tex' for plain
    latex inputs); when None the engine is chosen by ``Doc.to_pdf``.
    ``pdf_template`` optionally overrides the pdf template (an empty string
    renders the document body verbatim without a preamble wrapper).

    Args:
        doc (Doc): the document to export.
        out_path (str): the destination file path.
        fmt (str): the canonical output format (see ``FORMAT_ALIASES``).
        template_arg (str | None): the template as given by the user (only
            used for docx template files and no-effect warnings).
        files_to_upload (dict | None): attachment bytes (``{key: bytes}``)
            written into the pdf build directory (pdf only).
        verb (int): verbosity level for the export backends.
        pdf_engine (str | None): pdf engine to force (pdf only), e.g. 'tex'.
        pdf_template (str | None): pdf template override (pdf only); an
            empty string compiles the document body as a standalone document.

    Returns:
        str: the path that was written.

    Raises:
        CliError: when the export fails (e.g. missing pdf engine).
    """
    try:
        if fmt == 'pdf':
            if files_to_upload:
                doc.to_pdf(str(out_path), engine=pdf_engine, template=pdf_template,
                           files_to_upload=files_to_upload, verb=verb)
            else:
                doc.to_pdf(str(out_path), engine=pdf_engine, template=pdf_template, verb=verb)
        elif fmt == 'md':
            _warn_template_ignored(template_arg, 'markdown output')
            doc.to_markdown(str(out_path))
        elif fmt == 'html':
            doc.to_html(str(out_path))
        elif fmt == 'typst':
            doc.to_typst(str(out_path), verb=verb)
        elif fmt == 'tex':
            # a path ending in ".tex"/".latex" gets the plain latex source,
            # any other suffix (e.g. ".zip") gets the zipped latex project
            doc.to_tex(str(out_path), verb=verb)
        elif fmt == 'json':
            _warn_template_ignored(template_arg, 'json output')
            doc.to_json(str(out_path))
        elif fmt == 'docx':
            if _is_docx_template(template_arg):
                doc.to_docx(str(out_path), template=str(template_arg))
            else:
                _warn_template_ignored(template_arg, 'docx output (docx templates '
                                        'must be .docx files given via -t)')
                doc.to_docx(str(out_path))
        elif fmt == 'ipynb':
            _warn_template_ignored(template_arg, 'ipynb output')
            doc.to_ipynb(str(out_path))
        elif fmt == 'textile':
            _warn_template_ignored(template_arg, 'textile output')
            doc.to_textile(str(out_path))
        elif fmt == 'pydoc':
            _warn_template_ignored(template_arg, 'pydoc output')
            # lossless pydocmaker round-trip document (Doc.save)
            doc.save(str(out_path), format='pyd')
        else:  # pragma: no cover - _norm_format guards against this
            raise CliError(f'unsupported export format: {fmt!r}')
    except CliError:
        raise
    except Exception as err:
        raise CliError(f'could not export document to {out_path!r} ({fmt}): {err}')
    return str(out_path)


def _export_doc_to_stdout(doc, fmt, template_arg=None, verb=0):
    """Write a document to stdout in a given canonical format.

    Text based formats are printed as strings; binary formats (pdf, docx) are
    written raw to ``sys.stdout.buffer`` so they can be piped into files. When
    stdout is an interactive terminal and the format is binary an error is
    raised instead (to avoid dumping binary data into the terminal).

    Text templates (html/tex/typ) are applied beforehand via the document
    metadata (see ``_apply_template_and_params``); a docx template file is
    forwarded to the docx exporter here. ``verb`` is the verbosity level
    passed through to the export backends that support it (pdf, tex and
    typst; 0 = quiet, 1 = normal status messages, 2+ = debug output).

    Args:
        doc (Doc): the document to export.
        fmt (str): the canonical output format (see ``FORMAT_ALIASES``).
        template_arg (str | None): the template as given by the user (only
            used for docx template files and no-effect warnings).
        verb (int): verbosity level for the export backends.

    Raises:
        CliError: when the format is binary and stdout is a terminal, or the
        export fails.
    """
    try:
        if fmt in BINARY_FORMATS:
            if fmt == 'docx' and _is_docx_template(template_arg):
                data = doc.to_docx(template=str(template_arg))
            else:
                if fmt == 'docx':
                    _warn_template_ignored(template_arg, 'docx output (docx templates '
                                            'must be .docx files given via -t)')
                data = doc.to_pdf(verb=verb) if fmt == 'pdf' else doc.to_docx()
            if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
                raise CliError(
                    f'the {fmt!r} format is binary; give an output file with -o/--out '
                    f'(or redirect stdout to a file)')
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
            return
        if fmt == 'md':
            _warn_template_ignored(template_arg, 'markdown output')
            out = doc.to_markdown()
        elif fmt == 'html':
            out = doc.to_html()
        elif fmt == 'typst':
            out = doc.to_typst(verb=verb)
        elif fmt == 'tex':
            out = doc.to_tex(text_only=True, verb=verb)
        elif fmt == 'json':
            _warn_template_ignored(template_arg, 'json output')
            out = doc.to_json()
        elif fmt == 'ipynb':
            _warn_template_ignored(template_arg, 'ipynb output')
            out = doc.to_ipynb()
        elif fmt == 'textile':
            _warn_template_ignored(template_arg, 'textile output')
            out = doc.to_textile(text_only=True)
        elif fmt == 'pydoc':
            _warn_template_ignored(template_arg, 'pydoc output')
            out = doc.save(format='pyd')
        else:  # pragma: no cover - _norm_format guards against this
            raise CliError(f'unsupported export format: {fmt!r}')
    except CliError:
        raise
    except Exception as err:
        raise CliError(f'could not export document ({fmt}): {err}')
    sys.stdout.write(out)
    if not out.endswith('\n'):
        sys.stdout.write('\n')


# --------------------------------------------------------------------------- #
# template helpers (for the "template", "check" and "extract" commands)
# --------------------------------------------------------------------------- #

def _normalize_template_request(name):
    """Normalize the input string of the ``template`` command.

    A bare format name (``html``, ``tex``, ``typ`` and common aliases) maps to
    the base template of that format (``base.html``, ``base.tex``,
    ``base.typ``); anything else (a template id or file name) is used as-is.

    Args:
        name (str): the user given input string.

    Returns:
        str: the template name to look up.
    """
    name = str(name).strip().replace('\\', '/')
    if name.startswith('./'):
        name = name[2:]
    key = name.lower()
    if key in TEMPLATE_FORMAT_EXTS:
        return 'base' + TEMPLATE_FORMAT_EXTS[key]
    return name


def _find_template_file(name):
    """Locate the on-disk file of a registered template.

    The name is resolved against the registered template directories (the
    package template directory plus anything registered with
    ``register_new_template_dir``). Exact file matches win; a bare template id
    without extension is completed with the format extensions (new block
    templates first, then the legacy ``.j2`` jinja2 variants); as a last
    resort the library's own ``resolve_template_id`` logic is used.

    Args:
        name (str): template name, id or bare format (already normalized by
            ``_normalize_template_request`` or a raw file name).

    Returns:
        str: the absolute path of the template file.

    Raises:
        CliError: when no matching template file can be found.
    """
    name = _normalize_template_request(name)
    dirs = get_registered_template_dirs(include_default=True)

    candidates = [name]
    if not name.lower().endswith(TEMPLATE_FILE_EXTS):
        # bare id: prefer the new block templates over the legacy .j2 files
        candidates += [name + ext for ext in ('.typ', '.tex', '.html')]
        candidates += [name + ext for ext in ('.typ.j2', '.tex.j2', '.html.j2')]
    for candidate in candidates:
        for d in dirs:
            p = os.path.join(d, candidate)
            if os.path.isfile(p):
                return p

    # fall back to the library's template id resolution (handles ids which
    # only exist as .j2 files or live in subdirectories)
    try:
        resolved = resolve_template_id(name, on_error=None)
    except Exception:  # pragma: no cover - resolve_template_id misbehaving
        resolved = None
    if resolved:
        for d in dirs:
            p = os.path.join(d, resolved)
            if os.path.isfile(p):
                return p

    available = ', '.join(sorted(get_available_template_ids())) or '(none)'
    raise CliError(
        f'template {name!r} not found. available template ids: {available}. '
        f'the input can be a format ("html", "tex", "typ"), a template id '
        f'("base", "report") or a template file name ("base.html").')


#: keeps the temporary template directories alive until the process ends
_RAW_TEMPLATE_DIRS = []


def _register_raw_template_file(template, source=None):
    """Register a raw template file in a throwaway template directory.

    The file is copied into a temporary directory which is registered with
    ``register_new_template_dir``, so the file becomes a regular template id
    and can be attached to a document through ``Doc.set_template_to_meta``
    (with full default parameter and asset handling). The registered file
    name keeps the ``name.{format}.{ext}`` pattern the template id resolution
    expects (e.g. ``report.html.j2`` or ``base.typ``). Sources without block
    markers are scaffolded in memory first; jinja2 files (``.j2`` family) are
    registered unchanged.

    Args:
        template (str): path of the template file.
        source (str | None): the template content; when None the file is read
            from disk. Used to register a pre-processed variant of the file
            (e.g. with parameter assignments rewritten, see
            ``_bake_macro_named_params``).

    Returns:
        str: the template id under which the file is now registered.

    Raises:
        CliError: when the file cannot be read or its format cannot be
        determined.
    """
    import hashlib
    import tempfile

    if source is None:
        source = _read_text_file(template)
    name = os.path.basename(str(template))

    # split the name into stem, document format extension and jinja extension
    # (e.G. "report.html.j2" -> "report", ".html", ".j2")
    jinja_ext = next((e for e in JINJA_TEMPLATE_EXTS if name.endswith(e)), '')
    base = name[:len(name) - len(jinja_ext)] if jinja_ext else name
    stem, doc_ext = os.path.splitext(base)
    stem = stem.replace('.', '_')

    # the document format for the extension (without the leading dot)
    tformat = {'.html': 'html', '.htm': 'html', '.tex': 'tex',
               '.latex': 'tex', '.typ': 'typ'}.get(doc_ext.lower())

    if jinja_ext and not tformat:
        # a jinja file without a document format extension (e.g. "x.j2"):
        # sniff the format from the content so the id stays resolvable
        tformat = blocktmpl.detect_format(source)
        if tformat is None:
            raise CliError(
                f'cannot determine the format of template {template!r}; name jinja '
                f'templates like "name.html.j2", "name.tex.j2" or "name.typ.j2"')

    if not jinja_ext and not blocktmpl.detect(source):
        # unmarked source: scaffold the block markers in memory so the file
        # becomes a valid (block) template
        if tformat is None:
            tformat = blocktmpl.detect_format(source)
            if tformat is None:
                raise CliError(
                    f'cannot determine the format of template {template!r}; give the '
                    f'file a .html, .tex or .typ extension')
        try:
            source = blocktmpl.scaffold(source, tformat=tformat)
        except blocktmpl.BlockTemplatingError as err:
            raise CliError(f'could not prepare template {template!r}: {err}')
        doc_ext = {'html': '.html', 'tex': '.tex', 'typ': '.typ'}[tformat]

    # a unique id prevents collisions with (and shadowing of) the package
    # templates, e.G. when the user file happens to be called "base.typ"
    digest = hashlib.md5(os.path.abspath(str(template)).encode('utf-8')).hexdigest()[:8]
    template_id = f'cli_{digest}_{stem}{doc_ext}{jinja_ext}'

    try:
        tdir = tempfile.TemporaryDirectory(prefix='pydocmaker-cli-template-')
        with open(os.path.join(tdir.name, template_id), 'w', encoding='utf-8') as f:
            f.write(source)
        from pydocmaker.templating import register_new_template_dir
        register_new_template_dir(tdir.name)
    except OSError as err:
        raise CliError(f'could not register template {template!r}: {err}')
    _RAW_TEMPLATE_DIRS.append(tdir)  # keep the directory alive
    return template_id


def _first_existing_file(locations):
    """Return the first existing file of a list of candidate locations.

    Args:
        locations (list[str]): candidate file paths (duplicates are fine).

    Returns:
        str | None: the first candidate that is an existing file, or None.
    """
    for loc in locations:
        if os.path.isfile(loc):
            return loc
    return None


def _template_file_tformat(path, source):
    """Determine the template format of a raw template file.

    Mirrors the name analysis of ``_register_raw_template_file``: the document
    format extension of the file name (``.tex``, ``.typ``, ``.html``, also
    behind a jinja extension like ``.tex.j2``) wins; otherwise the format is
    sniffed from the content.

    Args:
        path (str): the template file path.
        source (str): the template file content.

    Returns:
        str | None: 'html', 'tex', 'typ' or None when unknown.
    """
    name = os.path.basename(str(path))
    jinja_ext = next((e for e in JINJA_TEMPLATE_EXTS if name.endswith(e)), '')
    base = name[:len(name) - len(jinja_ext)] if jinja_ext else name
    doc_ext = os.path.splitext(base)[1].lower()
    tformat = {'.html': 'html', '.htm': 'html', '.tex': 'tex',
               '.latex': 'tex', '.typ': 'typ'}.get(doc_ext)
    if tformat is None:
        tformat = blocktmpl.detect_format(source)
    return tformat


def _find_template_file_references(source, tformat, base_dir=None):
    """Scan a template source for references to external files.

    The scan collects references from format specific patterns
    (``\\includegraphics{...}`` and friends for latex, ``#image("...")`` and
    friends for typst) plus scalar block-template parameter defaults that look
    like file names (which catches macro-indirected references such as
    ``\\includegraphics{\\pProjectLogo}`` whose ``\\providecommand`` default is
    an image file). Candidates that contain a macro (``\\``), a jinja
    expression (``{{``/``}}``) or start with ``http`` are skipped. Each
    remaining candidate is resolved as given (absolute paths), relative to
    ``base_dir`` (the template's directory) and relative to the current
    working directory; found files are returned as attachment bytes keyed by
    the reference as written (forward slashes). Candidates that look like a
    file name but cannot be resolved produce a warning on stderr (the build
    itself continues).

    Args:
        source (str): the template source.
        tformat (str | None): the template format ('tex', 'typ', 'html' or
            None to only analyze block-template parameter defaults).
        base_dir (str | None): directory of the template file, tried before
            the current working directory for relative references.

    Returns:
        tuple[dict, list]: the found attachments (``{key: bytes}``) and the
        list of references that could not be resolved to an existing file.
    """
    refs = []
    for pattern in (TEX_FILE_REF_RES if tformat == 'tex'
                    else TYP_FILE_REF_RES if tformat == 'typ' else ()):
        refs += pattern.findall(source)

    # block-template parameter defaults that look like file names
    try:
        bdoc = blocktmpl.parse(source, tformat=tformat, strict=False)
    except Exception:
        bdoc = None
    if bdoc is not None and bdoc.params_section is not None:
        for param in bdoc.params_section.params.values():
            if param.kind == 'scalar' and isinstance(param.value, str):
                value = param.value.strip()
                if FILENAME_LIKE_RE.match(value):
                    refs.append(value)

    attachments = {}
    unresolved = []
    seen = set()
    for candidate in refs:
        ref = str(candidate).strip()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        if '\\' in ref or '{{' in ref or '}}' in ref or ref.startswith('http'):
            continue  # macro, jinja expression or url
        locations = [ref]
        if base_dir:
            locations.append(os.path.join(base_dir, ref))
        locations.append(os.path.join(os.getcwd(), ref))
        path = _first_existing_file(locations)
        if path is None:
            unresolved.append(ref)
            if FILENAME_LIKE_RE.match(ref):
                _info(f'warning: template references {ref!r} but no such file was '
                      f'found (next to the template or in the working directory)')
            continue
        try:
            with open(path, 'rb') as f:
                attachments[ref.replace('\\', '/')] = f.read()
        except OSError as err:
            _info(f'warning: could not read template reference {ref!r} '
                  f'({path!r}): {err}')
    return attachments, unresolved


def _load_param_file_values(params, template_dir=None):
    """Resolve template parameter values that point at existing files.

    String parameter values that look like a file name (``logo.png``) and
    exist -- relative to the template directory first, then the current
    working directory, then as an absolute path -- are loaded as attachments
    (keyed by the file's basename) and the parameter value is rewritten to
    that bare basename so template macros resolve in the build directory.
    When several parameters resolve to *different* files with the same
    basename a warning is printed and the last one wins.

    Args:
        params (dict): the merged template parameters (modified in place).
        template_dir (str | None): directory of the template (raw file or
            registered template id), tried before the working directory.

    Returns:
        dict: the loaded attachments (``{basename: bytes}``).
    """
    attachments = {}
    sources = {}  # attachment key -> resolved path (for collision warnings)
    for name, value in list(params.items()):
        if not isinstance(value, str):
            continue
        ref = value.strip()
        if not FILENAME_LIKE_RE.match(ref):
            continue
        locations = []
        if template_dir:
            locations.append(os.path.join(template_dir, ref))
        locations.append(os.path.join(os.getcwd(), ref))
        locations.append(ref)  # absolute paths
        path = _first_existing_file(locations)
        if path is None:
            continue  # a plain text value, not a file
        key = os.path.basename(path)
        prev = sources.get(key)
        if prev is not None and os.path.normpath(prev) != os.path.normpath(path):
            _info(f'warning: template parameters resolve to different files with '
                  f'the attachment name {key!r}; the last one wins')
        sources[key] = path
        try:
            with open(path, 'rb') as f:
                attachments[key] = f.read()
        except OSError as err:
            _info(f'warning: could not read parameter file {path!r}: {err}')
            continue
        params[name] = key
    return attachments


def _load_assets_paths(paths):
    """Load additional attachment paths given via ``-a/--assets``.

    Each path is either a file -- attached under its basename -- or a
    directory, which is walked recursively with the files attached under
    their path relative to the directory (posix separators). Hidden files,
    hidden directories and ``__pycache__`` directories are excluded.

    Args:
        paths (list[str] | None): the paths given via ``-a/--assets``.

    Returns:
        dict: the loaded attachments (``{key: bytes}``).

    Raises:
        CliError: when a path does not exist or a file cannot be read.
    """
    attachments = {}
    for path in paths or []:
        p = str(path)
        if os.path.isfile(p):
            try:
                with open(p, 'rb') as f:
                    attachments[os.path.basename(p)] = f.read()
            except OSError as err:
                raise CliError(f'could not read assets file {p!r}: {err}')
        elif os.path.isdir(p):
            root = os.path.abspath(p)
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames
                               if not d.startswith('.') and d != '__pycache__']
                for fn in filenames:
                    if fn.startswith('.'):
                        continue
                    fp = os.path.join(dirpath, fn)
                    try:
                        with open(fp, 'rb') as f:
                            attachments[os.path.relpath(fp, root)
                                        .replace(os.sep, '/')] = f.read()
                    except OSError as err:
                        raise CliError(f'could not read assets file {fp!r}: {err}')
        else:
            raise CliError(f'assets path not found: {p}')
    return attachments


def _merge_attachments_into_meta(doc, attachments):
    """Merge attachment bytes into the document metadata.

    The attachments are added to ``meta['files_to_upload']`` (base64 encoded,
    the same mechanism ``Doc.set_template_to_meta`` uses for template assets),
    overwriting existing entries with the same key. Unlike the template
    directory asset convention this supports nested keys such as
    ``images/logo.png``.

    Args:
        doc (Doc): the document to update.
        attachments (dict): the attachments to merge (``{key: bytes}``).
    """
    if not attachments:
        return
    meta = doc.get_meta({}).get('data', {})
    ftu = meta.setdefault('files_to_upload', {})
    for key, data in attachments.items():
        ftu[key] = base64.b64encode(data).decode() if isinstance(data, bytes) else data
    doc.update_meta(meta)  # mirror set_template_to_meta's mutation pattern


def _bake_macro_named_params(source, tformat, params):
    """Rewrite latex template assignments for parameters given by macro name.

    Latex block templates may declare a parameter under a snake_case marker
    name (``p_projectlogo``) while the assignment defines a camelCase macro
    (``\\providecommand{\\pProjectLogo}{...}``). A parameter override given on
    the command line under the *macro* name (``--pProjectLogo``) does not
    match the marker name, so the render engine would append it as a new
    assignment where a second ``\\providecommand`` cannot override the
    existing definition. This helper instead rewrites the matched assignment
    in the template source directly (keeping its macro) and removes the
    parameter from the override mapping.

    Args:
        source (str): the template source.
        tformat (str | None): the template format (only 'tex' is rewritten).
        params (dict): the template parameter overrides (updated in place).

    Returns:
        tuple[str, dict]: the rewritten source and the remaining parameters.
    """
    if not params or tformat != 'tex':
        return source, params
    try:
        bdoc = blocktmpl.parse(source, tformat=tformat, strict=False)
    except Exception:
        return source, params
    if bdoc.params_section is None:
        return source, params

    # macro name -> template parameter whose assignment defines that macro
    by_macro = {}
    for param in bdoc.params_section.params.values():
        if param.assign_lines is None:
            continue
        m = TEX_MACRO_DEF_RE.search(param.raw or '')
        if m:
            by_macro.setdefault(m.group(1), param)

    adapter = blocktmpl.get_adapter('tex')
    term = '\r\n' if '\r\n' in source else '\n'
    lines = source.splitlines(keepends=True)
    ops = []
    for name, value in list(params.items()):
        if value is None or name in bdoc.params_section.params:
            continue
        param = by_macro.get(str(name).replace('_', ''))
        if param is None:
            continue
        try:
            assign = adapter.serialize_param(name, value)
        except blocktmpl.ParameterTypeError:
            continue  # leave the complaint to the render engine
        if not assign:
            continue
        new_lines = [al + term for al in assign.splitlines()]
        ops.append((param.assign_lines[0], param.assign_lines[1], new_lines))
        del params[name]
    if not ops:
        return source, params
    for start, stop, new_lines in sorted(ops, key=lambda op: op[0], reverse=True):
        lines[start:stop] = new_lines
    return ''.join(lines), params


def _apply_template_and_params(doc, template, params, assets=None):
    """Attach a template, template parameters and attachments to a document.

    The template is applied through the document metadata (the mechanism the
    pydocmaker exporters use via ``Doc.get_template_from_meta``), so every
    template aware export (pdf, html, typst, tex) picks it up automatically.
    Three kinds of templates are supported:

    * a template id (e.g. ``base`` or ``base.tex``) -- resolved from the
      registered template directories via ``Doc.set_template_to_meta``,
      which also copies the template's default parameters and assets. For a
      bare id the per-format variant matching the output format is used;
    * an existing file path -- the file is registered as an ad-hoc template
      (see ``_register_raw_template_file``) and then treated like an id.
      Sources without block markers are scaffolded first;
    * a .docx file path -- not attached here (docx templates are binary
      files and are forwarded to the docx exporter directly).

    For a raw template *file* the source is additionally scanned for
    references to external files (``\\includegraphics``, ``#image``, ... and
    block-template parameter defaults that look like file names) and every
    found file is loaded as an attachment. String parameter values that point
    at existing files (searched next to the template first, then in the
    working directory, then as absolute paths) are loaded as attachments as
    well and rewritten to their bare basename. Extra attachment paths given
    via ``assets`` (``-a/--assets``) are loaded the same way. All of them
    are merged into the document metadata next to the template assets.

    Parameters without a template are stored in the metadata as well, where
    they parameterize the default template of the target format.

    Args:
        doc (Doc): the document to attach the template to.
        template (str | None): a template file path or template id.
        params (dict | None): template parameters to merge into the metadata
            (overriding template defaults).
        assets (list[str] | None): additional attachment paths (files or
            folders) from ``-a/--assets``.

    Returns:
        Doc: the document (for chaining).

    Raises:
        CliError: when the template cannot be resolved, read or applied.
    """
    params = dict(params or {})
    asset_attachments = _load_assets_paths(assets)

    if template and _is_docx_template(template):
        # binary docx template files are handled at export time (docx only)
        if params:
            _info('warning: parameters are ignored for .docx templates')
        _merge_attachments_into_meta(doc, asset_attachments)
        return doc

    # parameter values that point at existing files become attachments; the
    # directory of the template (raw file or registered id) is searched first
    template_dir = None
    if template:
        if os.path.isfile(template):
            template_dir = os.path.dirname(os.path.abspath(str(template)))
        else:
            try:
                template_dir = os.path.dirname(_find_template_file(template))
            except CliError:
                pass  # unknown template id; reported below by set_template_to_meta
    param_attachments = _load_param_file_values(params, template_dir)

    if not template:
        if params:
            meta = dict(doc.get_meta({}).get('data', {}))
            meta.update(params)
            doc.update_meta(meta)
        _merge_attachments_into_meta(doc, {**param_attachments,
                                           **asset_attachments})
        return doc

    scanned_attachments = {}
    if os.path.isfile(template):
        # raw template file: scan the source for sibling file references and
        # load the found files as attachments
        source = _read_text_file(template)
        tformat = _template_file_tformat(template, source)
        scanned_attachments, _unresolved = _find_template_file_references(
            source, tformat, template_dir)
        # parameters given under their macro name are baked into the source
        # so they win over the template's own \providecommand defaults
        source, params = _bake_macro_named_params(source, tformat, params)
        template = _register_raw_template_file(template, source=source)

    # a template id from the registered template directories
    try:
        doc.set_template_to_meta(template, on_exist='overwrite',
                                  template_params=params if params else None)
    except FileNotFoundError:
        available = ', '.join(sorted(get_available_template_ids())) or '(none)'
        raise CliError(
            f'template {template!r} is neither an existing file nor a known template '
            f'id. available template ids: {available}')
    except Exception as err:
        raise CliError(f'could not apply template {template!r}: {err}')

    # merge the collected attachments into the metadata (later wins:
    # scanned refs -> param-loaded files -> --assets)
    _merge_attachments_into_meta(doc, {**scanned_attachments,
                                      **param_attachments,
                                      **asset_attachments})
    return doc


def _params_from_block_template(source, tformat=None):
    """Parse a blocktemplate source and return its parameters as a dict.

    Args:
        source (str): the template file content.
        tformat (str | None): explicit format ('html', 'tex' or 'typ') or
            None to auto-detect from the content.

    Returns:
        tuple[dict, list]: the parameter mapping (name -> value) and the
        list of parse warnings (empty when the template is well formed).

    Raises:
        CliError: when the template cannot be parsed at all.
    """
    try:
        bdoc = blocktmpl.parse(source, tformat=tformat, strict=False)
    except Exception as err:
        raise CliError(f'could not parse the block template: {err}')
    params = {}
    if bdoc.params_section is not None:
        params = {n: p.value for n, p in bdoc.params_section.params.items()}
    return params, list(bdoc.warnings)


def _params_from_jinja_template(source, path):
    """Extract the parameters of a jinja2 template source.

    The parameter names are the undeclared variables of the template (the
    reserved name ``body`` is excluded). Values are ``None`` unless a sibling
    ``<name>.params.json`` file (the convention used by the template
    directories) provides defaults, in which case its contents are used.

    Args:
        source (str): the template file content.
        path (str): the template file path (used to find the sibling
            ``.params.json`` file).

    Returns:
        dict: the parameter mapping (name -> value or None).

    Raises:
        CliError: when the source is not valid jinja2 syntax.
    """
    from jinja2 import Environment, meta
    try:
        ast = Environment().parse(source)
    except Exception as err:
        raise CliError(f'could not parse the template {path!r}: {err}')
    names = sorted(meta.find_undeclared_variables(ast) - {'body'})
    params = {n: None for n in names}

    stem = os.path.basename(str(path)).split('.')[0]
    sibling = os.path.join(os.path.dirname(str(path)) or '.', stem + '.params.json')
    if os.path.isfile(sibling):
        try:
            with open(sibling, 'r', encoding='utf-8-sig') as f:
                params.update(json.load(f))
        except Exception as err:
            raise CliError(f'could not read template parameters from {sibling!r}: {err}')
    return params


# --------------------------------------------------------------------------- #
# command implementations
# --------------------------------------------------------------------------- #

def cmd_example(args):
    """``example`` command: write the built-in example document.

    Creates the document from ``Doc.get_example()``, optionally applies a
    template and template parameters (``-t``/``-p`` plus unknown ``--name
    value`` arguments, see ``_apply_template_and_params``) and writes it in
    the requested format either to the file given with ``-o/--out`` or to
    stdout. When no format is given it is inferred from the output file
    extension (falling back to ``html``).

    Args:
        args (argparse.Namespace): parsed arguments with the attributes
            ``format`` (str | None), ``out`` (str | None), ``template``
            (str | None), ``parameters`` (str | None) and ``assets``
            (list[str] | None).

    Returns:
        int: exit code (0 on success).
    """
    fmt = _norm_format(args.format)
    if fmt is None and args.out:
        fmt = _format_from_path(args.out)
    if fmt is None:
        fmt = 'html'

    doc = Doc.get_example()
    _apply_template_and_params(doc, args.template, _merged_params(args),
                               assets=getattr(args, 'assets', None))
    if args.out:
        out = str(args.out)
        if not os.path.splitext(out)[1]:
            out += FORMAT_EXTENSIONS[fmt]
        _export_doc_to_file(doc, out, fmt, template_arg=args.template,
                            verb=_verbosity(args))
        _info(f'wrote example document ({fmt}) to {out}')
    else:
        _export_doc_to_stdout(doc, fmt, template_arg=args.template,
                              verb=_verbosity(args))
    return 0


def cmd_show(args):
    """``show`` command: display a document on the terminal via ``Doc.show()``.

    The document is either loaded from the given input file (any format
    accepted by ``build``) or, when no input file is given, the built-in
    example document is used. A template and template parameters
    (``-t``/``-p`` plus unknown ``--name value`` arguments) are applied to
    the document before showing it (they only take effect for the rendering
    engines html, tex/latex, typst and pdf). As a convenience, when only one
    argument is given and it is an existing file, it is treated as the input
    file and the show engine defaults to ``auto``.

    Args:
        args (argparse.Namespace): parsed arguments with the attributes
            ``format`` (str | None), ``input`` (str | None), ``template``
            (str | None), ``parameters`` (str | None) and ``assets``
            (list[str] | None).

    Returns:
        int: exit code (0 on success).
    """
    engine = str(args.format or 'auto').strip().lower()
    input_path = args.input

    # convenience: "pydocmaker show mydoc.json" (first argument is the file)
    if input_path is None and engine not in SHOW_ENGINE_ALIASES and os.path.exists(args.format):
        input_path, engine = args.format, 'auto'

    if engine not in SHOW_ENGINE_ALIASES:
        supported = ', '.join(sorted(SHOW_ENGINE_ALIASES))
        raise CliError(f'unknown show format {args.format!r}. supported: {supported}')
    engine = SHOW_ENGINE_ALIASES[engine]

    if input_path:
        doc = _load_input_doc(input_path)
        _info(f'showing {input_path} ({len(doc)} parts) with engine {engine!r}')
    else:
        doc = Doc.get_example()
        _info('no input file given, showing the built-in example document '
              f'with engine {engine!r}')

    _apply_template_and_params(doc, args.template, _merged_params(args),
                               assets=getattr(args, 'assets', None))
    if args.template and engine not in ('html', 'pdf', 'tex', 'typst'):
        _info(f'warning: the template {args.template!r} has no effect for the '
              f'{engine!r} show engine')

    try:
        doc.show(engine=engine)
    except KeyError as err:
        # NOTE: Doc.show(engine='md') pops 'embed_images' from its kwargs in
        # terminal mode which raises a KeyError when nothing was passed; fall
        # back to the equivalent direct markdown export
        if engine == 'md' and 'embed_images' in str(err):
            print(doc.to_markdown(embed_images=False))
        else:
            raise
    return 0


def _build_input(args, path, fmt, i=1, n=1):
    """Build one input document into the target format.

    Implements the per-file build of ``cmd_build`` (which may pass several
    paths when the input argument was a glob pattern). A typst file is
    compiled directly (to pdf only) and rejects a template and template
    parameters with an error; any other input is loaded as a ``Doc``,
    optionally templated (``-t``/``-p`` plus unknown ``--name value``
    arguments, see ``_apply_template_and_params``) and exported. The output
    file name defaults to the input file name with the extension exchanged
    (``report.md`` -> ``report.pdf``).

    Because pdf compiles run in isolated temp directories, file references
    are resolved against the directory of the input file: direct typst
    builds pass it as compile ``root`` and direct tex builds have their
    references scanned and attached (as given, next to the input file, then
    in the working directory; unresolved filename-like references only warn).

    Args:
        args (argparse.Namespace): parsed arguments with the attributes
            ``out`` (str | None), ``template`` (str | None), ``nocode``
            (bool), ``verbosity`` (int), ``parameters`` (str | None) and
            ``assets`` (list[str] | None).
        path (str): the input document path.
        fmt (str): the canonical output format (see ``FORMAT_ALIASES``).
        i (int), current document index number
        n (int), total number of documents
    Raises:
        CliError: on invalid input/output combinations or build failures.
    """
    verb = _verbosity(args)

    # a .typ/.typst file is compiled directly by the typst engine (pdf only)
    if os.path.splitext(str(path))[1].lower() in ('.typ', '.typst'):
        # the direct compile uses neither a template nor template parameters;
        # reject the given options instead of silently ignoring them
        if getattr(args, 'template', None):
            raise CliError(
                f'typst file {path!r} is compiled directly and does not accept a '
                f'template, but -t/--template was given ({args.template!r}); remove '
                f'it or build a pydocmaker document format instead')
        params = _merged_params(args)
        if params:
            given = ', '.join('--' + k for k in sorted(params))
            raise CliError(
                f'typst file {path!r} is compiled directly and does not accept '
                f'template parameters, but parameters were given: {given}; remove '
                f'them or build a pydocmaker document format instead')
        if fmt != 'pdf':
            raise CliError(
                f'typst file {path!r} can only be built to pdf; use -f/--format '
                f'pdf or convert the document to another format first')
        try:
            typ_code = _read_text_file(path)
            if args.out:
                out = str(args.out)
                if not os.path.splitext(out)[1]:
                    out += FORMAT_EXTENSIONS['pdf']
            else:
                out = os.path.splitext(str(path))[0] + '.pdf'
            if os.path.abspath(out) == os.path.abspath(str(path)):
                raise CliError(
                    f'the output file {out!r} would overwrite the input file {path!r}; '
                    f'choose a different output with -o/--out')
            from pydocmaker.backend.ex_typst import compile_with_typst
            # resolve file references (#image("..."), ...) next to the input
            # file first (the compile itself runs in a temp directory)
            src_dir = os.path.dirname(os.path.abspath(path))
            compile_with_typst(typ_code, output=out, verb=verb, root=src_dir)
            _info(f'built {i}/{n} {path} -> {out} ({fmt})')
            return
        except CliError:
            raise
        except Exception as err:
            raise CliError(f'could not compile typst file {path!r}: {err}')

    nocode = getattr(args, 'nocode', False)
    doc = _load_input_doc(path, nocode=nocode)

    _apply_template_and_params(doc, args.template, _merged_params(args),
                               assets=getattr(args, 'assets', None))

    if args.out:
        out = str(args.out)
        if not os.path.splitext(out)[1]:
            out += FORMAT_EXTENSIONS[fmt]
    else:
        out = os.path.splitext(str(path))[0] + FORMAT_EXTENSIONS[fmt]

    if os.path.abspath(out) == os.path.abspath(str(path)):
        raise CliError(
            f'the output file {out!r} would overwrite the input file {path!r}; '
            f'choose a different output with -o/--out or another format with -f/--format')

    # a direct .tex/.latex input compiled to pdf runs in a temp directory;
    # scan its file references and attach them so they are found there.
    # Without a user template the latex engine is forced and an empty
    # template is used: a plain latex document is a complete standalone
    # source (own \documentclass, preamble and \begin{document}) and must
    # not be wrapped in the default pydocmaker preamble nor silently fall
    # back to the configured default engine (which may e.g. be typst)
    files_to_upload = None
    pdf_engine = None
    pdf_template = None
    if fmt == 'pdf' and os.path.splitext(str(path))[1].lower() in ('.tex', '.latex'):
        source = _read_text_file(path)
        files_to_upload, _unresolved = _find_template_file_references(
            source, 'tex', base_dir=os.path.dirname(os.path.abspath(path)))
        if not args.template:
            pdf_engine = 'tex'
            pdf_template = ''

    _export_doc_to_file(doc, out, fmt, template_arg=args.template,
                        files_to_upload=files_to_upload, verb=verb,
                        pdf_engine=pdf_engine, pdf_template=pdf_template)
    _info(f'built {i}/{n} {path} -> {out} ({fmt})')


def cmd_build(args):
    """``build`` / ``convert`` command: convert documents into another format.

    Each input document is built individually into its own output file (as if
    the command was run once per file); inputs are never merged. An input may
    be a glob pattern (``abc*.tex``); every file matched by the pattern is
    then built individually. Unquoted patterns which the shell has already
    expanded into several arguments are handled identically. ``-o/--out``
    cannot be used when several files are built.

    Args:
        args (argparse.Namespace): parsed arguments with the attributes
            ``inputs`` (list[str]), ``format`` (str | None), ``out``
            (str | None), ``template`` (str | None), ``verbosity`` (int),
            ``parameters`` (str | None) and ``assets`` (list[str] | None).

    Returns:
        int: exit code (0 on success).
    """
    fmt = _norm_format(args.format)
    if fmt is None and args.out:
        fmt = _format_from_path(args.out)
    if fmt is None:
        fmt = 'pdf'

    inputs = []
    for arg in args.inputs:
        inputs += _expand_input_pattern(arg)
    if len(inputs) > 1 and args.out:
        raise CliError(
            f'{len(inputs)} files are built; -o/--out cannot be used with '
            f'multiple inputs (each file is built to its own output next to '
            f'the input file)')
    for i, path in enumerate(inputs, 1):
        _build_input(args, path, fmt, i, len(inputs))
    return 0


def cmd_check(args):
    """``check`` command: validate the syntax of a document or template.

    Depending on the input file, one of three checks runs:

    * json pydocmaker file -- loaded via ``Doc.load``; states whether the
      syntax is OK.
    * html pydocmaker file (``html_loader.py``) -- the embedded payload is
      deserialized; states whether the syntax is OK.
    * blocktemplate file (``.html`` without a pydocmaker payload, ``.tex`` or
      ``.typ``) -- the comment-delimited ``pydocmaker:`` blocks are analyzed
      with the block templating engine, correctness problems are reported and
      the found parameters are printed as JSON.

    Args:
        args (argparse.Namespace): parsed arguments with the attribute
            ``input`` (str).

    Returns:
        int: exit code (0 = syntax OK, 1 = syntax NOT OK).
    """
    path = str(args.input)
    if not os.path.isfile(path):
        raise CliError(f'input file not found: {path}')
    ext = os.path.splitext(path)[1].lower()
    text = _read_text_file(path)

    # --- 1. json pydocmaker document ---------------------------------- #
    if ext == '.json':
        print(f'file      : {path}')
        print('kind      : json pydocmaker document')
        try:
            doc = Doc.load(path)
        except Exception as err:
            print('syntax    : NOT OK')
            print(f'problem   : {err}')
            return 1
        print(f'syntax    : OK ({len(doc)} parts)')
        return 0

    # --- 2. html pydocmaker document ---------------------------------- #
    if ext in ('.html', '.htm', '.pyd', '.pydoc'):
        from pydocmaker.io.html_loader import io_check_html, io_deserialize_html
        if io_check_html(text) or ext in ('.pyd', '.pydoc'):
            print(f'file      : {path}')
            print('kind      : html pydocmaker document')
            try:
                doc = io_deserialize_html(text)
            except Exception as err:
                print('syntax    : NOT OK')
                print(f'problem   : {err}')
                return 1
            print(f'syntax    : OK ({len(doc)} parts)')
            return 0
        # a plain .html file falls through to the blocktemplate check below

    # --- 3. blocktemplate file ----------------------------------------- #
    if ext in ('.html', '.htm', '.tex', '.latex', '.typ'):
        tformat = 'html' if ext in ('.html', '.htm') else ('tex' if ext in ('.tex', '.latex') else 'typ')
        print(f'file      : {path}')
        print(f'kind      : block template ({tformat})')
        try:
            bdoc = blocktmpl.parse(text, tformat=tformat, strict=False)
        except Exception as err:
            print('syntax    : NOT OK')
            print(f'problem   : {err}')
            return 1
        print(f'markers   : {"yes" if bdoc.had_markers else "no"}')
        if not bdoc.had_markers:
            print('note      : no pydocmaker:parameters/body markers found, nothing to check')
        if bdoc.warnings:
            print('syntax    : NOT OK')
            for w in bdoc.warnings:
                print(f'problem   : {w}')
        else:
            print('syntax    : OK')
        params = {}
        if bdoc.params_section is not None:
            params = {n: p.value for n, p in bdoc.params_section.params.items()}
        print('parameters: ' + json.dumps(params, ensure_ascii=False, default=str))
        return 1 if bdoc.warnings else 0

    raise CliError(
        f'cannot check {path!r}: expected a json pydocmaker file, an html pydocmaker '
        f'file or a blocktemplate file (.html, .tex or .typ)')


def cmd_extract(args):
    """``extract`` command: print the parameters of a template as JSON.

    Blocktemplates (with ``pydocmaker:`` markers) yield the values declared in
    their parameters block; jinja2 templates yield their undeclared variables
    (value ``null``, unless a sibling ``<name>.params.json`` file provides
    defaults). The parameter mapping is printed as JSON to stdout.

    Args:
        args (argparse.Namespace): parsed arguments with the attribute
            ``input`` (str).

    Returns:
        int: exit code (0 on success).
    """
    path = str(args.input)
    if not os.path.isfile(path):
        raise CliError(f'input file not found: {path}')
    text = _read_text_file(path)
    ext = os.path.splitext(path)[1].lower()
    tformat = {'html': 'html', 'htm': 'html', 'tex': 'tex', 'latex': 'tex', 'typ': 'typ'}.get(ext)

    if blocktmpl.detect(text):
        params, warnings = _params_from_block_template(text, tformat=tformat)
        for w in warnings:
            _info(f'warning: {w}')
    else:
        params = _params_from_jinja_template(text, path)

    print(json.dumps(params, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_template(args):
    """``template`` command: copy a document template to a file or stdout.

    The template is looked up in the registered template directories (the
    package templates plus user registered ones). The input string can be a
    bare format name (``html``, ``tex``, ``typ`` -> defaults back to
    ``base.XXX``), a bare template id (``base``, ``report``) or a template
    file name (``base.html``, ``report.typ.j2``).

    Args:
        args (argparse.Namespace): parsed arguments with the attributes
            ``template`` (str) and ``out`` (str | None).

    Returns:
        int: exit code (0 on success).
    """
    src = _find_template_file(args.template)
    try:
        with open(src, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except OSError as err:  # pragma: no cover - raced/unreadable file
        raise CliError(f'cannot read template file {src!r}: {err}')

    if args.out:
        out = str(args.out)
        if not os.path.splitext(out)[1]:
            # default the output extension to the template's extension
            out += os.path.splitext(src)[1]
        try:
            with open(out, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError as err:
            raise CliError(f'cannot write output file {out!r}: {err}')
        _info(f'wrote template {os.path.basename(src)} to {out}')
    else:
        sys.stdout.write(content)
    return 0


def cmd_templates(args):
    """``templates`` command: list the registered templates and their paths.

    Walks the registered template directories (the package templates plus
    user registered ones, see ``register_new_template_dir``) and prints every
    template file (html, tex, typ and the jinja2 ``.j2`` family) with its
    full path, grouped by directory, to stdout.

    Args:
        args (argparse.Namespace): parsed arguments (unused).

    Returns:
        int: exit code (0 on success).
    """
    seen = set()
    for d in get_registered_template_dirs(include_default=True):
        d = str(d)
        key = os.path.normpath(os.path.abspath(d))
        if key in seen:
            continue
        seen.add(key)
        if not os.path.isdir(d):
            _info(f'warning: template directory {d!r} does not exist')
            continue
        files = sorted(fn for fn in os.listdir(d)
                       if fn.lower().endswith(TEMPLATE_FILE_EXTS))
        if not files:
            continue
        print(d)
        for fn in files:
            print(f'    {os.path.join(d, fn)}')
    return 0


# --------------------------------------------------------------------------- #
# argument parser
# --------------------------------------------------------------------------- #

def build_parser():
    """Build the argparse parser for the ``pydocmaker`` command line gateway.

    Returns:
        argparse.ArgumentParser: the fully configured parser with all
        subcommands (example, show, build, convert, check, extract,
        template, templates).
    """
    parser = argparse.ArgumentParser(
        prog='pydocmaker',
        description='pydocmaker command line gateway: create, convert, validate and '
                   'template pydocmaker documents from the shell.',
        epilog="""\
examples:
  pydocmaker example md                        example document as markdown on stdout
  pydocmaker example pdf -o example.pdf        example document as pdf file
  pydocmaker show rich                         show the example document in the terminal
  pydocmaker show html my_document.json        show an input file as html
  pydocmaker build README.md                   convert markdown to README.pdf
  pydocmaker build my_report.tex               convert latex to my_report.pdf
  pydocmaker convert notes.md -f html          convert markdown to notes.html
  pydocmaker check my_document.json            validate a json pydocmaker file
  pydocmaker check base.typ                    validate a block template file
  pydocmaker extract base.html                 print template parameters as json
  pydocmaker template html -o my.html          copy the base html template
  pydocmaker template tex                      print the base latex template
  pydocmaker templates                         list registered templates and paths

templating (example, show and build/convert accept -t/-p plus unknown
"--name value" arguments as template parameters):
  pydocmaker example pdf -t base --pAuthor "me"
  pydocmaker build README.md -t base.tex --pTitle "Readme"
  pydocmaker build doc.md -p params.json
  pydocmaker build README.md -t report.tex -a ./assets

run "pydocmaker <command> --help" for the full argument reference of a command.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {__version__}')
    # shared template options (also accepted before the subcommand; the
    # subparsers below re-define them with default=SUPPRESS so a value given
    # here survives when the subcommand does not override it)
    parser.add_argument('-t', '--template', default=None, metavar='TEMPLATE',
                        help='document template: a template file path or a template id '
                             'like "base" or "base.tex" (only example, show and '
                             'build/convert)')
    parser.add_argument('-p', '--parameters', default=None, metavar='PARAMS',
                        help='template parameters as a JSON object string or a JSON file '
                             '(additional parameters can be given as unknown '
                             '"--name value" arguments)')
    parser.add_argument('-a', '--assets', action='append', default=None,
                        metavar='PATH',
                        help='additional attachment for the document build: a file '
                             '(attached under its name) or a folder (attached '
                             'recursively); repeatable (only example, show and '
                             'build/convert)')
    parser.add_argument('-v', '--verbosity', default=1, type=int, metavar='N',
                        help='verbosity level for document builds and exports: '
                             '0 = quiet, 1 = normal status messages, 2 = more '
                             'details, 3+ = full backend output (default: 1; '
                             'only example and build/convert)')

    sub = parser.add_subparsers(dest='command', metavar='COMMAND', required=True)

    # ---- example ------------------------------------------------------ #
    p = sub.add_parser(
        'example',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='write the built-in example document to a file or stdout',
        description='Write the built-in example document (Doc.get_example()) in a '
                    'given format either to the file given with -o/--out or to stdout '
                    '(when -o is omitted or empty).',
        epilog="""\
examples:
  pydocmaker example md                        markdown to stdout
  pydocmaker example pdf -o out.pdf             pdf to the file out.pdf
  pydocmaker example -o out.html               format inferred from the extension (html)
  pydocmaker example pdf -t base --pAuthor "me"
  pydocmaker example typst -t base --pTitle "My Report" --pAuthor me
  pydocmaker example pdf -t my.tmpl.tex -a logo.png
""")
    p.add_argument('format', nargs='?', default=None, metavar='FORMAT',
                   help='output format: pdf, md/markdown, html, typ/typst, tex/latex, '
                        'json, docx, ipynb, textile or pydoc/pyd (default: inferred from '
                        'the -o file extension, or html)')
    p.add_argument('-o', '--out', default=None, metavar='OUT',
                   help='output file path; if omitted or empty the document is printed '
                        'to stdout (default: stdout)')
    p.add_argument('-t', '--template', default=argparse.SUPPRESS, metavar='TEMPLATE',
                   help='document template: a template file path or a template id like '
                        '"base" or "base.tex"')
    p.add_argument('-p', '--parameters', default=argparse.SUPPRESS, metavar='PARAMS',
                   help='template parameters as a JSON object string or a JSON file; '
                        'additional parameters can be given as unknown "--name value" '
                        'arguments')
    p.add_argument('-a', '--assets', action='append', default=argparse.SUPPRESS,
                   metavar='PATH',
                   help='additional attachment for the document build: a file '
                        '(attached under its name) or a folder (attached '
                        'recursively); repeatable')
    p.add_argument('-v', '--verbosity', default=argparse.SUPPRESS, type=int,
                   metavar='N',
                   help='verbosity level for the export: 0 = quiet, 1 = normal '
                        'status messages, 2 = more details, 3+ = full backend '
                        'output (default: 1)')
    p.set_defaults(func=cmd_example)

    # ---- show --------------------------------------------------------- #
    p = sub.add_parser(
        'show',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='show a document (or the example) on the terminal',
        description='Display a document using Doc.show(). The document is either read '
                    'from the given input file (any format accepted by build) or, when '
                    'no input is given, the built-in example document is used.',
        epilog="""\
examples:
  pydocmaker show rich                    example document, rich terminal output
  pydocmaker show html                     example document as html
  pydocmaker show md my_report.json        show an input file as markdown
  pydocmaker show my_report.md             (single argument = input file, engine auto)
  pydocmaker show html doc.json -t base --pTitle "Doc"
""")
    p.add_argument('format', nargs='?', default=None, metavar='FORMAT',
                   help='show engine: auto (default), html, md/markdown, tex/latex, '
                        'typ/typst, rich, console, terminal or plain')
    p.add_argument('input', nargs='?', default=None, metavar='INPUT',
                   help='input document (json/html/pyd/ipynb pydocmaker file, markdown, '
                        'latex or plain text); if omitted the built-in example '
                        'document is shown')
    p.add_argument('-t', '--template', default=argparse.SUPPRESS, metavar='TEMPLATE',
                   help='document template: a template file path or a template id like '
                        '"base" or "base.tex" (takes effect for the html, tex, typst '
                        'and pdf engines)')
    p.add_argument('-p', '--parameters', default=argparse.SUPPRESS, metavar='PARAMS',
                   help='template parameters as a JSON object string or a JSON file; '
                        'additional parameters can be given as unknown "--name value" '
                        'arguments')
    p.add_argument('-a', '--assets', action='append', default=argparse.SUPPRESS,
                   metavar='PATH',
                   help='additional attachment for the document build: a file '
                        '(attached under its name) or a folder (attached '
                        'recursively); repeatable')
    p.set_defaults(func=cmd_show)

    # ---- build / convert ------------------------------------------------ #
    p = sub.add_parser(
        'build',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        aliases=['convert'],
        help='convert document(s) into another format (default: pdf)',
        description='Read one or more documents and export each of them into a given '
                    'output format (pdf by default); inputs are never merged -- every '
                    'file is built individually into its own output file. The output '
                    'file name defaults to the input file name with the file extension '
                    'exchanged (README.md -> README.pdf). Inputs may be glob patterns '
                    '("abc*.tex"); an unquoted pattern already expanded by the shell is '
                    'handled identically. Readable inputs: json pydocmaker '
                    'files (Doc.save/Doc.load), html pydocmaker files (html_loader.py), '
                    'notebooks (.ipynb), markdown, latex (.tex), typst (.typ), and any '
                    'other non-binary text document (added via add_text). Plain latex '
                    'files are compiled to pdf as standalone documents with the latex '
                    'engine; typst files are compiled directly by the typst engine and '
                    'accept neither a template nor template parameters (both are '
                    'rejected with an error).',
        epilog="""\
examples:
  pydocmaker build README.md              -> README.pdf
  pydocmaker build my_report.tex          -> my_report.pdf
  pydocmaker build my_report.typ          -> my_report.pdf
  pydocmaker build notes.md -f html       -> notes.html
  pydocmaker build "abc*.tex" -t my.tmpl.tex   build every matched file
  pydocmaker build docs/s*.ipynb          also works unquoted (shell expanded)
  pydocmaker build README.md -t base.tex --pTitle "Readme"
  pydocmaker build README.md -t my.tmpl.tex -a ./assets
  pydocmaker build notebook.ipynb --nocode   -> notebook.pdf (no code)
  pydocmaker build report.tex -v 3        build with verbose backend output
""")
    p.add_argument('inputs', nargs='+', metavar='INPUT',
                   help='one or more input documents; may contain glob patterns like '
                        '"abc*.tex" (each matched file is built individually, sorted '
                        'by name); inputs are never merged')
    p.add_argument('-f', '--format', default=None, metavar='FORMAT',
                   help='output format: pdf (default), md/markdown, html, typ/typst, '
                        'tex/latex, json, docx, ipynb, textile or pydoc/pyd')
    p.add_argument('-o', '--out', default=None, metavar='OUT',
                   help='explicit output file path (default: the input file name '
                        'with the extension exchanged)')
    p.add_argument('-t', '--template', default=argparse.SUPPRESS, metavar='TEMPLATE',
                   help='document template: a template file path or a template id like '
                        '"base" or "base.tex"; for a bare id the per-format variant '
                        'matching the output format is used')
    p.add_argument('-p', '--parameters', default=argparse.SUPPRESS, metavar='PARAMS',
                   help='template parameters as a JSON object string or a JSON file; '
                        'additional parameters can be given as unknown "--name value" '
                        'arguments')
    p.add_argument('-a', '--assets', action='append', default=argparse.SUPPRESS,
                   metavar='PATH',
                   help='additional attachment for the document build: a file '
                        '(attached under its name) or a folder (attached '
                        'recursively); repeatable')
    p.add_argument('-v', '--verbosity', default=argparse.SUPPRESS, type=int,
                   metavar='N',
                   help='verbosity level for the build: 0 = quiet, 1 = normal '
                        'status messages, 2 = more details, 3+ = full backend '
                        'output (default: 1; passed through to the pdf, tex and '
                        'typst engines)')
    p.add_argument('--nocode', action='store_true', default=False,
                   help='when loading notebook (.ipynb) files, exclude all code '
                        'cells from the document')
    p.set_defaults(func=cmd_build)

    # ---- check --------------------------------------------------------- #
    p = sub.add_parser(
        'check',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='check the syntax of a document or template file',
        description='Check the syntax of an input file and state whether it is OK. '
                    'Supported inputs: json pydocmaker files, html pydocmaker files '
                    '(html_loader.py) and blocktemplate files (.html without a '
                    'pydocmaker payload, .tex or .typ). For blocktemplates the blocks '
                    'are analyzed, correctness problems are reported and the found '
                    'parameters are printed as JSON.',
        epilog="""\
examples:
  pydocmaker check my_document.json     validate a json pydocmaker file
  pydocmaker check my_document.html     validate an html pydocmaker file
  pydocmaker check base.typ             validate a block template and print parameters

exit codes: 0 = syntax OK, 1 = syntax NOT OK, 2 = usage error.
""")
    p.add_argument('input', metavar='INPUT',
                   help='the file to check (json/pyd/pydoc/html pydocmaker file or '
                        '.html/.tex/.typ blocktemplate file)')
    p.set_defaults(func=cmd_check)

    # ---- extract -------------------------------------------------------- #
    p = sub.add_parser(
        'extract',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='print the parameters of a template file as JSON',
        description='Extract the parameters from a given template file and print them '
                    'as a JSON mapping to stdout. Blocktemplates (pydocmaker: markers) '
                    'yield the values declared in their parameters block; jinja2 '
                    'templates yield their undeclared variables (value null unless a '
                    'sibling <name>.params.json file provides defaults).',
        epilog="""\
examples:
  pydocmaker extract base.typ
  pydocmaker extract my_template.html > params.json
""")
    p.add_argument('input', metavar='INPUT',
                   help='the template file to extract parameters from (.html, .tex, '
                        '.typ or any jinja2 template)')
    p.set_defaults(func=cmd_extract)

    # ---- template -------------------------------------------------------- #
    p = sub.add_parser(
        'template',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='copy a document template to a file or stdout',
        description='Copy one of the registered pydocmaker document templates either '
                    'to the file given with -o/--out or to stdout (when -o is omitted '
                    'or empty). The template input can be a bare format ("html", "tex" '
                    'or "typ"; defaults back to the base template base.XXX), a bare '
                    'template id ("base", "report") or a template file name '
                    '("base.html", "report.typ.j2").',
        epilog="""\
examples:
  pydocmaker template html                 print the base html template (base.html)
  pydocmaker template tex -o my.tex        write the base latex template to my.tex
  pydocmaker template base.typ             print the base typst template
  pydocmaker template report.typ.j2       print a specific registered template
""")
    p.add_argument('template', nargs='?', default='html', metavar='TEMPLATE',
                   help='the template to copy: a format name ("html", "tex", "typ" -> '
                        'base.XXX), a template id ("base", "report") or a template '
                        'file name ("base.html"); default: html')
    p.add_argument('-o', '--out', default=None, metavar='OUT',
                   help='output file path; if omitted or empty the template is printed '
                        'to stdout (default: stdout)')
    p.set_defaults(func=cmd_template)

    # ---- templates -------------------------------------------------------- #
    p = sub.add_parser(
        'templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='list the registered templates and their paths',
        description='List every template file (html, tex, typ and the jinja2 ".j2" '
                    'family) found in the registered template directories (the '
                    'package templates plus user registered ones) with its full '
                    'path, grouped by directory, on stdout.',
        epilog="""\
examples:
  pydocmaker templates                  list all registered template files
  pydocmaker templates | grep base      filter the listing
""")
    p.set_defaults(func=cmd_templates)

    return parser


def main(argv=None):
    """Entry point of the ``pydocmaker`` command line gateway.

    Unknown long options (``--name value``) are extracted as template
    parameters *before* argparse runs (see ``_extract_template_params``), so
    they never surface as argument errors for the templating commands.

    Args:
        argv (list[str] | None): the command line arguments to parse; when
            None the arguments of ``sys.argv`` are used.

    Returns:
        int: the process exit code (0 = success, 1 = a check failed,
        2 = usage or runtime error).
    """
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    clean, params = _extract_template_params(argv, _collect_option_specs(parser))
    args = parser.parse_args(clean)
    if params:
        args.cli_params = params
    s = f'pydocmaker v:{__version__} -> {argv[0]}'

    if len(argv) > 1:
        s += f" {argv[1]}"
    _info(s)

    try:
        # template options are only meaningful for the templating commands
        # (example, show, build/convert); the top level parser accepts them
        # before any subcommand, so they must be rejected here for the other
        # commands instead of being silently ignored. NOTE: the "template"
        # command has a positional argument named "template" (its input), so
        # the -t/--template option cannot be checked for it (a -t given
        # before that subcommand is already overwritten by the positional)
        if getattr(args, 'command', None) in ('check', 'extract', 'template', 'templates'):
            attrs = [('parameters', '-p/--parameters'), ('assets', '-a/--assets')]
            if args.command != 'template':
                attrs.insert(0, ('template', '-t/--template'))
            given = [flag for attr, flag in attrs if getattr(args, attr, None)]
            if given:
                raise CliError(f'the {args.command!r} command does not accept '
                               f'template options ({", ".join(given)})')
        return args.func(args)
    except CliError as err:
        print(f'error: {err}', file=sys.stderr)
        return 2
    except blocktmpl.BlockTemplatingError as err:
        print(f'error: {err}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
