

// ============================================================================
// MPIfR - TDD report template (Typst)
// ============================================================================
// This is the Typst counterpart of `tdd-template-report.tex` and produces a
// document with the same look and the same parameter interface.
//
// The file is valid standalone Typst (place the logo assets next to it) and is
// understood by the pydocmaker block templating engine
// (https://pypi.org/project/pydocmaker/). Parameter marker names are identical
// to the ones used in the .tex template, so the same parameters can be used to
// fill either template.
// ============================================================================

// pydocmaker:parameters:begin

// the project name you want to give
// pydocmaker:param:p_project
#let p_project = "Example Project"

// any logo for your project (file name of an image placed next to this file)
// pydocmaker:param:p_projectlogo
#let p_projectlogo = "MKE.png"

// any title text you want to give this document
// pydocmaker:param:pDocTitle
#let pDocTitle = "New Document Title"

// any identification number you want to give your document
// pydocmaker:param:pDocNo
#let pDocNo = "TDD-RX-1234"

// the revision of this document
// pydocmaker:param:pDocRevision
#let pDocRevision = "DRAFT 1"

// the document status
// pydocmaker:param:pDocStatus
#let pDocStatus = "WIP"

// the document date (YYYY-MM-DD), empty means todays date
// pydocmaker:param:pDate
#let pDate = ""

// the author name
// pydocmaker:param:pAuthorName
#let pAuthorName = "Michael Musterer"

// the approved by name
// pydocmaker:param:pApprovedBy
#let pApprovedBy = "Birgit Musterfrau"

// the released by name
// pydocmaker:param:pReleasedBy
#let pReleasedBy = "Hans Mustermann"

// the raw footer string on the left
// pydocmaker:param:pFooterStringLeft
#let pFooterStringLeft = ""

// the raw footer string on the right
// pydocmaker:param:pFooterStringRight
#let pFooterStringRight = ""

// the acronyms given as "label": "description" pairs
// pydocmaker:param:pAcronyms
#let pAcronyms = (FTE: "Full Time Equivalent", PBS: "Product Breakdown Structure", SOW: "Statement Of Work", WBS: "Work Breakdown Structure", WP: "Work-Package")

// the applicable documents given as "label": "description" pairs
// pydocmaker:param:pApplicables
#let pApplicables = (AD1: "Applicable Document 1", AD2: "Applicable Document 2")

// the reference documents given as "label": "description" pairs
// pydocmaker:param:pReferences
#let pReferences = (RD1: "Reference Document 1", RD2: "Reference Document 2", RD3: "Reference Document 3")

// set to true to show the signature panel on the title page
// pydocmaker:param:pShowSignaturePanel
#let pShowSignaturePanel = true

// set to true to hide the full title page (renders a compact title block)
// pydocmaker:param:pHideTitlePage
#let pHideTitlePage = false

// set to true to add the confidentiality / proprietary note
// pydocmaker:param:pIsConfidential
#let pIsConfidential = true

// set to true to add a page break before the acronyms (and after the TOC)
// pydocmaker:param:pPageBreakAfterLists
#let pPageBreakAfterLists = true

// pydocmaker:parameters:end


// ============================
// HELPER FUNCTIONS
// ============================

// interprets booleans, 1/0 numbers and "1"/"true"/"yes" strings as flags
// (pydocmaker may pass flags as booleans, numbers or strings)
#let truthy(v) = {
  if v == true or v == 1 {
    true
  } else if type(v) == str {
    let s = lower(trim(v))
    s == "1" or s == "true" or s == "yes" or s == "on"
  } else {
    false
  }
}

// the date shown throughout the document, empty pDate means todays date
#let the-date = if pDate == none or pDate == "" {
  datetime.today().display("[year]-[month]-[day]")
} else {
  str(pDate)
}

// iterate over a dict or an array of (label, description) pairs
#let kv-pairs(v) = {
  if type(v) == dictionary {
    v.pairs()
  } else if type(v) == array {
    let out = ()
    for item in v {
      out.push((item.at(0), item.at(1)))
    }
    out
  } else {
    ()
  }
}

