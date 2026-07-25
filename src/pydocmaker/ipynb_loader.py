import io
import re
import json, os, sys
from dataclasses import dataclass
from typing import Any, List, Optional, Union
import base64
import string

from pydocmaker import util
from pydocmaker.core import Doc
from pydocmaker.backend import pandoc_api
from pydocmaker.util import log


def _ms(s):
    """Convert a string or list of strings to a single string."""
    if hasattr(s, '__iter__') and not isinstance(s, (str, bytes)):
        return "".join([_ms(item) for item in s])
    elif isinstance(s, bytes):
        return s.decode("utf-8")
    elif isinstance(s, str):
        return s
    else:
        return str(s)
    

# PX_TO_CM = 0.0265 
# PX_TO_PERC = lambda px: (px * PX_TO_CM) / 21.0

def get_between_pre(s, starter='<', ender='>'):
    ss = s.strip()

    if ss.startswith("<pre") and ss.endswith("</pre>"):
        cnt = 0
        for i, el in enumerate(ss, 1):
            if el == starter: cnt += 1
            if el == ender: cnt -= 1
            if cnt == 0: break
        if i > len(ss) - 6:
            return ss
        
        return ss[i:-6]
    return s

# slow but works
def get_between(s, starter='<', ender='>'):
    istart = None
    cnt = 0
    for i, el in enumerate(s, 1):
        if el == starter: 
            if istart is None:
                istart = i
            cnt += 1
        if el == ender: 
            cnt -= 1
        if not istart is None and cnt == 0: 
            break
    return istart, i-1


def html2md(s:str) -> Doc:
    
    md = pandoc_api.pandoc_convert(s, "html", "markdown")
    return clean_md(md)

def clean_md(md:str) -> Doc:
    doc = Doc()
    md = md.replace("<div>", "").replace("</div>", "")
    lines = md.split('\n')
    block = []
    for l in lines:
        ls = l.strip()
        # if l.startswith("![](data:image"):
        # if re.match(r'^!\[[^\]]*\]\(data:image/png.*$', l):
        if ls.startswith('![') and '](data:image' in ls:
            if block:
                doc.add_md('\n'.join(block)) # add prior existing as md
            istart, iend = get_between(l, '(', ')')
            imageblob = str(l[istart:iend])
            imageblob = imageblob.split(';base64,')[-1]
            if imageblob:
                try:
                    rest = str(l[min(iend+1, len(l)-1):])
                    w = rest.split('max-width:')[-1].split('%')[0]
                    width = float(w) / 100 if w else None
                except Exception as err:
                    width = None

                doc.add_image(imageblob, width=width)
            

        elif ":::" in l:
            continue
        else:
            block.append(l)

    return doc



