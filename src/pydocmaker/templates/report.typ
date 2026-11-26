// pydocmaker:parameters:begin
// pydocmaker:param:pTitle
#let pTitle = ""
// pydocmaker:param:pSubtitle
#let pSubtitle = ""
// pydocmaker:param:pAbstract
#let pAbstract = ""
// pydocmaker:param:pAuthor
#let pAuthor = ""
// pydocmaker:param:pDate
#let pDate = ""
// pydocmaker:param:pVersion
#let pVersion = "N/A"
// pydocmaker:param:pDocCategory
#let pDocCategory = ""
// pydocmaker:param:pLanguage
#let pLanguage = "en"
// pydocmaker:param:pAcronyms
#let pAcronyms = (:)
// pydocmaker:param:pApplicables
#let pApplicables = (:)
// pydocmaker:param:pReferences
#let pReferences = (:)
// pydocmaker:param:pTitlepageInfoDict
#let pTitlepageInfoDict = (:)
// pydocmaker:param:pHeaderStrLeft
#let pHeaderStrLeft = ""
// pydocmaker:param:pHeaderStrRight
#let pHeaderStrRight = ""
// pydocmaker:param:pFooterStrLeft
#let pFooterStrLeft = ""
// pydocmaker:param:pFooterStrRight
#let pFooterStrRight = ""
// pydocmaker:param:pHideToc
#let pHideToc = false
// pydocmaker:param:pHideDate
#let pHideDate = false
// pydocmaker:param:pHidePydocmaker
#let pHidePydocmaker = false
// pydocmaker:param:pLogoB64
#let pLogoB64 = ""
// pydocmaker:param:pLogoB64Pydocmaker
#let pLogoB64Pydocmaker = ""
// pydocmaker:parameters:end

#import "@preview/based:0.2.0": base64

// copied and modified from https://github.com/roland-KA/basic-report-typst-template/tree/main
// THANKS!

// ===== helper functions ====================

#let nonedefault(val, default: none) = if val == none or val == "" { default } else { val }

#let powered_by_link = link("https://pypi.org/project/pydocmaker/")[pydocmaker]

