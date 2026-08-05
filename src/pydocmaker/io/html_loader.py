import json
from bs4 import BeautifulSoup
from jinja2 import Template
from pathlib import Path

from pydocmaker.core import Doc

ONLY_STORE_IMGS_ONCE = True

# HTML Template with styling, a rendered view for humans, 
# and a hidden JSON payload for lossless round-tripping.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pydocmaker Document</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.6; }
        .meta-box { background: #f4f4f4; padding: 15px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9em; }
        .block { margin-bottom: 15px; }
        .latex { font-family: serif; font-style: italic; background: #fafafa; padding: 2px 5px; }
        .verbatim { font-family: monospace; background: #eee; padding: 10px; white-space: pre-wrap; border-radius: 3px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 15px; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        th { background: #f0f0f0; }
        img { max-width: 100%; height: auto; display: block; margin: 10px 0; }
        hr { border: 0; border-top: 1px solid #ccc; margin: 20px 0; }
        .pydocmaker-footer {
            position: fixed;
            right: 20px;
            bottom: 20px;
            font-size: 0.8em;
            color: #777;
        }
    </style>
</head>
<body>

  {% if (title) %}
    <h1>{{ title }}</h1>
  {% endif %}
    <!-- This is where pydocmaker shows the document -->
    <div>{{ body }}</div>

    <div class="pydocmaker-footer"><a href="https://pypi.org/project/pydocmaker/" target="_blank">pydocmaker</a> document (HTML)</div>

    <!-- Lossless Payload for Deserialization -->
    <script type="application/json" id="pydocmaker-payload" data-generator="pydocmaker" data-version="1.0">
    {{ raw_json | safe }}
    </script>

    {{ js_part | safe }}

</body>
</html>
"""

JS_PART = """

    <script type="text/javascript">
const payloadScript = document.getElementById('pydocmaker-payload');
const jsonText = payloadScript.textContent;
const doc = JSON.parse(jsonText);

var imgCnt = 0;
function updateImages(el) {
    if (!el) return;

    if (el.typ === 'image') {
        const imgEl = document.querySelector(`img[data-img-no="${imgCnt}"]`);
        if (imgEl) {
            imgEl.src = el.imageblob;
            console.log(`Image element with data-img-no="${imgCnt}" replaced.`);
        } else {
            console.warn(`Image element with data-img-no="${imgCnt}" not found.`);
        }
        imgCnt += 1;
    } else if (Array.isArray(el.children)) {
        for (const child of el.children) {
            updateImages(child);
        }
    } else if (Array.isArray(el)) {
        for (const child of el) {
            updateImages(child);
        }
    }
}

updateImages(doc);

    </script>
"""

def io_check_html(doc_content: str) -> bool:
    """Checks if the HTML content is a valid pydocmaker document."""
    if not doc_content:
        return False
    if not isinstance(doc_content, str):
        return False
    if not doc_content.strip().startswith("<!DOCTYPE html>"):
        return False
    if not '<script type="application/json" id="pydocmaker-payload" data-generator="pydocmaker"' in doc_content:
        return False

    return True

def io_serialize_html(doc: Doc|list, only_store_images_once: bool=ONLY_STORE_IMGS_ONCE) -> str:
    """Serializes the pydocmaker node structure into a self-contained HTML file."""
    if isinstance(doc, list):
        doc = Doc(doc)

    if only_store_images_once:
        doc_vis = doc.copy()
        for el in doc_vis:
            if isinstance(el, dict) and el["typ"] == "image" and "imageblob" in el:
                del el["imageblob"]
    else:
        doc_vis = doc

    params = {
        "raw_json": doc.to_json(),
        "js_part": JS_PART if only_store_images_once else ""
    }
    html_output = doc_vis.to_html(template=HTML_TEMPLATE, template_params=params)
    
    return html_output


def io_deserialize_html(doc_content: str) -> Doc:
    """Reads the HTML content, extracts the embedded pydocmaker payload, and returns the exact node list."""
    soup = BeautifulSoup(doc_content, "html.parser")

    # Locate the embedded script payload
    payload_tag = soup.find("script", id="pydocmaker-payload")
    
    if not payload_tag:
        raise ValueError("Invalid file: This HTML file was not written by pydocmaker (missing payload tag).")
        
    # Validate generator and internal format markers
    generator = payload_tag.get("data-generator")
    if generator != "pydocmaker":
        raise ValueError(f"Format mismatch: Expected generator 'pydocmaker', found '{generator}'.")
        
    try:
        # Load back exact JSON data model structures
        document_nodes = json.loads(payload_tag.string)
        return Doc(document_nodes)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted internal pydocmaker data payload: {e}")


if __name__ == "__main__":
    doc = Doc.get_example()
    doc.update_meta({
        "title": "Sample Document",
        "author": "Jane Doe",
        "status": "draft"
    })

    file_path = "output_document.html"

    # 2. Serialize to HTML
    print(f"Serializing document to {file_path}...")
    html = io_serialize_html(doc)
    Path(file_path).write_text(html, encoding="utf-8")

    # 3. Deserialize back from HTML
    print(f"Deserializing document back from {file_path}...")
    restored_document = io_deserialize_html(html)

    # 4. Verify lossless round-trip
    assert doc.dumps() == restored_document.dumps(), "Round-trip failed! Data mismatch detected."
    print("Success! Round-trip serialization and deserialization completed with 100% fidelity.")
