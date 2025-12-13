import traceback
import io

import base64
from typing import List

import docx
from docx.shared import Inches, Pt, RGBColor

import tempfile
import os

from pathlib import Path
import zipfile, os, sys
from io import BytesIO

import markdown

try:
    from pydocmaker.backend.baseformatter import BaseFormatter
except Exception as err:
    from .baseformatter import BaseFormatter

can_run_pandoc = lambda : False


try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert, pandoc_convert_file
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert, pandoc_convert_file

try:
    from pydocmaker.backend.ex_html import convert as convert_html
except Exception as err:
    from .ex_html import convert as convert_html



from docx import Document

def _make_output(bts, output_file_or_buffer):
    
    if isinstance(output_file_or_buffer, (str, Path)):
        os.makedirs(os.path.dirname(output_file_or_buffer), exist_ok=True)
        with open(output_file_or_buffer, 'wb') as f:
            f.write(bts)
        return os.path.exists(output_file_or_buffer)
    elif hasattr(output_file_or_buffer, 'write'):
        return output_file_or_buffer.write(bts)
    else:
        return bts
    

def _get_bytes_file_or_buffer(file_path_or_buffer):
    if hasattr(file_path_or_buffer, "read"):
        bts_data = file_path_or_buffer.read()
    elif isinstance(file_path_or_buffer, bytes):
        bts_data = file_path_or_buffer
    else:
        # Read the original DOCX file
        with open(file_path_or_buffer, 'rb') as f:
            bts_data = f.read()
    return bts_data

def docx_update_w32(inpath, outpath=None):
    """
    Update all fields in a Word document using COM automation.

    This function opens a `.docx` file via the Word COM interface,
    updates all fields in the main body and in all story ranges
    (including headers and footers), and then saves the document.
    If `outpath` is provided, the updated document is saved to that
    path; otherwise, the original file is overwritten.

    Args:
        inpath (str): Path to the input Word document (.docx).
        outpath (str, optional): Path to save the updated document.
            If None, the input file is overwritten. Defaults to None.

    Returns:
        None

    Raises:
        pywintypes.com_error: If Word cannot open the document or
            if COM automation fails.

    Example:
        >>> docx_update_w32("C:/docs/report.docx")
        # Updates fields in report.docx and overwrites the file

        >>> docx_update_w32("C:/docs/report.docx", "C:/docs/report_updated.docx")
        # Updates fields and saves to a new file
    """

    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    doc = word.Documents.Open(inpath)
    doc.Fields.Update()

    for story_range in doc.StoryRanges:
        story_range.Fields.Update()
        # Some story ranges have linked ranges (e.g., next header/footer)
        while story_range.NextStoryRange is not None:
            story_range = story_range.NextStoryRange
            story_range.Fields.Update()
    if outpath is None:
        doc.Save()
    else:
        doc.SaveAs(outpath)

    doc.Close()
    word.Quit()


