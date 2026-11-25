CLI Reference
=============

The ``pydocmaker`` command-line interface turns common document workflows into small shell
commands, letting you create, convert, validate, and template documents without writing any
Python code.

It is registered as the ``pydocmaker`` console script and can equivalently be run as a module::

    pydocmaker <command> [arguments]
    python -m pydocmaker.cli <command> [arguments]

Use ``pydocmaker <command> --help`` to see the full argument reference of a single command.
All commands write the produced *document data* to **stdout** (or the file given with ``-o``)
while progress/status messages go to **stderr**, so stdout stays clean for piping and redirection.


Commands Overview
-----------------

+---------------------+---------------------------------------------------------------+
| Command             | Description                                                   |
+---------------------+---------------------------------------------------------------+
| ``example``         | Write the built-in example document in a given format         |
+---------------------+---------------------------------------------------------------+
| ``show``            | Display a document on the terminal                            |
+---------------------+---------------------------------------------------------------+
| ``build`` / ``convert`` | Convert document(s) into another format (default: PDF)    |
+---------------------+---------------------------------------------------------------+
| ``check``           | Validate the syntax of a document or template file            |
+---------------------+---------------------------------------------------------------+
| ``extract``         | Print a template's parameters as JSON                         |
+---------------------+---------------------------------------------------------------+
| ``template``        | Copy a registered document template to a file or stdout       |
+---------------------+---------------------------------------------------------------+


Output Formats
--------------

All commands that produce documents accept the following output format names (case-insensitive)::

    pdf  ·  md / markdown  ·  html  ·  typ / typst  ·  tex / latex
    json  ·  docx / word  ·  ipynb  ·  textile  ·  pydoc / pyd

The ``pdf`` and ``docx`` formats are binary; they require an output file (give ``-o`` or pipe
stdout into a file). When the ``-f/--format`` flag is omitted the format is inferred from the
``-o`` file extension; for ``build``/``convert`` the default is ``pdf``.


Exit Codes
----------

+------+--------------------------------------------------------------+
| Code | Meaning                                                      |
+======+==============================================================+
| ``0``| Success                                                      |
+------+--------------------------------------------------------------+
| ``1``| A check failed (e.g. invalid syntax)                         |
+------+--------------------------------------------------------------+
| ``2``| A usage or runtime error (bad arguments, unreadable input …) |
+------+--------------------------------------------------------------+


Command Details
---------------

example
~~~~~~~

Write the built-in example document (``Doc.get_example()``) in a given format to a file or stdout.

Usage::

    pydocmaker example [FORMAT] [-o OUTPUT] [-t TEMPLATE] [-p PARAMS] [-a PATH]

**Arguments:**

- ``FORMAT`` (optional) — output format (default: inferred from ``-o`` extension, or ``html``).
- ``-o, --out PATH`` — output file path. Omit or leave empty to print to stdout.
- ``-t, --template ID`` — template file path or template id (e.g. ``base``, ``base.tex``).
- ``-p, --parameters SPEC`` — template parameters as a JSON string or path to a JSON file.
- ``-a, --assets PATH`` — additional attachment (file or folder). Repeatable.

**Examples:**

.. code-block:: bash

    # markdown to stdout
    pydocmaker example md

    # PDF to a file
    pydocmaker example pdf -o example.pdf

    # format inferred from the file extension
    pydocmaker example -o out.html

    # with a template and parameter overrides
    pydocmaker example pdf -t base --pAuthor "me" --pTitle "My Report"

    # pass a JSON file of parameters
    pydocmaker example typst -t base -p params.json


show
~~~~

Display a document (or the built-in example) on the terminal using ``Doc.show()``.

Usage::

    pydocmaker show [ENGINE] [INPUT] [-o OUTPUT] [-t TEMPLATE] [-p PARAMS] [-a PATH]

**Arguments:**

- ``ENGINE`` (optional) — show engine: ``auto`` (default), ``html``, ``md/markdown``,
  ``tex/latex``, ``typ/typst``, ``rich``, ``console``, ``terminal``, or ``plain``.
- ``INPUT`` (optional) — input document path. If omitted the built-in example is shown.
- ``-o, --out PATH`` — output file path. Omit to display in the terminal.
- ``-t, --template ID`` — template file path or template id (applies to html, tex, typst, pdf engines).
- ``-p, --parameters SPEC`` — template parameters as a JSON string or file path.
- ``-a, --assets PATH`` — additional attachment. Repeatable.