@dataclass
class IpynbLoader:
    """Load a Jupyter notebook and return its contents as a pydocmaker document."""

    # whether to include input cells as code blocks in the output document
    include_input_cells: bool = True
    source_as_markdown : bool = True
    
    add_cell_numbers: bool = True

    source_language: str = 'python'
    
    plainout_as_raw : bool = False

    # a list of output types to exclude from the output document (e.g. "text/plain", "image/png") (can be Regex patterns)
    exclude_output_type_filters: List[str] = None

    # a list of output types to include in the output document (e.g. "text/plain", "image/png") (can be Regex patterns)
    include_output_type_filters: List[str] = None

    # whether to include metadata in the output document
    include_metadata_in_doc: bool = True

    include_metadata_in_docmeta: bool = True

    # whether to include the notebook version in the output document
    add_nb_version: bool = True

    make_output_blue: bool = True

    verb: bool = False

    def load_notebook(self, file_content:str, file_name="") -> Doc:
        if not isinstance(file_content, dict):
            dc = json.loads(file_content)

        doc = Doc()


        for cell in dc.get("cells", []):
            cell_number = cell.get("execution_count", "N/A")
            if self.verb:
                log.info(f"Parsing cell {cell_number} of type {cell['cell_type']}")

            if self.include_input_cells:
                self.cell_parse_source(cell, doc)

            try:
                self.cell_parse_output(cell, doc)
            except Exception as e:
                s = f"Error parsing output cell: {type(e).__name__}: {e} {util.limit_len(json.dumps(cell, indent=2), 1000)}"
                log.error(s, exc_info=True)
                return doc.add_pre(s, color="red")

        if self.include_metadata_in_doc or self.add_nb_version:
            doc.add_md(f"---")

        if self.include_metadata_in_doc:
            meta = dc.get("metadata", {})
            if meta:
                doc.add_md("Notebook metadata")
                doc.add_pre(json.dumps(meta, indent=2))

        s = ''
        if self.add_nb_version:
            nbformat = dc.get("nbformat", 0)
            nbformat_minor = dc.get("nbformat_minor", 0)
            doc.add_meta({"nbformat": nbformat, "nbformat_minor": nbformat_minor})
            s += f"- Notebook version: {nbformat}.{nbformat_minor}"

        if file_name:
            s += f'\n- Notebook name: "{file_name}"'
        if s:
            doc.add_md(s)

        if self.include_metadata_in_docmeta:
            meta = dc.get("metadata", {})
            if meta:
                doc.add_meta(meta)

                
        return doc


    
    def parse_output_data_part(self, doc:Doc, mimetype:str, data: Any, **kw) -> str:
        """Parse a data dictionary and return its contents as a string."""
        s = _ms(data)

        if s.startswith("<IPython.core") and mimetype == "text/plain":
            return self
        
        if self.verb:
            log.info(f"         data part of {mimetype=} {type(data)=} data={util.limit_len(str(data), 30)}")

        color = 'blue' if self.make_output_blue else None
        if mimetype == "text/plain":
            if self.plainout_as_raw:
                doc.add_text(s)
            else:
                doc.add_pre(s, color=color)
        elif mimetype == "text/markdown":    
            doc.add(clean_md(s))
        elif mimetype == "text/json":    
            doc.add_pre(json.dumps(data, indent=2), color=color)
        elif mimetype == "text/html":
            if s.startswith("<pre") and s.endswith("</pre>"):
                s = get_between_pre(s)
                doc.add_pre(s, color=color)
            elif pandoc_api.can_run_pandoc():
                try:
                    docpart = html2md(s)
                    doc += docpart
                except Exception as e:
                    doc.add_pre(f"Error occurred while converting HTML to Markdown:\nError: {e}\nhtml:\n\n{s}", color="red")
            else:
                doc.add_pre("Unable to convert HTML to markdown or similar, here is the HTML code directly:\n\n" + s, color="red")
        elif mimetype == "image/png" or mimetype == "image/jpeg":
            bts = io.BytesIO(base64.b64decode(s))
            doc.add_image(bts, color=color)
        else:
            raise ValueError(f"Unknown data type: {mimetype=} {data=}")
        
        return self
    
    def _filtoutp(self, key):
        if self.exclude_output_type_filters and any([re.search(pattern, key) for pattern in self.exclude_output_type_filters]):
            return False
        if self.include_output_type_filters and not any([re.search(pattern, key) for pattern in self.include_output_type_filters]):
            return False
        return True
    
    def parse_output_data(self, data: dict, doc:Doc) -> List[str]:
        """Parse a data dictionary and return its contents as a list of strings."""
        
        temp = {k:v for k, v in data.items() if self._filtoutp(k)}
        if self.verb:
            log.info(f"      output data list with n={len(data)} elements and {len(temp)} elements after filtering")
        if len(temp) == 2 and "text/html" in temp and "text/plain" in temp:
            self.parse_output_data_part(doc, "text/html", temp["text/html"])
        else:    
            for k, v in temp.items():
                self.parse_output_data_part(doc, k, v)
        return self
            
    def parse_output_error(self, data: dict, doc:Doc) -> str:
        """Parse an error dictionary and return its contents as a string."""
        ename = data.get("ename", "")
        evalue = data.get("evalue", "")
        traceback = data.get("traceback", [])
        s = "".join(traceback)
        s = re.sub(r'\x1b\[.*?m',r'', s) 
        # s = s.encode('ascii',errors='ignore').decode(encoding='ascii', errors='ignore')
        doc.add_md(f"Execution Error:\n{ename}: {evalue}", color="red")
        doc.add_pre(s, color="red")

        return self

    def cell_parse_output(self, cell: Union[dict, list], doc:Doc) -> list:
        """Parse an output cell and return its contents as a string."""
        
        if isinstance(cell, (list, tuple)):
            for c in cell:
                self.cell_parse_output(c, doc)
            return self
        
        try:

            outputs = cell.get("outputs", [])
            cell_number = cell.get("execution_count", "")

            if self.verb:
                log.info(f"   output for cell {cell_number} with n={len(outputs)} outputs")

            
            if not outputs:
                return self

            
            # if outputs and self.add_cell_numbers:
                # doc.add_md(f"\n\n**Output Cell {cell_number}**\n\n")
            for o in outputs:
                otype = o.get("output_type", "")
                    
                if otype == "stream":
                    s = _ms(o["text"])
                    c = "red" if o["name"] == "stderr" else ""
                    doc.add_pre(s, color=c)
                elif otype == "display_data" or otype == "execute_result":
                    self.parse_output_data(o["data"], doc)
                elif otype == "error":
                    self.parse_output_error(o, doc)
                else:
                    raise ValueError(f"Unknown cell type: {otype}")
                
            return self
        except Exception as e:
            s = f"Error parsing output cell: {type(e).__name__}: {e} {util.limit_len(json.dumps(cell, indent=2), 1000)}"
            log.error(s, exc_info=True)
            doc.add_pre(s, color="red")
            return self

        
    def cell_parse_source(self, cell: dict, doc:Doc) -> str:
        """Parse a source cell and return its contents as a string."""

        cell_number = cell.get("execution_count", "")
        if self.verb :
            log.info(f"   source cell {cell_number} of type {cell['cell_type']}")

        s = _ms(cell["source"])

        if cell["cell_type"] == "code":
            
            if s and self.add_cell_numbers:
                doc.add_md(f"\n\nCell {cell_number}\n\n")
        
            if self.source_as_markdown:
                doc.add_md(f"```{self.source_language}\n{s}\n```")
            else:
                doc.add_pre(s, lang=self.source_language)

        elif cell["cell_type"] == "markdown":
            doc.add(clean_md(s))

        else:
            raise ValueError(f"Unknown cell type: {cell['cell_type']}")
        
        return self
    


