import json
from typing import Union
from bs4 import BeautifulSoup
from jinja2 import Template
from pathlib import Path

from pydocmaker.core import Doc


# HTML Template: body starts empty; JS renders JSON -> HTML on load.
# A ?renderMarkdown=1 query param triggers CDN loading (snarkdown + highlight.js).
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pydocmaker Document</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.6; }
        .meta-box { background: #f4f4f4; padding: 15px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9em; }
        .block { margin-bottom: 15px; }
        .verbatim { font-family: monospace; background: #eee; padding: 10px; white-space: pre-wrap; border-radius: 3px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 15px; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        th { background: #fafafa; }
        img { max-width: 100%; height: auto; display: block; margin: 10px 0; }
        hr { border: 0; border-top: 1px solid #ccc; margin: 20px 0; }
        #pydocmaker-title { margin-bottom: 0; }
        #pydocmaker-body { margin-top: 20px; min-height: 100px; }
        .pydocmaker-footer {
            position: fixed;
            right: 20px;
            bottom: 20px;
            font-size: 0.8em;
            color: #777;
        }
        pre {
            white-space: pre-wrap;
        }
        .rendered-markdown h1 { font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
        .rendered-markdown h2 { font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
        .rendered-markdown h3 { font-size: 1.3em; }
        .rendered-markdown h4 { font-size: 1.1em; }
        .rendered-markdown h5 { font-size: 1em; }
        .rendered-markdown h6 { font-size: 0.9em; color: #666; }
        .rendered-markdown p { margin: 0.5em 0; }
        .rendered-markdown strong { font-weight: bold; }
        .rendered-markdown em { font-style: italic; }
        .rendered-markdown code { font-family: monospace; background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }
        .rendered-markdown pre { background: #f4f4f4; padding: 10px; border-radius: 3px; overflow-x: auto; }
        .rendered-markdown pre code { background: none; padding: 0; }
        .rendered-markdown ul, .rendered-markdown ol { margin: 0.5em 0; padding-left: 2em; }
        .rendered-markdown li { margin: 0.2em 0; }
        .rendered-markdown blockquote { border-left: 3px solid #ddd; margin: 0.5em 0; padding: 0.5em 1em; color: #666; }
        .rendered-markdown a { color: #0366d6; text-decoration: none; }
        .rendered-markdown a:hover { text-decoration: underline; }
        .rendered-markdown table { border-collapse: collapse; }
        .rendered-markdown th, .rendered-markdown td { border: 1px solid #ddd; padding: 6px 10px; }
        .rendered-markdown img { max-width: 100%; }
    </style>
</head>
<body>

{% if (title) %}
    <h1 id="pydocmaker-title">{{ title }}</h1>
{% endif %}

    <div style="display:flex;justify-content:flex-end;align-items:center;gap:12px;margin-bottom:10px;">
        <button style="font-size:0.85em;color:#888;text-decoration:none;" onclick="renderMain(false);">
            [show plain view]
        </button>
        <button style="font-size:0.85em;color:#0366d6;text-decoration:none;" onclick="renderMain(true);">
            [render nicely]
        </button>
    </div>


    <div id="pydocmaker-body"></div>

    <div class="pydocmaker-footer">
        <div style="display:flex;justify-content:flex-end;align-items:center;gap:12px;margin-bottom:10px;">
            <button style="font-size:0.85em;color:#888;text-decoration:none;" onclick="renderMain(false);">
                [show plain view]
            </button>
            <button style="font-size:0.85em;color:#0366d6;text-decoration:none;" onclick="renderMain(true);">
                [render nicely]
            </button>
        </div>
        <a href="https://pypi.org/project/pydocmaker/" target="_blank">pydocmaker</a> 
        document (HTML)
    </div>


    <!-- Lossless Payload for Deserialization -->
    <script type="application/json" id="pydocmaker-payload" data-generator="pydocmaker" data-version="1.0">
    {{ raw_json | safe }}
    </script>

    {{ js_part | safe }}

</body>
</html>
"""

JS_PART = r"""

    <script type="text/javascript">

/*
async function renderMd(text) {
    const { default: md } = await import('https://cdn.jsdelivr.net/npm/snarkdown@2.0.0/+esm');
    return md(text);
}*/

async function renderMd(text) {
  const [{ marked }, { default: dompurify }] = await Promise.all([
    import("https://cdn.jsdelivr.net/npm/marked/lib/marked.esm.js"),
    import("https://cdn.jsdelivr.net/npm/dompurify/dist/purify.es.mjs")
  ]);

  return dompurify.sanitize(marked.parse(text));
}

async function renderMain(renderMarkdown) {

    

    /* ---- decide rendering mode ---- */
    if (renderMarkdown) {
        /* need snarkdown – load from CDN first */
        // Load snarkdown (ESM)
        console.log("Importing CDN libs...");

        var tmp = await renderMd("**Hello World**"); /* just to import */

/*
        // Load highlight.js
        var hlLink = document.createElement('link');
        hlLink.rel = 'stylesheet';
        hlLink.href = 'https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github.min.css';
        document.head.appendChild(hlLink);

        var hlCore = document.createElement('script');
        hlCore.src = 'https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/lib/core.min.js';
        document.head.appendChild(hlCore);

        var langs = ['python','bash','javascript','xml'];
        for (var i=0;i<langs.length;i++) {
            var ls = document.createElement('script');
            ls.src = 'https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/lib/languages/' + langs[i] + '.min.js';
            document.head.appendChild(ls);
        }
*/
        console.log("Importing CDN libs...DONE");

    }

    var _imgCounter = 0;

    /* ---- helpers ---- */
    function esc(s) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(String(s)));
        return d.innerHTML;
    }

    /* ---- flatten iter-wrapped lists ---- */
    function flatten(lst) {
        var out = [];
        for (var i = 0; i < lst.length; i++) {
            var e = lst[i];
            if (!e || typeof e !== 'object') {
                if (typeof e === 'string' && e) out.push({typ: 'text', children: e});
                continue;
            }
            if (e.typ === 'iter' && e.children && Array.isArray(e.children)) {
                var sub = flatten(e.children);
                for (var j = 0; j < sub.length; j++) out.push(sub[j]);
            } else {
                out.push(e);
            }
        }
        return out;
    }

    var payloadScript = document.getElementById('pydocmaker-payload');
    if (!payloadScript) {
        document.getElementById('pydocmaker-body').innerText = "Error! Document empty!";
    };
    var doc = JSON.parse(payloadScript.textContent);
    var parts = await Promise.all(flatten(doc).map(e => digest(e, renderMarkdown)));
    document.getElementById('pydocmaker-body').innerHTML = parts.join('\n');


    async function digest(el, withMd) {
        if (!el || !el.typ) return '';
        var t = el.typ, ch = el.children || '', col = el.color || '', cap = el.caption || '';
        var sty = col ? ' style="color:' + col + ';"' : '';

        if (t === 'markdown') {
            if (withMd) {
                try { return '<div' + sty + ' class="rendered-markdown">' + await renderMd(ch) + '</div>'; }
                catch(x) {}
            }
            return '<div>pyd.markdown element:</div>\n<div' + sty + ' class="verbatim"><pre>' + esc(ch) + '</pre></div>';
        }
        if (t === 'latex') {
            return '<div>pyd.latex element:</div>\n<div' + sty + ' class="verbatim"><pre>' + esc(ch) + '</pre></div>';
        }
        if (t === 'verbatim') {
            var ln = el.lang || '';
            var cl = ln ? ' class="language-' + esc(ln) + '"' : '';
            var lb = cap ? '<div style="font-size:0.9em;color:#666;"><b>' + esc(cap) + '</b></div>' : '';
            return lb + '<div' + sty + '><pre><code' + cl + '>' + esc(ch) + '</code></pre></div>';
        }
        if (t === 'text' || t === 'line') {
            var txt = typeof ch === 'string' ? ch : esc(String(ch));
            return '<div' + sty + '>' + txt + '</div>';
        }
        if (t === 'image') {
            var src = el.imageblob || '';
            if (src && src.indexOf('data:image') !== 0) src = 'data:image/png;base64,' + src;
            var w = el.width ? ' max-width:' + Math.round((el.width||0.8)*100) + '%;' : '';
            var no = _imgCounter++;
            var tag = '<img data-img-no="' + no + '" src="' + src +
                '" style="display:block;margin:10px auto;width:auto;' + w + '"/>';
            var out = '<div style="text-align:center;">' + tag + '</div>';
            if (cap) out += '<div style="text-align:center;font-size:0.9em;color:#666;"><b>Figure:</b> ' + esc(cap) + '</div>';
            return out;
        }
        if (t === 'table') {
            var bdr = el.borders !== false;
            var hd = el.header || [], mt = el.children || [];
            var stb = bdr ? ' style="border:1px solid black;"' : '';
            var rows = [];
            if (hd.length) {
                var hc = '';
                for (var i=0;i<hd.length;i++) hc += '<th' + stb + '>' + esc(String(hd[i])) + '</th>';
                rows.push(hc);
            }
            for (var r=0;r<mt.length;r++) {
                var cc = '';
                for (var c=0;c<mt[r].length;c++) cc += '<td' + stb + '>' + esc(String(mt[r][c])) + '</td>';
                rows.push('  <tr>' + cc + '</tr>');
            }
            var tbl = '<table' + sty + '>' + rows.join('\n') + '</table>';
            if (cap) tbl += '<div style="text-align:center;font-size:0.9em;color:#666;"><b>Table:</b> ' + esc(cap) + '</div>';
            return tbl;
        }
        if (t === 'meta') return '';
        return '<div' + sty + ' class="verbatim"><pre>' + esc(String(ch)) + '</pre></div>';
    }

}
    
renderMain(false).then(() => {
    console.info("pydocmaker DONE!");
}).catch((e) => {
    console.error("pydocmaker ERROR!");
    console.error(e);
});

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

def io_serialize_html(doc: Union[Doc, list], **kwargs) -> str:
    """Serializes the pydocmaker node structure into a self-contained HTML file."""
    if isinstance(doc, list):
        doc = Doc(doc)


    doc_vis = Doc()

    params = {
        "raw_json": doc.to_json(),
        "js_part": JS_PART
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
    from pathlib import Path
    
    doc = Doc().add_md(Path("README.md").read_text())
    # doc = Doc.get_example()
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