def docx_merge(*files, verb=0) -> bytes:
    """
    Merge multiple Word (.docx) documents into a single document.

    This function uses the `docxcompose.Composer` class to combine
    multiple `.docx` files into one. The merged document is returned
    as raw bytes, suitable for saving to disk or further processing.
    Input files can be provided as paths, file-like objects, or raw
    byte buffers. If the first argument is a list or tuple, it will
    be unpacked as the set of files to merge.

    Args:
        *files (Union[str, bytes, io.BytesIO, list, tuple]):
            One or more `.docx` files to merge. Each file can be a
            filesystem path, a bytes buffer, or a file-like object.
            If a single list or tuple is passed, it will be expanded.
        verb (int, optional): Verbosity level. If nonzero, progress
            messages are printed during merging. Defaults to 0.

    Returns:
        bytes: The merged `.docx` document as a byte string.

    Raises:
        AssertionError: If no files are provided.
        ImportError: If `docxcompose` is not installed.
        Exception: Any error raised during document loading or merging.

    Example:
        >>> merged_bytes = docx_merge("intro.docx", "chapter1.docx", "chapter2.docx")
        >>> with open("book.docx", "wb") as f:
        ...     f.write(merged_bytes)

        >>> files = ["report_part1.docx", "report_part2.docx"]
        >>> merged_bytes = docx_merge(files, verb=1)
        >>> open("report_full.docx", "wb").write(merged_bytes)
    """

    if not locals().get("Composer", globals().get("Composer")):
        print('importing Composer from docxcompose...')
        from docxcompose.composer import Composer

    assert files, f'Must supply files to merge, but given was {files=}!'

    if files and isinstance(files[0], (tuple, list)):
        files = files[0]

    composer = None
    for i, file in enumerate(files):

        bts = _get_bytes_file_or_buffer(file)
        if composer is None:
            if verb:
                print(f'loading template {i}/{len(files)}...')
            composer = Composer(Document(io.BytesIO(bts)))
            if verb: 
                print('compose...')
        else:
            if verb:
                print(f'adding doc {i}/{len(files)}')
                print("load report...")
                print(f'doc={file}')
            doc_b = Document(io.BytesIO(bts))
            if verb:
                print("adding report to template...")
            composer.append(doc_b)
    if verb:
        print("saving merged as bytes...")
        
    with io.BytesIO() as fp:
        composer.save(fp)
        fp.seek(0)
        bts = fp.getvalue()

    if verb:
        print("returning...")

    return bts


# def docx_replace_color(file_path_or_buffer, output_file_or_buffer=None, color_to_replace=(0, 0, 0), new_color=(0, 112, 192), do_replace_default_color=True):

#     docx_data = _get_bytes_file_or_buffer(file_path_or_buffer)
        
#     # Create a temporary zip file from the DOCX data
#     doc = Document(BytesIO(docx_data))

#     if isinstance(color_to_replace, (tuple, list)):
#         color_to_replace = RGBColor(*color_to_replace)
    
#     if isinstance(new_color, (tuple, list)):
#         new_color = RGBColor(*new_color)
    

#     # Iterate through all paragraphs and runs
#     for para in doc.paragraphs:
#         for run in para.runs:
#             # Check if the run has a font color set to black
#             if (run.font.color is None and do_replace_default_color) or run.font.color.rgb == color_to_replace:
#                 run.font.color.rgb = new_color  # set to navyblue

#     with BytesIO() as fp:
#         doc.save(fp)
#         bts = fp.getvalue()

#     return _make_output(bts, output_file_or_buffer)



def docx_replace_fields(file_path_or_buffer, replace_dict, output_file_or_buffer=None):
    """
    replace all MergeFields of a DOCX file with given text in form of a dict.
    
    Adding MergeFields In Word:
        - Go to Insert → Quick Parts → Field → MergeField.
    - Give it a name like FirstName, Date, etc.

    This function reads a DOCX file, searches for specific MergeFields and replaces them. 
    Writes the modified content back into a new DOCX file or returns it as bytes.
    Args:
        file_path_or_buffer (str, filelike): Path to the input DOCX file to be modified
        replace_dict (dict): Dictionary mapping strings to be replaced (keys) to their replacement values (values)
        output_file_or_buffer (str, Path, or filelike object, optional): Path to save the modified DOCX file, or a buffer object to write to. If None, returns the modified DOCX content as bytes.
    Returns:
        bool or bytes: If output_file_or_buffer is a path, returns True if successful. If output_file_or_buffer is a buffer or None, returns the modified DOCX content as bytes.
    """
        
    if not locals().get("MailMerge", globals().get("MailMerge")):
        from mailmerge import MailMerge

    bts = _get_bytes_file_or_buffer(file_path_or_buffer)
    outbuf = BytesIO()

    with MailMerge(BytesIO(bts)) as document:
        # fields = document.get_merge_fields()

        document.merge(**replace_dict)
        document.write(outbuf)

    return _make_output(outbuf.getvalue(), output_file_or_buffer)