**Examples:**

.. code-block:: bash

    # example document, rich terminal output
    pydocmaker show rich

    # example document as HTML in the browser
    pydocmaker show html

    # show a saved document as markdown
    pydocmaker show md my_report.json

    # show without specifying engine (auto-detect)
    pydocmaker show my_report.md

    # render with a template
    pydocmaker show html doc.json -t base --pTitle "Doc"


build / convert
~~~~~~~~~~~~~~~

Read one or more documents and export each of them into a given output format
(PDF by default); inputs are never merged — every file is built individually.
The output file name defaults to the input file name with the extension exchanged
(e.g. ``README.md`` → ``README.pdf``). Use ``-o`` for an explicit output path.
An input may be a glob pattern (``abc*.tex``); every matched file is built
individually and ``-o`` cannot be combined with multiple inputs.

Readable input formats:

- **JSON pydocmaker files** — ``Doc.save`` / ``Doc.load`` output (``.json``, ``.pyd``, ``.pydoc``)
- **HTML pydocmaker files** — ``html_loader.py`` output (``.html`` without payload markers)
- **Notebooks** — ``.ipynb``
- **Markdown** — ``.md``
- **LaTeX** — ``.tex`` (compiled to PDF as a complete standalone document with the
  latex engine; with ``-t`` the input is wrapped in the given template instead)
- **Typst** — ``.typ`` (compiled to PDF directly with the typst engine; accepts
  neither a template nor template parameters — both are rejected with an error)
- **Any non-binary text** — treated as plain text

Usage::

    pydocmaker build INPUT [INPUT ...] [-f FORMAT] [-o OUT] [-t TEMPLATE] [-p PARAMS] [-a PATH] [-v N]

**Arguments:**

- ``INPUT`` — one or more input documents.
- ``-f, --format FORMAT`` — output format (default: ``pdf``).
- ``-o, --out PATH`` — explicit output file path.
- ``-t, --template ID`` — template file path or template id.
- ``-p, --parameters SPEC`` — template parameters as a JSON string or file path.
- ``-a, --assets PATH`` — additional attachment. Repeatable.
- ``-v, --verbosity N`` — verbosity level passed through to the pdf, tex and typst
  engines: 0 = quiet, 1 = normal status messages, 2 = more details, 3+ = full backend
  output (default: 1).
- ``--nocode`` — when loading notebooks (``.ipynb``), exclude all code cells from
  the document.

**Examples:**

.. code-block:: bash

    # markdown -> PDF (output: README.pdf)
    pydocmaker build README.md

    # standalone latex -> PDF (output: my_report.pdf)
    pydocmaker build my_report.tex

    # typst -> PDF (output: my_report.pdf)
    pydocmaker build my_report.typ

    # notebook -> PDF without the code cells
    pydocmaker build notebook.ipynb --nocode

    # markdown -> HTML (output: notes.html)
    pydocmaker build notes.md -f html

    # merge json + markdown -> docx
    pydocmaker build a.json b.md -o out.docx

    # markdown -> PDF with a custom template
    pydocmaker build README.md -t base.tex --pTitle "Readme"

    # with attachment assets
    pydocmaker build README.md -t report.tex -a ./assets

    # convert is a synonym for build
    pydocmaker convert a.json -f html -o out.html


check
~~~~~

Check the syntax of a file and report whether it is valid.

Supported inputs:

- **JSON pydocmaker files** (``.json``, ``.pyd``, ``.pydoc``)
- **HTML pydocmaker files** (``.html`` without payload markers)
- **Blocktemplate files** (``.html``, ``.tex``, ``.typ``)

For blocktemplates the ``pydocmaker:`` markers are analyzed, correctness problems are reported,
and the found parameters are printed as JSON.

Usage::

    pydocmaker check INPUT

**Examples:**

.. code-block:: bash

    # validate a json pydocmaker file
    pydocmaker check my_document.json

    # validate an html pydocmaker file
    pydocmaker check my_document.html

    # validate a block template and print its parameters as JSON
    pydocmaker check base.typ


extract
~~~~~~~

Extract the parameters declared in a template file and print them as a JSON mapping to stdout.

- **Blocktemplates** (``pydocmaker:`` markers) — yield the values declared in the parameters block.
- **Jinja2 templates** — yield their undeclared variables (value ``null``).