def load_notebook(file_path: str, 
    include_input_cells: bool = True,
    source_as_markdown : bool = True,
    add_cell_numbers: bool = True,
    source_language: str = 'python',
    plainout_as_raw : bool = False,
    exclude_output_type_filters: List[str] = None,
    include_output_type_filters: List[str] = None,
    include_metadata_in_doc: bool = True,
    include_metadata_in_docmeta: bool = True,
    add_nb_version: bool = True,
    verb: bool = False, 
    **kw
    ) -> Doc:

    file_name = ""
    if isinstance(file_path, str) and not os.path.isfile(file_path):
        file_content = file_path
    elif isinstance(file_path, dict):
        file_content = file_path
    else:    
        with open(file_path, "r") as f:
            file_content = f.read()
        file_name = file_path
    loader = IpynbLoader(include_input_cells=include_input_cells,
                         source_as_markdown=source_as_markdown,
                         add_cell_numbers=add_cell_numbers,
                         source_language=source_language,
                         plainout_as_raw=plainout_as_raw,
                         exclude_output_type_filters=exclude_output_type_filters,
                         include_output_type_filters=include_output_type_filters,
                         include_metadata_in_doc=include_metadata_in_doc,
                         include_metadata_in_docmeta=include_metadata_in_docmeta,
                         add_nb_version=add_nb_version,
                         verb=verb, **kw)
    
    return loader.load_notebook(file_content, file_name)





if __name__ == "__main__":


    from pathlib import Path

    folder_path = Path('/home/tglaubach/pydocmaker')

    # Get all files recursively (filtering out directories)
    all_files = [f for f in folder_path.rglob('*.ipynb') if f.is_file()]

    for file in all_files:
        doc = load_notebook(file, verb=0, source_language='python')
        
        fn = Path('testout') / Path(file.name)
        print(file)
        print(fn)
        doc.to_json(fn.with_suffix(".json"))
        doc.to_typst(fn.with_suffix(".typ"))
        doc.to_pdf(fn.with_suffix(".pdf"), verb=2)

    # import pydocmaker as pyd

    