def docx_replace_keywords(file_path_or_buffer, replace_dict, output_file_or_buffer=None):
    """
    Edit raw XML content of a DOCX file by replacing specified strings using python docx.

    This function reads a DOCX file, searches for specific strings in all XML files 
    inside the archive, replaces them with new values,
    and writes the modified content back into a new DOCX file or returns it as bytes.
    Args:
        file_path_or_buffer (str, filelike): Path to the input DOCX file to be modified
        replace_dict (dict): Dictionary mapping strings to be replaced (keys) to their replacement values (values)
        output_file_or_buffer (str, Path, or filelike object, optional): Path to save the modified DOCX file, or a buffer object to write to. If None, returns the modified DOCX content as bytes.
    Returns:
        bool or bytes: If output_file_or_buffer is a path, returns True if successful. If output_file_or_buffer is a buffer or None, returns the modified DOCX content as bytes.
    """
    
    docx_data = _get_bytes_file_or_buffer(file_path_or_buffer)
        
    # Create a temporary zip file from the DOCX data
    doc = Document(BytesIO(docx_data))

    for p in doc.paragraphs:
        for key_to_replace, new_value in replace_dict.items():
            p.text = p.text.replace(str(key_to_replace), str(new_value))
    
    with BytesIO() as fp:
        doc.save(fp)
        bts = fp.getvalue()

    return _make_output(bts, output_file_or_buffer)