// renders a "label": "description" collection in the style of the LaTeX
// description environment used in the .tex template (bold label + text)
#let render-description(items) = {
  let rows = ()
  for (label, body) in kv-pairs(items) {
    rows.push(strong(label))
    rows.push([#body])
  }
  if rows.len() > 0 {
    table(
      columns: (auto, 1fr),
      column-gutter: 1.2em,
      stroke: none,
      inset: (x: 0pt, y: 5pt),
      ..rows,
    )
  }
}

// an unnumbered heading which does not show up in the table of contents
// (the equivalent of LaTeX \section* / \subsection*)
#let unnumbered-heading(level, title) = {
  set heading(numbering: none)
  heading(level: level, outlined: false)[#title]
}

// optional content replacing the whole (full page) title page
#let pTitlePage = none

// number of roman-numbered front matter pages (title page and, if enabled,
// the proprietary note). All following pages are numbered arabic starting at 1,
// exactly like \pagenumbering{arabic} in the .tex template.
#let fm-pages = 1 + if truthy(pIsConfidential) { 1 } else { 0 }

// left side of the running header: logos + document/project info
#let header-left = [
  #box[#image("MPIfR-Logo.png", height: 1.2cm)]
  #h(0.3cm)
  #box[#image("logo_tdd_RGB_Compact.png", height: 1.2cm)]
  #h(0.2cm)
  #box(width: 3.5cm)[
    #set text(size: 8pt)
    #text(weight: "bold", pDocTitle) \
    #p_project
  ]
]


// ============================
// LAYOUT SETUP
// ============================

// pydocmaker:b_pagesetup:begin

#set document(title: pDocTitle)

#set text(
  lang: "en",
  size: 11pt,
  font: ("Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"),
)

#set par(justify: true)

