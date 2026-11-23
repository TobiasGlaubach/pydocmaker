import datetime
import pydocmaker as pyd
from pathlib import Path

from importlib.metadata import metadata
pkg_meta = metadata("pydocmaker")

def get_project_url(meta, label):
    """Extract the URL for a given Project-URL label."""
    urls = meta.get_all("Project-URL") or []
    for entry in urls:
        if entry.startswith(label + ","):
            return entry.split(",", 1)[1].strip()
    return None

titlepage_info_dict = {
    "Repository":    get_project_url(pkg_meta, "Repository"),
    "Documentation": get_project_url(pkg_meta, "Documentation"),
}




version = 'v' + pyd.__version__
titlepage_info_dict = {'Version': version, **titlepage_info_dict}
# docname = f'#link("https://pypi.org/project/pydocmaker/")[pydocmaker] {version} documentation'
docname = f"https://pypi.org/project/pydocmaker/ {version} documentation"

date = datetime.datetime.now().strftime("%Y-%m-%d")
template_params = {
    "pTitle": "Pydocmaker Documentation",
    "pSubtitle": "Automatically created via pydocmaker from README.md",
    "pAuthor": "Tobias Glaubach",
    "pHideToc": False,

    "pDocCategory": "Report",
    "pHideDate": False,
    "pTitlepageInfoDict": titlepage_info_dict,

    "pHidePydocmaker": False,
    "pAbstract": pkg_meta["Summary"],

    "pHeaderStrLeft": docname,
    "pHeaderStrRight": date,

    "pVersion": version,

    "pAcronyms": {},
    "pApplicables": {},
    "pReferences": {},
}
path = (Path(__file__).parent / "README.md").absolute().resolve()
readme = path.read_text()
doc = pyd.Doc().add_md(readme)
doc.set_template_to_meta('base.typ', template_params=template_params)

doc.to_tex(path.with_suffix(".tex"))

doc.to_pdf(path.with_suffix(".pdf"))
print(path.as_uri())