def docx_replace_keywords_raw(file_path_or_buffer, replace_dict, output_file_or_buffer=None):
    """
    Edit raw XML content of a DOCX file by replacing specified strings in all XML files within the document.

    This function reads a DOCX file, extracts its contents (which are stored as a ZIP archive),
    searches for specific strings in all XML files inside the archive, replaces them with new values,
    and writes the modified content back into a new DOCX file or returns it as bytes.
    Args:
        file_path_or_buffer (str, filelike): Path to the input DOCX file to be modified
        replace_dict (dict): Dictionary mapping strings to be replaced (keys) to their replacement values (values)
        output_file_or_buffer (str, Path, or filelike object, optional): Path to save the modified DOCX file, or a buffer object to write to. If None, returns the modified DOCX content as bytes.
    Returns:
        bool or bytes: If output_file_or_buffer is a path, returns True if successful. If output_file_or_buffer is a buffer or None, returns the modified DOCX content as bytes.
    """
    
    docx_data = _get_bytes_file_or_buffer(file_path_or_buffer)
        
    # Create a temporary zip file from the DOCX data
    zip_buffer = BytesIO(docx_data)
    with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
        # Get all file names in the archive
        file_list = zip_file.namelist()

        output_buffer = BytesIO()
        with zipfile.ZipFile(output_buffer, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            # Process each file in the original zip
            for filename in file_list:
                # Read the file content
                content = zip_file.read(filename)
                
                for key_to_replace, new_value in replace_dict.items():
                    content = content.replace(key_to_replace.encode('utf-8'), new_value.encode('utf-8'))
                
                # Add file to new zip
                new_zip.writestr(filename, content)
            # Create a new zip file in memory
        bts = output_buffer.getvalue()

    return _make_output(bts, output_file_or_buffer)


def blue(run):
    run.font.color.rgb = docx.shared.RGBColor(0, 0, 255)

def red(run):
    run.font.color.rgb = docx.shared.RGBColor(255, 0, 0)

def convert_pandoc(doc:List[dict]) -> bytes:

    with tempfile.TemporaryDirectory() as temp_dir:
        html_file_path = os.path.join(temp_dir, 'temp.html')
        docx_file_path = os.path.join(temp_dir, 'temp.docx')

        with open(html_file_path, 'w', encoding='utf-8') as fp:
            fp.write(convert_html(doc))
        
        pandoc_convert_file(html_file_path, docx_file_path)
        with open(docx_file_path, 'rb') as fp:
            return fp.read()
        
def convert(doc:List[dict]) -> bytes:

    if can_run_pandoc():
        return convert_pandoc(doc)
    else:
        renderer = docx_renderer()
        renderer.digest(doc)
        return renderer.doc_to_bytes()

class docx_renderer(BaseFormatter):
    def __init__(self, template_path:str=None, make_blue=False) -> None:
        self.d = docx.Document(template_path)
        self.make_blue = make_blue

    def add_paragraph(self, newtext, *args, **kwargs):
        new_paragraph = self.d.add_paragraph(newtext, *args, **kwargs)
        if self.make_blue:
            for r in new_paragraph.runs:
                blue(r)
        return new_paragraph
    
    def add_run(self, text, *args, **kwargs):
        if not self.d.paragraphs:
            self.add_paragraph('')

        last_paragraph = self.d.paragraphs[-1]
        
        if not last_paragraph.runs:
            last_run = last_paragraph.add_run(text)
        else:
            last_run = last_paragraph.runs[-1]
            last_run.add_text(text)
            
        if self.make_blue:
            blue(last_run)
        return last_run
        
    def digest_text(self, children, *args, **kwargs):
        return self.add_paragraph(children)
    

    def digest_str(self, children, *args, **kwargs):
        return self.add_run(children)

    def digest_line(self, children, *args, **kwargs):
        return self.add_run(children + '\n')
    
    def digest_markdown(self, children, *args, **kwargs):
        return self.add_paragraph(children, style='Normal')
        
    def digest_verbatim(self, children, *args, **kwargs):
        new_run = self.add_run(children)
        new_run.font.name = 'Courier New'  # Or any other monospace font
        new_run.font.size = docx.shared.Pt(8)  # Adjust font size as needed
        return new_run

    def digest_latex(self, children, *args, **kwargs):
        new_run = self.add_run(children)
        new_run.font.name = 'Courier New'  # Or any other monospace font
        new_run.font.size = docx.shared.Pt(8)  # Adjust font size as needed
        return new_run


    def handle_error(self, err, el=None) -> list:
        if isinstance(err, BaseException):
            traceback.print_exc(limit=5)
            err = '\n'.join(traceback.format_exception(type(err), value=err, tb=err.__traceback__, limit=5))

        new_run = self.add_run(err)
        new_run.font.name = 'Courier New'  # Or any other monospace font
        new_run.font.size = docx.shared.Pt(8)  # Adjust font size as needed
        red(new_run)
        return new_run


    def digest_iterator(self, children, *args, **kwargs):
        if children:
            return [self.digest(val, *args, **kwargs) for val in children]
        return []

    def digest_table(self, children=None, **kwargs) -> str:
        self.handle_error(NotImplementedError(f'exporter of type {type(self)} can not handle tables'))
    
    def digest_image(self, children, *args, **kwargs):

        image_width = Inches(max(1, kwargs.get('width', 0.8)*5))
        image_caption = kwargs.get('caption', '')
        image_blob = kwargs.get('imageblob', '')

        assert image_blob, 'no image data given!'

        btsb64 = image_blob.split(',')[-1]

        # Decode the base64 image
        img_bytes = base64.b64decode(btsb64)

        # Create an image stream from the bytes
        image_stream = io.BytesIO(img_bytes)
        
        picture = self.d.add_picture(image_stream, width=image_width)
        # picture.width = image_width  # Ensure fixed width
        # picture.height = None  # Adjust height automatically
        picture.alignment = 1

        run = self.add_paragraph(image_caption)
        # run.style = 'Caption'  # Apply the 'Caption' style for formatting

        return run

    def format(self, *args, **kwargs):
        raise NotImplementedError('Can not format a docx document directly')
    

    def doc_to_bytes(self):
        with io.BytesIO() as fp:
            self.d.save(fp)
            fp.seek(0)
            return fp.read()

    def save(self, filepath):
        self.d.save(filepath)