#set page(
  paper: "a4",
  margin: (left: 2.5cm, right: 2.5cm, top: 3.45cm, bottom: 3.7cm),
  header-ascent: 0.5cm,
  footer-descent: 0.4cm,
  header: context {
    // here().page() is the physical page number (used to hide the header on the
    // title page and to tell the roman front matter from the arabic pages),
    // the page counter carries the display number (\pagenumbering in the .tex)
    let pg-phys = here().page()
    let pg = counter(page).get().first()
    let total = counter(page).final().first()
    let cur = if pg-phys <= fm-pages { numbering("i", pg) } else { str(pg) }
    if pg-phys > 1 [
      #set text(size: 8pt)
      #block(
        stroke: (bottom: 0.4pt),
        inset: (bottom: 4pt, rest: 0pt),
        grid(
          columns: (1fr, auto),
          column-gutter: 0.4cm,
          align: (left, right),
          header-left,
          table(
            columns: (auto, auto),
            stroke: 0.5pt,
            inset: (x: 5pt, y: 2.5pt),
            [Doc.\# :], [#pDocNo],
            [Rev. :], [#pDocRevision],
            [Date :], [#the-date],
            [Page :], [#cur / #total],
          ),
        ),
      )
    ]
  },
  footer: context {
    let pg = here().page()
    let show-rule = truthy(pIsConfidential)
    let show-text = pFooterStringLeft != "" or pFooterStringRight != ""
    if pg > 1 and (show-rule or show-text) [
      #set text(size: 9pt)
      #block(
        stroke: (top: if show-rule { 0.4pt } else { none }),
        inset: (top: 4pt, rest: 0pt),
        grid(
          columns: (1fr, auto),
          align: (left, right),
          [#pFooterStringLeft],
          [#pFooterStringRight],
        ),
      )
    ]
  },
)

// pydocmaker:b_pagesetup:end


// ============================
// DOCUMENT STYLING
// ============================

// heading numbering and sizes like the LaTeX article class ("1", "1.1", ...)
#set heading(numbering: "1.1")
#show heading: set par(justify: false)
#show heading.where(level: 1): set text(size: 1.31em)
#show heading.where(level: 2): set text(size: 1.09em)

// figures, tables and code blocks
#set figure(numbering: "1")
#set figure.caption(separator: ": ")

#show link: set text(fill: blue)

#show raw.where(block: true): set text(size: 0.8em)
#show raw.where(block: true): it => block(
  width: 100%,
  inset: 8pt,
  stroke: 0.4pt + black,
  it,
)


// ============================
// TITLE PAGE
// ============================

// pydocmaker:b_titlepage:begin

#if truthy(pHideTitlePage) [
  // compact title block instead of a full title page
  #if pDocTitle != "" [
    #align(center)[
      #text(size: 14.4pt)[#p_project] \
      #v(0.8cm)
      #text(size: 24.9pt)[#pDocTitle] \
      #v(0.8cm)
      #text(size: 12pt)[#smallcaps[#pAuthorName]] \
      #text(size: 10pt)[#the-date]
    ]
    #v(1cm)
  ]
  // restart page numbering (arabic, starting at the table of contents)
  #if not truthy(pIsConfidential) [
    #counter(page).update(0)
  ]
  #pagebreak()
] else if pTitlePage != none [
  #pTitlePage
  // restart page numbering (arabic, starting at the table of contents)
  #if not truthy(pIsConfidential) [
    #counter(page).update(0)
  ]
  #pagebreak()
] else [
  #page(
    header: none,
    footer: none,
    numbering: none,
    margin: (left: 2.5cm, right: 2.5cm, top: 1.9cm, bottom: 3.7cm),
  )[
    // tight paragraph spacing like in LaTeX, all gaps are explicit below
    #set par(spacing: 0em)
    // logos of MPIfR and the TDD with a horizontal rule below
    #align(center)[
      #block(
        width: 15cm,
        stroke: (bottom: 0.4pt),
        inset: (bottom: 3pt, x: 0pt, top: 0pt),
        grid(
          columns: (1fr, auto),
          align: (left, right),
          [#image("MPIfR-Logo.png", width: 8cm)],
          [#image("logo_tdd_RGB_Wide.png", width: 5cm)],
        ),
      )
    ]
    #v(1.6cm)
    // project logo and project name
    #align(center)[
      #if truthy(pShowSignaturePanel) [
        #image(p_projectlogo, height: 6cm) \
      ] else [
        #image(p_projectlogo, height: 7cm) \
      ]
      #text(size: 14.4pt)[#p_project]
    ]
    #if truthy(pShowSignaturePanel) [
      #v(0.5cm)
    ] else [
      #v(1.5cm)
    ]
    // title, document number, revision, status and date
    #align(center)[
      #text(size: 24.9pt)[#pDocTitle]

      #v(0.8cm)
      #text(size: 12pt)[#smallcaps[#pDocNo]] \
      #text(size: 12pt)[#smallcaps[Revision : #pDocRevision]] \
      #text(size: 12pt)[#smallcaps[Status : #pDocStatus]] \
      #text(size: 12pt)[#smallcaps[#the-date]]

      #if truthy(pShowSignaturePanel) [
        #v(1.5cm)
        // signature panel
        #table(
          columns: (2.6cm, 4cm, 3cm, 4cm),
          stroke: (y: none),
          inset: (x: 4pt, y: 10pt),
          table.hline(stroke: 0.5pt),
          [], [*Name*], [*Organisation*], [*Signature*],
          table.hline(stroke: 0.5pt),
          [Prepared by], [#pAuthorName], [], [],
          table.hline(stroke: 0.5pt),
          [Approved by], [#pApprovedBy], [], [],
          table.hline(stroke: 0.5pt),
          [Released by], [#pReleasedBy], [], [],
          table.hline(stroke: 0.5pt),
        )
      ] else [
        #v(0.5cm)
        #text(size: 12pt)[#smallcaps[Author : #pAuthorName]]
      ]
    ]
    // restart page numbering (arabic, starting at the table of contents)
    #if not truthy(pIsConfidential) [
      #counter(page).update(0)
    ]
  ]
]