Usage::

    pydocmaker extract INPUT

**Examples:**

.. code-block:: bash

    # print block template parameters as JSON
    pydocmaker extract base.typ

    # save parameters to a file
    pydocmaker extract my_template.html > params.json


template
~~~~~~~~

Copy one of the registered pydocmaker document templates to a file or stdout.

The ``TEMPLATE`` argument can be:

- A bare format name — ``html``, ``tex``, or ``typ`` — in which case the base template
  ``base.XXX`` is used.
- A bare template id — ``base``, ``paper``, or ``report``.
- A full template file name — ``base.html``, ``report.typ.j2``, etc.

Usage::

    pydocmaker template [TEMPLATE] [-o OUTPUT]

**Examples:**

.. code-block:: bash

    # print the base HTML template to stdout
    pydocmaker template html

    # write the base LaTeX template to a file
    pydocmaker template tex -o my.tex

    # print the base Typst template
    pydocmaker template base.typ

    # print a specific registered template
    pydocmaker template report.typ.j2


Templating
----------

The ``example``, ``show``, and ``build``/``convert`` commands accept document templates
and parameters for producing customized output.

Template Specification
~~~~~~~~~~~~~~~~~~~~~~

Templates can be specified in several ways:

- **File path** — a path to a template file (``-t my_template.tex``).
- **Template id** — a registered id (``-t base``, ``-t report``). For a bare id the
  per-format variant matching the output format is used, so ``-t base`` renders html,
  latex, and typst exports each with their own ``base.XXX`` template.
- **Format name** — ``base.html``, ``base.tex``, ``base.typ``, etc.

Template Parameters
~~~~~~~~~~~~~~~~~~~

Parameters are supplied in three ways, applied in this precedence order (later sources override earlier):

1. **``-p/--parameters SPEC``** — a JSON object string or a path to a JSON file.
   Paths can be given directly or prefixed with ``@`` (``-p @params.json``).

   .. code-block:: bash

       # inline JSON
       pydocmaker build doc.md -p '{"pTitle": "From JSON"}'

       # path to a JSON file
       pydocmaker build doc.md -p params.json

2. **Unknown ``--name value`` arguments** — any ``--key value`` (or ``--key=value``)
   not recognized by argparse is collected as a template parameter. Boolean flags
   (a bare ``--flag``) become ``true``. String values are JSON-parsed when possible
   (``--n 5`` becomes the integer ``5``; ``--title "My Report"`` stays a string).

   .. code-block:: bash

       pydocmaker example pdf -t base --pAuthor "me" --pTitle "My Report"
       pydocmaker build README.md -t base.tex --pTitle "Readme"
       pydocmaker show html doc.json -t base --pTitle "Doc"

3. **Template file references** — string parameter values that point at existing files
   (searched next to the template first, then the working directory, then as absolute paths)
   are automatically loaded as attachments and rewritten to their bare file name.

   .. code-block:: bash

       pydocmaker build README.md -t report.tex --pProjectLogo INAF-Logo.png

Where Template Options Are Accepted
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Template options (``-t``/``-p``/``-a``) are only accepted where they have an
effect. Operations that do not use templates reject them with an error instead
of silently ignoring them:

- the non-templating commands ``check``, ``extract``, ``template`` and
  ``templates`` reject ``-p``/``-a`` (and ``-t`` for ``check``/``extract``);
- the direct typst build (``build my_report.typ``) rejects both a template and
  template parameters, since the typst source is compiled as-is.

.. code-block:: bash

    # error: the direct typst build accepts no template parameters
    pydocmaker build my_report.typ --pTitle "T"

    # error: check does not accept template options
    pydocmaker check my_document.json -t base


Attachments
~~~~~~~~~~~

Templates often reference sibling files (logos, images, bibliography files).

**File-reference scanning** — When a template is given as a *file path* via ``-t``, pydocmaker
automatically scans the template source for file references and loads existing files as
attachments:

- **LaTeX**: ``\includegraphics{...}``, ``\input{...}``, ``\include{...}``
- **Typst**: ``#image("...")``, ``#include "..."``, ``#import "..."``
- **Block-template parameter defaults** — values that look like file names (e.g. ``MKE.png`` with surrounding spaces in the source)

Unresolved references only produce a warning; the template still renders.

**Registered template ids** use the existing ``{name}.assets`` folder convention
(their sources are not scanned).