#let render_kvtable(mydict, prefix: none) = {
  let rows = ()
  let i = 0
  for (key, value) in mydict {
    i += 1
    let lbl = if prefix == none { key } else { prefix + str(i) }
    rows.push([#strong[#lbl] #label(key)])
    rows.push([#value])
  }
  table(
    columns: (auto, 1fr),
    stroke: none,
    ..rows,
  )
}

// ===== Functions for TITLE PAGE and COMPACT TITLE ===============

// ===== TITLE PAGE: `titlepage` ====================

#let titlepage(
  doc-category,
  doc-title,
  author,
  logo,
  heading-color,            // heading-color applies as well for the title
  info-size,                // used throughout the document for "info text"
  datetime-fmt,
) = {

  // ----- Page-Setup ------------------------
  set page(
    paper: "a4",
    margin: (top: 2.5cm, left: 2.0cm, right: 2.5cm, bottom: 2.0cm),
  )

  // Some basic rules for the title page layout:
  // - logo is right-justified
  // - all other elements are left-justified
  // - the page uses a grid of 1.5 cm units

  // ----- Logo ------------------------
  place(top + right,        // `place` so that the remaining layout is independent of the size of the logo
    logo,
  )

  v(4cm)                    // = 4 x 1.5 cm

  // ----- Title Category & Title ------------------------
  align(
    left,                   // 1 x 14pt + 2 x 36pt ≈ 2 x 1.5 cm
    text(weight: "regular", size: 14pt, fill: luma(50%),
      doc-category),
  )

  text(weight: "light", size: 36pt,  fill: heading-color,
    doc-title,
  )

  if nonedefault(pSubtitle) != none {
    v(0.3cm)

    text(weight: "regular", size: 18pt, fill: luma(50%),
      pSubtitle,
    )
  }

  if nonedefault(pAbstract) != none {
    v(3cm)
    text(weight: "bold", size: 11pt,
      [Abstract: ]
    )
    text(weight: "regular", size: 9pt,
      pAbstract,
    )
  }

  // ----- Info Block ------------------------
  set par(leading: 1em)
  let author-prefix = if nonedefault(pAuthor) == none { "" } else { "Author:" }

  let watermark = [This document was generated with #powered_by_link]

  let info-rows = ()
  for (key, value) in pTitlepageInfoDict {
    info-rows.push([#key])
    info-rows.push([#value])
  }

  place(
    bottom + left,
    text(
      weight: "regular", size: info-size, fill: black,
      grid(
        columns: (auto, auto),
        align: (right, left),
        gutter: 2.5em,
        row-gutter: 0.5em,
        [#author-prefix], [#author],
        ..(if nonedefault(pDate) != none {
          ([Date:], [#pDate])
        } else if not pHideDate {
          ([Date:], [#datetime.today().display(datetime-fmt)])
        } else {
          ()
        }),
        ..info-rows,
        ..(if not pHidePydocmaker {
          ([], [],
           [], [],
           [], [],
           grid.cell(colspan: 2)[#watermark])
        } else {
          ()
        }),
        // space at the bottom
        [], [],
        [], [],
        [], [],
        [], [],
        [], [],
        [], [],
        [], [],
        [], [],
        [], [],
        [], [],
      )
    )
  )
}


// ----- Main Template Function: `basic-report` ----------------------

#let basic-report(
  doc-category: none,
  doc-title: none,
  author: none,
  logo: none,
  language: "en",
  show-outline: true,
  heading-color: black,
  datetime-fmt: "[year]-[month]-[day]",
  body,
) = {

  // ----- Global Parameters ------------------------

  set document(title: doc-title)

  if author != none {
    set document(author: author)
  }

  set text(lang: language)

  let body-size = 11pt

  // heading font is used in this size for kind of "information blocks"
  let info-size = 10pt

  // heading font is used in this size for different sorts of labels
  let label-size = 9pt

  // are we inside or outside of the outline (for roman/arabic page numbers)?
  let in-outline = state("in-outline", true)

  // ----- Title Page ------------------------

  if (doc-title != none and doc-title != "") {
    counter(page).update(0)                     // so TOC after titlepage begins with page no 1 (roman)
    titlepage(
      doc-category,
      doc-title,
      author,
      logo,
      heading-color,
      info-size,
      datetime-fmt,
    )
  }

  // ----- Basic Text- and Page-Setup ------------------------

  set text(
    size: body-size,
  )

  set par(
    justify: true,
    leading: 0.75em,
    spacing: 1.65em,
    first-line-indent: 0em,
  )


  set page(
    paper: "a4",
    margin: (top: 2.5cm, left: 2.0cm, right: 2.5cm, bottom: 2.0cm),

    ..(if nonedefault(pHeaderStrLeft) != none or nonedefault(pHeaderStrRight) != none {
      (
        header: {
            grid(
                columns: (auto, auto),
                align: (left, right),
                row-gutter: 0.5em,
                text(size: label-size, nonedefault(pHeaderStrLeft, default: "")),
                text(size: label-size, nonedefault(pHeaderStrRight, default: "")),
                grid.cell(colspan: 2, line(length: 100%, stroke: 0.5pt)),
            )
        },
        header-ascent: 1.5em,
      )
    } else {
      (:)
    }),

    footer: context {
        let total = counter(page).final().at(0)
        grid(
          columns: (auto, 1fr, auto ),
          align: (left, center, right),
          row-gutter: 0.5em,
          grid.cell(colspan: 3, line(length: 100%, stroke: 0.5pt)),
          text(size: label-size, nonedefault(pFooterStrLeft, default: "")),

          text(size: label-size,
            number-type: "lining",
            {if in-outline.get() {
                let current = counter(page).display("i")
                [Page #current]
              } else {
                let current = counter(page).display("1")
                [Page #current of #total]
              }
            }
          ),
          text(size: label-size, nonedefault(pFooterStrRight, default: "")),
        )
    }
  )



  // ----- Table of Contents ------------------------

  if not pHideToc {

    if (show-outline) {

      outline(
        title: if language == "de" {
          "Inhalt"
        } else if language == "fr" {
          "Table des matières"
        } else if language == "es" {
          "Contenido"
        } else if language == "it" {
          "Indice"
        } else if language == "nl" {
          "Inhoud"
        } else if language == "pt" {
          "Índice"
        } else if language == "zh" {
          "目录"
        } else if language == "ja" {
          "目次"
        } else if language == "ru" {
          "Содержание"
        } else if language == "ar" {
          "المحتويات"
        } else {
          auto
        },
        indent: auto,
      )


      outline(
        title: "List of Figures",
        target: figure.where(kind: image),
      )

      // 3. Table of Tables
      outline(
        title: "List of Tables",
        target: figure.where(kind: table),
      )


      if pAcronyms.len() > 0 {
        heading(level: 1, outlined: false)[List of Acronyms]
        render_kvtable(pAcronyms)
      }


      if pApplicables.len() > 0 {
        heading(level: 1, outlined: false)[List of Applicable Documents]
        render_kvtable(pApplicables, prefix: "AD")
      }


      if pReferences.len() > 0 {
        heading(level: 1, outlined: false)[List of Reference Documents]
        render_kvtable(pReferences, prefix: "RD")
      }




      pagebreak()
      counter(page).update(1)     // so the first chapter starts at page 1 (now in arabic numbers)
      in-outline.update(false)

    } else {
      in-outline.update(false)    // even if outline is not shown, we want to continue with arabic page numbers
      counter(page).update(1)
    }
  } else {
    in-outline.update(false)      // even if outline is not shown, we want to continue with arabic page numbers
    counter(page).update(1)
  }

  // ----- Headings & Numbering Schemes ------------------------

  set heading(numbering: "1.")
  show heading: set text(fill: heading-color)
  show heading: set par(justify: false)
  show heading: set block(below: 2em)
  show text.where(fill: green): set text(fill: green.darken(35%))
  
  set figure(numbering: "1")
  show figure.caption: it => {
    set text(size: label-size)
    block(it)
  }


  // ----- Body Text ------------------------
  body

}




#set document(title: if nonedefault(pTitle) != none { pTitle })



#show link: set text(fill: blue, weight: 500)
#show link: underline
//#show table.cell.where(y: 0): set text(weight: "bold")
#show table.cell: set text(size: 0.7em)


// code blocks
#let code-border = luma(0)

#show raw.where(block: true): set text(size: 0.7em)
#show raw.where(block: true): it => {
    block(
        width:100%,
        inset: 10pt,
        radius: 4pt,
        stroke: 0.1pt + code-border,
        it,
    )
}


#set figure(numbering: "1")
#set figure.caption(separator: ": ") // With a nice separator
#set math.equation(numbering: "(1)", supplement: "Eq.")


#let logo = if nonedefault(pLogoB64) != none {
    image(base64.decode(pLogoB64), width: 2cm)
} else if not pHidePydocmaker and nonedefault(pLogoB64Pydocmaker) != none {
    image(base64.decode(pLogoB64Pydocmaker), width: 2cm)
} else {
    none
}

#show: it => basic-report(
  doc-category: nonedefault(pDocCategory),
  doc-title: nonedefault(pTitle),
  author: nonedefault(pAuthor),
  logo: logo,
  language: pLanguage,
  it
)


#set heading(numbering: (..nums) => {
  // 1. Convert the arguments to a regular positional array
  let parts = nums.pos()

  // 2. If the first item is 0, slice it off
  if parts.at(0, default: none) == 0 {
    parts = parts.slice(1)
  }

  // 3. Join the remaining numbers with dots and add a trailing period
  if parts.len() > 0 {
    parts.map(str).join(".") + "."
  }
})


// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