// pydocmaker:b_titlepage:end


// ============================
// CONFIDENTIALITY
// ============================

// pydocmaker:b_confidential:begin

#if truthy(pIsConfidential) [
  #unnumbered-heading(1)[Proprietary note]

  This document is our exclusive and legal property and may under no
  circumstances be reproduced nor supplied to third parties nor be used for the
  purpose of construction or manufacture without our consent.

  #v(3cm)
  #align(center)[
    #block(width: 9cm)[
      #align(left)[
        #strong[Max Planck Institute for Radio Astronomy] \
        Auf dem Hügel 69 \
        53121 Bonn / Germany \
        #v(0.6em)
        #grid(
          columns: (auto, auto),
          column-gutter: 1em,
          [Phone:], [+49 228 525-0],
          [Fax:], [+49 228 525-229],
        )
        #v(0.6em)
        www.mpifr-bonn.mpg.de
      ]
    ]
  ]
  #v(1fr)
  Copyright #datetime.today().year() Max Planck Institute for Radio Astronomy.
  All rights reserved. No part of this document may be reproduced or
  transmitted in any means, electronic or mechanical, for any purpose without
  the written permission of the Max Planck Institute for Radio Astronomy.

  This document is proprietary to the Max Planck Institute for Radio Astronomy,
  contains propriety information and shall be protected by a receiving party in
  accordance with the Uniform Trade Secrets Act, prevailing intellectual
  property rights laws, and the terms of the recipient's contracts and
  agreements with the Max Planck Institute for Radio Astronomy.
  // restart page numbering (arabic, starting at the table of contents)
  #counter(page).update(0)
  #pagebreak()
]

// pydocmaker:b_confidential:end


// ============================
// TABLE OF CONTENTS
// ============================

#outline(title: [Table of Contents], depth: 3)

#if truthy(pPageBreakAfterLists) {
  pagebreak()
}


// ============================
// ACRONYMS
// ============================

// pydocmaker:b_acronyms:begin

#if kv-pairs(pAcronyms).len() > 0 {
  if truthy(pPageBreakAfterLists) {
    unnumbered-heading(1)[List of acronyms]
  } else {
    unnumbered-heading(2)[List of Acronyms]
  }
  render-description(pAcronyms)
  if truthy(pPageBreakAfterLists) {
    pagebreak()
  }
}

// pydocmaker:b_acronyms:end


// ============================
// APPLICABLES
// ============================

// pydocmaker:b_applicables:begin

#let has-applicables = kv-pairs(pApplicables).len() > 0
#let has-references = kv-pairs(pReferences).len() > 0

#if has-applicables {
  unnumbered-heading(2)[Applicable Documents]
  render-description(pApplicables)
}

// pydocmaker:b_applicables:end


// ============================
// REFRENCES
// ============================

// pydocmaker:b_references:begin

#if has-references {
  unnumbered-heading(2)[Reference Documents]
  render-description(pReferences)
}

// pydocmaker:b_references:end

#if has-applicables or has-references {
  pagebreak()
}


// ============================
// DOCUMENT BODY
// ============================

// pydocmaker:body:begin
= pydocmaker
<pydocmaker>

#block[
#figure([#box(width: 150.0pt, image("icon.png"));],
  caption: [
    Icon
  ]
)

]
A minimal easy to use python document maker to create reports in `pdf`, `md`, `typst`, `html`, `docx`, `tex` and more formats. Written purely in python, but optional features use external non python libraries such as `typst` or pandoc \(if installed). Nearly no code written by AI \(some test cases, and some documentation was written by AI tools)

- #strong[NOTE:] some functions will try to call pandoc and fall back if not found.
- #strong[NOTE:] exporting PDFs by default works using `typst`. All other engines need optional dependencies, such as either a latex compiler or Microsoft Word, or Libreoffice.

