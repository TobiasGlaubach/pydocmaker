from weasyprint import HTML
from pathlib import Path

p = Path("src/pydocmaker/templates/weasy.html").resolve()

html_content = p.read_text()

# Pass base_url="." if your HTML references local images or stylesheets
HTML(string=html_content, base_url=".").write_pdf("weekly_report.pdf")