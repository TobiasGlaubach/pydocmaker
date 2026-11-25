// pydocmaker:parameters:begin
// pydocmaker:param:pTitle
#let pTitle = "My Report"
// pydocmaker:param:pAuthor
#let pAuthor = "Automatically Generated via pydocmaker"
// pydocmaker:param:pDate
#let pDate = ""
// pydocmaker:param:pAcronyms
#let pAcronyms = (:) // e.G: (SNR: "Signal-to-Noise Ratio", FFT: "Fast Fourier Transform")
// pydocmaker:param:pApplicables
#let pApplicables = (:)
// pydocmaker:param:pReferences
#let pReferences = (:)
// pydocmaker:parameters:end

#set page("a4")
#set document(title: if pTitle != "" { pTitle } else { "untitled" })

#show link: set text(fill: blue, weight: 700)
#show link: underline

// code blocks
#let code-border = luma(0)
#show raw.where(block: false): set text(weight: "semibold")
#show raw.where(block: true): set text(size: 0.8em)
#show raw.where(block: true): it => {
    block(
        width: 100%,
        inset: 10pt,
        radius: 4pt,
        stroke: 0.1pt + code-border,
        it,
    )
}

#set figure(numbering: "1")
#set figure.caption(separator: " - ")
#set math.equation(numbering: "(1)", supplement: "Eq.")

#let kv_rows(mydict) = {
    let rows = ()
    for (k, v) in mydict {
        rows.push([#strong[#k]])
        rows.push([#v])
    }
    rows
}

#let render_kvtable(mydict) = table(
    columns: (auto, 1fr),
    stroke: none,
    ..kv_rows(mydict),
)

#if pTitle != "" [
    #heading(level: 1)[#pTitle]
]
#if pAuthor != "" [
    #text(size: 0.9em)[#pAuthor]
]
#if pDate != "" [
    #text(size: 0.9em)[#pDate]
]

#if pAcronyms.len() > 0 [
    #heading(level: 2)[List of Acronyms]
    #render_kvtable(pAcronyms)
]
#if pApplicables.len() > 0 [
    #heading(level: 2)[Applicable Documents]
    #render_kvtable(pApplicables)
]
#if pReferences.len() > 0 [
    #heading(level: 2)[Reference Documents]
    #render_kvtable(pReferences)
]

// pydocmaker:body:begin
Document body placeholder
// pydocmaker:body:end