Full documentation at https:\/\/pydocmaker.readthedocs.io/en/latest/

For an #strong[example of a created PDF document] please see `README.pdf` \(located within the root folder of this repository) which is this `README.md` file converted to pdf via `pydocmaker` and `typst` with the `report` template.

== Installation
<installation>
Install via:

```bash
pip install pydocmaker
```

== TL;DR; Code examples
<tldr-code-examples>
=== Snippet:
<snippet>
```python

import pydocmaker as pyd

doc = pyd.Doc.get_example()
doc.show()
```

=== Minimal Usage Example:
<minimal-usage-example>
```python

import pydocmaker as pyd

doc = pyd.Doc() # basic doc. Workd like a list, We always append new content to the end
doc.add('dummy text') # adds raw text

# this is how to add parts to the document
doc.add_pre('this will be shown as preformatted') # preformatted
doc.add_md('This is some *fancy* `markdown` **text**') # markdown
doc.add_tex(r'\textbf{Hello, LaTeX!}') # latex
doc.add_table([['John Doe', "30"]], header=['Name', 'Age'], caption='example table') # table

# this is how to add an image from link
doc.add_image("https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png", caption='Github Logo')

# this is how to add matplotlib figures to your report
import matplotlib.pyplot as plt
fig = plt.figure()
plt.plot([1,2,3], [6,5,7])
doc.add_image(fig, caption='Example figure', width=0.7)

# show will render and show a doc when in an iPython
# environment such as jupyter or colab, on the terminal 
# it will fall back to use rich console instead
doc.show()
```

=== "Showing" Documents in iPython/Terminal
<showing-documents-in-ipythonterminal>
the `Doc` class has a method called `show` which will detect if its running in `Ipython`. If it does it will render the document and show it. If not it will fallback to a rich consiole and do its best to show the content on the terminal \(on a terminal image support is very limited). The desired rendering format can be set with the `engine` argument. `rich`, `markdown`, `HTML`, or `PDF` is possible.

Any environment: #strong[NOTE];: when rendering with "rich" console image support is very limited, since images will be printed on the console as pixels \(with the size being scaled down to the console width)

```python
doc.show()
doc.show('rich')
doc.show('rich', embed_images=False)
```

In `Ipython` \(such as Jupyter or Colab) any of the following:

```python
doc.show('md')
```

Or:

```python
doc.show('html')
```

Or:

```python
doc.show('pdf')
```

#strong[NOTE];: some IDEs do not support the PDF option and instead open a "save" dialog, but in a browser with jupyter this works

=== Exporting:
<exporting>
export via:

```python
# returns string
text_html = doc.export('html')
# or write a file
doc.export('path/to/my_file.html')
```

Or alternatively:

```python
doc.to_html('path/to/my_file.html') # will write a HTML file
doc.to_pdf('path/to/my_file.pdf') # will write a PDF file via typst
doc.to_pdf('path/to/my_file.zip') # will write the whole latex project dir as a pdf file
doc.to_markdown('path/to/my_file.md') # will write a Markdown file
doc.to_docx('path/to/my_file.docx') # will write a docx file
doc.to_textile('path/to/my_file.textile.zip') # will pack all textile files and write them to a zip archive
doc.to_tex('path/to/my_file.tex.zip') # will pack all tex files and write them to a zip archive
doc.to_ipynb('path/to/my_file.ipynb') # will write a ipynb file

doc.to_json('path/to/doc.json') # saves the document
```

=== Saving and Loading \(Minimal)
<saving-and-loading-minimal>
A minimal example showing how to save and load `Doc` objects. `Doc.save` accepts a file path \(string or `pathlib.Path`) or a file-like object. When no path is provided it returns the rendered content \(HTML by default). `Doc.load` accepts a JSON string/bytes, a path, or a stream.