**Explicit attachments** — Use ``-a/--assets`` for files or folders that are not
referenced inside the template source, or when regex-based reference scanning cannot
resolve paths (e.g. ``\graphicspath``-directed paths or jinja-interpolated dynamic paths).

The flag is repeatable; each file is attached under its own name, and each folder is
attached recursively with the file's path relative to the folder as the key.
Hidden files and directories (``.git``, ``__pycache__``, dotfiles) are skipped.

.. code-block:: bash

    pydocmaker build README.md -t report.tex -a ./assets -a extra_logo.png


Example Workflows
-----------------

Below are common end-to-end workflows demonstrating the most useful CLI combinations.

Basic conversion (no template)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert a markdown file to PDF using the default template.

.. code-block:: bash

    # README.md -> README.pdf
    pydocmaker build README.md

    # Specify the format explicitly
    pydocmaker build README.md -f html

    # Output to a custom path
    pydocmaker build README.md -f pdf -o my_report.pdf


Apply a template with parameter overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build a report using the built-in ``base.tex`` template and set the title and author.

.. code-block:: bash

    # Using unknown long options as template parameters
    pydocmaker build README.md -f tex -t base.tex \
        --pTitle "Readme Report" --pAuthor "Jane Doe"

    # Or with a JSON parameters file
    pydocmaker build README.md -f tex -t base.tex -p report_params.json

The JSON file ``report_params.json`` might contain::

    {
        "pTitle": "Readme Report",
        "pAuthor": "Jane Doe",
        "pAcronyms": {}
    }


Create a report from the example document
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generate a PDF of the built-in example document using a specific template.

.. code-block:: bash

    pydocmaker example pdf -t report -o example_report.pdf

    # With custom title
    pydocmaker example pdf -t report --pTitle "Example"


Validate and inspect templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check a block template for errors and see what parameters it declares.

.. code-block:: bash

    # Validate and extract parameters
    pydocmaker check base.tex
    pydocmaker extract base.tex

    # Redirect parameters to a file for later use
    pydocmaker extract base.html > template_params.json


Extract a template for editing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copy a registered template to a file, edit it, then use it.

.. code-block:: bash

    # Copy the base LaTeX template
    pydocmaker template base.tex -o my_custom_template.tex

    # Edit my_custom_template.tex, then use it:
    pydocmaker build README.md -t my_custom_template.tex --pTitle "Custom"


Merge multiple inputs
~~~~~~~~~~~~~~~~~~~~~

Combine several documents into a single output.

.. code-block:: bash

    # Merge a JSON doc and a markdown file into a docx
    pydocmaker build section1.json section2.md -o merged_report.docx

    # Merge multiple markdown files into one PDF
    pydocmaker build ch1.md ch2.md ch3.md -o full_report.pdf


Inspect a saved document
~~~~~~~~~~~~~~~~~~~~~~~~

Show a saved pydocmaker document in various formats on the terminal.

.. code-block:: bash

    # Show in rich console format
    pydocmaker show rich doc.json

    # Show as HTML (opens in browser if possible)
    pydocmaker show html doc.json

    # Show as plain markdown
    pydocmaker show md doc.json


Quick-start Cheat Sheet
-----------------------

.. code-block:: bash

    # === Generate ===
    pydocmaker example pdf -o example.pdf                   # example doc -> PDF
    pydocmaker example md                                    # example doc -> stdout (markdown)

    # === Convert ===
    pydocmaker build README.md                               # markdown -> PDF
    pydocmaker build README.md -f html                       # markdown -> HTML
    pydocmaker build doc.json -f docx                        # JSON -> docx
    pydocmaker build a.md b.md c.md -f pdf -o final.pdf     # merge 3 markdowns

    # === Templating ===
    pydocmaker build README.md -t base.tex --pTitle "Hi"    # with template + params
    pydocmaker build README.md -p params.json               # params from JSON file
    pydocmaker build README.md -a logo.png                  # with attachment

    # === Inspect ===
    pydocmaker check base.tex                               # validate a template
    pydocmaker extract base.typ                             # print params as JSON
    pydocmaker show rich doc.json                           # terminal preview
    pydocmaker show html doc.json                           # browser preview

    # === Template management ===
    pydocmaker template html                                # print base HTML template
    pydocmaker template report.typ.j2 -o custom.typ         # copy template to file

    # === Help ===
    pydocmaker --help                                      # main help
    pydocmaker build --help                                # build command help
