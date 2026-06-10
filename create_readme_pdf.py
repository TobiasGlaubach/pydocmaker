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
docname = f'#link("https://pypi.org/project/pydocmaker/")[pydocmaker] {version} documentation'
date = datetime.datetime.now().strftime("%Y-%m-%d")
template_params = {
    "title": "Pydocmaker Documentation",
    "subtitle": "Automatically created via pydocmaker from README.md",
    "author": "Tobias Glaubach",
    "hide_toc": False,  

    "doc_category": "Report",
    "hide_date": False,
    "titlepage_info_dict": titlepage_info_dict,

    "hide_pydocmaker": False,
    "abstract": pkg_meta["Summary"],

    "header_str_left": docname,
    "header_str_right": date,

    "version": version,
}

readme = (Path(__file__).parent / "README.md").read_text()
doc = pyd.Doc().add_md(readme)
doc.set_template_to_meta('report', tformat='typ', template_params=template_params)

path = Path('README.pdf').absolute().resolve()
res = doc.to_pdf(path)
print(path.as_uri())