```python
import pydocmaker as pyd

doc = pyd.get_example()

# save to common formats (case-insensitive suffixes are supported)
doc.save('report.html')      # writes HTML
doc.save('report.json')      # writes JSON
doc.save('report.ipynb')     # writes an ipynb (may depend on environment)

doc2 = pyd.load('report.json') # load back in (should now be same as doc)

json_str = doc.save(format='json') # save as in-memory string in given format
loaded = pyd.load(json_str) # and load back

```

Supported save/load formats for `Doc.save`/`Doc.load`:

- `.html`, `.pyd`, `.pydoc` — HTML serialization/serialization used by pydocmaker
- `.ipynb` — Jupyter notebook \(may require additional environment support)
- `.json` — Raw document JSON \(recommended for round-trip fidelity)

#strong[Note];: Saving and Loading is fundamentally different from exporting a report \(e.G. to\_html), since save/load allows round trip loading and saving, while exporting makes nice documents to view in other other software and not load again.

=== Configuring Options:
<configuring-options>
All configurable options for this package are in `pydocmaker.options`. They are always callable functions with “\*\_get”, “\*\_set”, “\*\_scan” etc.

```python

import pydocmaker as pyd

pyd.options.pandoc_allowed_set(False)
print(pyd.options.pandoc_allowed_get())

pyd.options.pdf_engine_set('typst') # default
print(pyd.options.pdf_engine_get())
```

=== Block Templates \(comment-delimited, standalone-compilable)
<block-templates-comment-delimited-standalone-compilable>
Besides the classic Jinja2 templates \(`.j2` files), pydocmaker supports #strong[block templates];: plain `.html`, `.tex` and `.typ` files that carry `pydocmaker:` markers inside comments. These files stay valid and compilable standalone \(the native compilers ignore the parameter constructs and show the body placeholder) while pydocmaker can render, scaffold and update them without ever modifying the file on disk during render.

```latex
% pydocmaker:parameters:begin
% pydocmaker:param:title
\providecommand{\title}{My Report}
% pydocmaker:param:acronyms
\newcommand{\acronyms}{%
\begin{description}
\item{SNR}{Signal-to-Noise Ratio}
\end{description}
}
% pydocmaker:parameters:end

\begin{document}
% pydocmaker:body:begin
placeholder text
% pydocmaker:body:end
\end{document}
```

```typst
// pydocmaker:parameters:begin
// pydocmaker:param:title
#let title = "My Report"
// pydocmaker:param:acronyms
#let acronyms = (SNR: "Signal-to-Noise Ratio")
// pydocmaker:parameters:end

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
```

```html
<!-- pydocmaker:parameters:begin -->
<!-- pydocmaker:param:title -->
<meta name="pydocmaker:param:title" content="My Report">
<!-- pydocmaker:parameters:end -->
<body>
<!-- pydocmaker:body:begin -->
placeholder text
<!-- pydocmaker:body:end -->
</body>
```

Engine selection is automatic \(markers in the template source select the block engine) and can be forced with the `template_engine` argument \(`'auto'` \(default), `'jinja2'` or `'blocks'`) on `Doc.to_html`, `Doc.to_typst` and `Doc.to_pdf`:

```python
import pydocmaker as pyd

doc = pyd.Doc().add_text('Hello Block Templates')

# auto-detection: marked sources render through the block engine
out = doc.to_typst(template='my_template.typ', template_params={'title': 'Rendered'})

# explicit override
out = doc.to_typst(template='my_template.typ', template_engine='blocks')
out = doc.to_typst(template='my_template.typ', template_engine='jinja2')
```

The `pydocmaker.blocktmpl` subpackage exposes the engine directly:

```python
from pydocmaker import blocktmpl

blocktmpl.detect(source)                    # True if block markers are present
blocktmpl.parse(source, tformat='typ')      # parse into a BlockDocument
blocktmpl.scaffold(source, tformat='typ', params={'title': 'V1'})   # insert missing blocks
blocktmpl.update_params(source, {'title': 'V2'})                    # write values back (idempotent)
blocktmpl.render(source, body='...', params={'title': 'V2'})        # replace body + apply params
```

