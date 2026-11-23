Block Templating Engine
=======================

pydocmaker supports **comment-delimited block templates** as an alternative to the classic Jinja2
(``.j2``) templates. Block templates are plain ``.html`` / ``.tex`` / ``.typ`` files that stay valid
and compilable standalone while carrying ``pydocmaker:`` markers inside comments.

All markers must be alone on their line (optional leading/trailing whitespace):

* ``pydocmaker:parameters:begin`` / ``pydocmaker:parameters:end``
* ``pydocmaker:body:begin`` / ``pydocmaker:body:end``
* ``pydocmaker:param:<name>`` -- one per parameter; the native assignment starts on the next line

Comment syntax per format: ``<!-- ... -->`` (HTML), ``% ...`` (LaTeX), ``// ...`` (Typst).

Parameter value representation
------------------------------

* **LaTeX**: scalars via ``\providecommand{\name}{value}``, dicts via
  ``\newcommand{\name}{%\begin{description}\item{KEY}{VALUE}...\end{description}}``,
  lists via ``\newcommand{\name}{%\begin{itemize}\item VALUE...\end{itemize}}``.
  Special characters are escaped (``\ & % $ # _ { } ~ ^``). Note that parameter names colliding
  with LaTeX kernel macros (``title``, ``author``, ``date``) produce inert definitions; use names
  such as ``reporttitle`` for values to be displayed.
* **Typst**: ``#let name = <literal>`` with strings, numbers, ``true``/``false``/``none`` and
  nested ``(k: v, ...)`` dictionaries / ``(a, b, ...)`` arrays.
* **HTML**: scalars via ``<meta name="pydocmaker:param:<name>" content="...">``, dicts and lists
  via ``<script type="application/json" data-pydocmaker-param="<name>">...</script>``.

Everything inside a parameters block that is not a ``param:`` marker plus assignment is static
content and is preserved verbatim on scaffold/update.

Render semantics
----------------

Rendering replaces the content between the ``body`` markers with the generated document body and
applies parameter overrides; the file on disk is **never modified** by rendering. Block defaults
take lower precedence than explicit ``template_params``. Unknown parameter names are appended to
the parameters block; parameters without values are dropped (consistent with Jinja2's
``Undefined`` handling).

Engine selection
----------------

``Doc.to_html``, ``Doc.to_typst`` and ``Doc.to_pdf`` accept ``template_engine='auto'`` (default):
sources containing block markers are rendered by the block engine, everything else by the Jinja2
engine. ``'jinja2'`` and ``'blocks'`` force one engine explicitly.

Template directory resolution: an exact file name (``'base.tex'``) resolves to the block file even
when a ``base.tex.j2`` twin exists; short IDs (``'base'``) prefer the ``.j2`` file (backward
compatibility). ``<id>.params.json`` files stay authoritative for default parameters.

Python API
----------

.. code-block:: python

    from pydocmaker import blocktmpl

    blocktmpl.detect(source)                    # True if block markers are present
    doc = blocktmpl.parse(source, tformat='typ')  # -> BlockDocument
    out = blocktmpl.scaffold(source, tformat='typ', params={'title': 'V1'})
    out = blocktmpl.update_params(source, {'title': 'V2'})   # idempotent
    out = blocktmpl.render(source, body='...', params={'title': 'V2'})

Shipped example templates: ``base.tex``, ``base.html``, ``base.typ`` (see ``src/pydocmaker/templates/``).