When resolved from a template directory, an #strong[exact file name] \(`'base.tex'`) resolves to the block file even when a `base.tex.j2` twin exists; #strong[short IDs] \(`'base'`) keep preferring the `.j2` file for backward compatibility. Shipped examples: `base.tex`, `base.html`, `base.typ` in `src/pydocmaker/templates/`.

NOTE for LaTeX templates: parameter names that collide with LaTeX kernel macros \(`title`, `author`, `date`) produce inert `\providecommand` definitions; use names such as `reporttitle` when the value shall be displayed in the document body.

=== Install Optional Requirements
<install-optional-requirements>
==== Optional Requirement `pandoc`
<optional-requirement-pandoc>
In order to get all functionality `pandoc` needs to be available. Please follow the recommended installation steps on the software projects webpage. For convenience the minimal installation is listed here:

On Linux \(Debian/Ubuntu) install via:

```bash
sudo apt update
sudo apt install pandoc
```

On MacOS:

```bash
brew install pandoc
```

On Windows:

```bash
winget install JohnMacFarlane.Pandoc
```

=== Optional Requirement `Latex`
<optional-requirement-latex>
In order to get all functionality a latex compiler needs to be available. Please follow the recommended installation steps on the webpage. For convenience the minimal installation is listed here:

On Linux \(Debian/Ubuntu) install via:

```bash
sudo apt update
sudo apt install texlive-full
```

On MacOS:

```bash
brew install --cask mactex
```

On Windows:

```bash
winget install MiKTeX.MiKTeX
```

=== Optional Requirement for DOCX either `libreoffice` or `win32com`
<optional-requirement-for-docx-either-libreoffice-or-win32com>
Some DOCX functionality need either Microsoft Windows and Microsoft Word and the `win32com` library or `libreoffice` available.

==== Installing `pywin32` \(Windows only)
<installing-pywin32-windows-only>
Install via:

```bash
pip install pywin32
```

==== Installing `libreoffice`
<installing-libreoffice>
On a Linux \(Debian/Ubuntu) system insall via:

```bash
sudo apt update
sudo apt-get install libreoffice
```

On MacOS:

```bash
brew install --cask libreoffice
```

On Windows:

```bash
winget install TheDocumentFoundation.LibreOffice
```

#strong[NOTE];: You need to add the folder with the libreoffice executeables to PATH in windows.

=== Writing Word docx Documents with templates and fields
<writing-word-docx-documents-with-templates-and-fields>
Below is an example on how to use pydocmaker to write word docx documents from format templates and also automatically "replace" fields \(MergeFields in Word or plain text) to be filled out in the docx document with text from python.

\(#strong[NOTE];: some of the code below utilized the `win32com` api and only works on windows)

prepare a report, a template and some fields in the template:

```python

import pydocmaker as pyd

metadata = {
    'repno': "1234",
    "summary": "This is a nice workflow for automatically creating docx documents",
    "date": "2025-12-13",
    "comment": f"this works!",
    "author": "Me"
}

# HOWTO: 
#  Adding MergeFields In Word to replace them later: 
#    Go to Insert → Quick Parts → Field → MergeField.
templatepath = 'my/path/template.docx'
outpath = 'my/path/outfile.docx'

# get a pyd example document to show the concept
doc = pyd.get_example()
```

this is the quick and easy way using the common pydocmaker api:

```python
# three different examples below
docx_bts = doc.to_docx("my/path/outfile.docx", template=templatepath, template_params=metadata, use_w32=False)
docx_bts = doc.to_docx("my/path/outfile_w32.docx", template=templatepath, template_params=metadata, use_w32=True)
docx_bts = doc.to_docx("my/path/outfile_w32_comp.pdf", template=templatepath, template_params=metadata, use_w32=True, as_pdf=True, compress_images=True)
```






// pydocmaker:body:end
