import base64
import io
import os
import re
from pathlib import Path
import json
import shutil
import subprocess
import time
import traceback
import sys

import tempfile
import shutil
import warnings
import zipfile

from pydocmaker.util import log


# Define a function to test if pdflatex, lualatex, or xelatex is installed
def test_latex_compiler(compiler):
    try:
        subprocess.run([compiler, '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

# Define a global variable to store the latex compiler
_latex_compiler = None

_allowed_compilers = 'tectonic pdflatex lualatex xelatex'.split()

#: latex source patterns that reference external files (group 1 = the reference)
_LATEX_FILE_REF_RES = (
    re.compile(r'\\includegraphics\*?(?:\[[^\]]*\])?\{([^{}]+)\}'),
    re.compile(r'\\(?:input|include|lstinputlisting|bibliography|addbibresource)\{([^{}]+)\}'),
)


def _copy_missing_file_refs(input_latex_text, output_dir):
    """Copy files referenced by the latex source into the compile folder.

    Document content converted from markdown may reference local files by
    their bare name (``\\includegraphics{icon.png}``). The latex compiler runs
    inside the (temporary) output folder, so files that exist next to the
    caller (in the working directory) would not be found. This copies every
    referenced file that is not already in the output folder from the
    working directory so the references resolve.

    Args:
        input_latex_text (str | bytes): the latex source to scan.
        output_dir (str): the compile folder (copy destination).
    """
    if isinstance(input_latex_text, bytes):
        try:
            input_latex_text = input_latex_text.decode('utf-8', 'replace')
        except Exception:
            return
    if not isinstance(input_latex_text, str):
        return
    refs = []
    for pattern in _LATEX_FILE_REF_RES:
        refs += pattern.findall(input_latex_text)
    for ref in dict.fromkeys(r.strip() for r in refs):
        if not ref or ref.startswith('http') or '\\' in ref or '{{' in ref:
            continue
        dst = os.path.join(output_dir, ref)
        if os.path.exists(dst):
            continue  # already provided with the attachments
        src = ref if os.path.isabs(ref) else os.path.join(os.getcwd(), ref)
        if not os.path.isfile(src):
            continue
        parent = os.path.dirname(dst)
        if parent:
            os.makedirs(parent, exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except OSError as err:
            log.warning(f'could not copy referenced file {src!r} into the '
                        f'latex compile folder: {err}')


def config_latex_compiler_scan():
    return [c for c in _allowed_compilers if test_latex_compiler(c)]

# Define a function to test which latex compiler is installed
def config_latex_compiler_testset(verb=1):
    global _latex_compiler
    if verb:
        log.info('testing available latex compilers')
    _latex_compiler = next((c for c in _allowed_compilers if test_latex_compiler(c)), '')
    if verb:
        log.info(f'DONE testing latex compilers: found compiler="{_latex_compiler}"')


def config_latex_compiler_set(new_latex_compiler_str):
    assert test_latex_compiler(new_latex_compiler_str), f'The given Latex Compiler "{new_latex_compiler_str}" was not found in PATH'
    global _latex_compiler
    _latex_compiler = new_latex_compiler_str
    return _latex_compiler

def config_latex_compiler_get(verb=0):
    global _latex_compiler
    if _latex_compiler is None:
        if verb: log.info("getting latex compiler for the first time")
        config_latex_compiler_testset(verb=verb)
        if verb: log.info(f"found  {_latex_compiler=}")
    ret = _latex_compiler # copy
    return ret

def setup():
    config_latex_compiler_testset()                    



def zip_folder(folder_path):
    # Create a bytes buffer
    zip_buffer = io.BytesIO()

    # Create a zip file in the buffer
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Walk through the directory
        for foldername, subfolders, filenames in os.walk(folder_path):
            for filename in filenames:
                # Create complete filepath
                filepath = os.path.join(foldername, filename)
                # Add file to zip
                zipf.write(filepath, os.path.relpath(filepath, folder_path))

    # Reset the buffer's file pointer to the beginning
    zip_buffer.seek(0)
    return zip_buffer.read()


def _procrun(args, verb=0, ignore_error=False, **kwargs):
    if verb > 1: log.info(args)

    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout, stderr = process.communicate()

    if stdout and verb > 2:
        log.info(stdout.decode())

    if stderr:
        stderr = stderr.decode()
        if 'warn' in stderr.lower() or ignore_error:
            log.warning(stderr)
            # warnings.warn(stderr)
        elif not ignore_error:
            raise Exception(stderr.decode())
        
    if process.returncode != 0:
        s = f"Command {' '.join(args)} returned non-zero exit status {process.returncode=}"
        if ignore_error:
            if stderr:
                if hasattr(stderr, 'decode'):
                    stderr = stderr.decode()
                if hasattr(stdout, 'decode'):
                    stdout = stdout.decode()
                log.warning(f'{process.returncode=} from {args=}.')
                log.warning(f'stderr follows on next line')
                log.warning(str(stderr))
                log.warning(f'stdout follows on next line')
                log.warning(str(stdout))
            # warnings.warn(s)
        else:
            raise Exception(s)
    return process.returncode

# def _get_platform_tempdir():
#     import platform
#     # HACK: Stupid windows sometimes has a tilde in the user path and PDFlatex does not like this
#     # therefore we need to expand the user name using ctypes. 
#     # NOTE: os.path.expanduser(tempfile.tempdir) does not work for this either
#     if platform.system().lower() == "windows":
#         # Use the Windows API to get the full long path (remove tilde)
#         import ctypes
#         buf_size = ctypes.windll.kernel32.GetLongPathNameW(tempfile.gettempdir(), None, 0)
#         if buf_size == 0:
#             return tempfile.gettempdir()  # In case GetLongPathNameW fails, return original path
#         buffer = ctypes.create_unicode_buffer(buf_size)
#         ctypes.windll.kernel32.GetLongPathNameW(tempfile.gettempdir(), buffer, buf_size)
#         return buffer.value
#     else:
#         # For Unix-like systems (Linux, macOS), plug in None to indicate to use 
#         return None
    

def make_pdf_from_tex(input_latex_text, attachments_dc=None, docname='', out_format='pdf', base_dir=None, latex_compiler=None, n_times_make=None, verb=0, ignore_error=False) -> bytes:
    """Converts a LaTeX document to a PDF or a ZIP file containing the PDF and all attachments.

    Args:
        input_latex_text (str or bytes): The LaTeX document as a string or bytes.
        attachments_dc (dict, optional): A dictionary of attachments to include in the ZIP file.
            The keys are the filenames and the values are the file contents as bytes or strings.
            Defaults to an empty dictionary.
        docname (str, optional): The name of the output document. Defaults to a timestamp.
        out_format (str, optional): The format of the output. Either 'pdf' or 'zip'. Defaults to 'pdf'.
        base_dir (str, optional): The directory to use as the base directory for the temporary directory.
            Defaults to the system's default temporary directory.
        latex_compiler (str, optional): The LaTeX compiler to use. Either 'pdflatex', 'lualatex', 'xelatex', or 'pandoc'.
            If not specified, the function will try to use 'pandoc', 'pdflatex', 'lualatex', or 'xelatex' in that order.
        n_times_make (int, optional): The number of times to run the LaTeX compiler. Defaults to 1 for pandoc and 3 for al others.
        verb (int, optional): The verbosity level. If greater than 0, the function will print debug information. Defaults to 0.
        ignore_error (bool, optional): Whether to ignore errors during the LaTeX compilation. Defaults to False.

    Returns:
        bytes: The PDF document as bytes, or a ZIP file containing the PDF and all attachments as bytes.

    Raises:
        ValueError: If the input_latex_text is not a string or bytes, or if the docname is not a string.
        ValueError: If the latex_compiler is not 'pdflatex', 'lualatex', 'xelatex', or 'pandoc'.
        ValueError: If the out_format is not 'pdf' or 'zip'.
        AssertionError: If the attachments_dc contains invalid keys or values.
    """
     
    try:
            
        if attachments_dc is None:
            attachments_dc = {}

        if isinstance(input_latex_text, bytes):
            input_latex_text = input_latex_text.decode('utf-8')
        
        if not docname:
            docname = f'{time.time():.0f}_mydocument'

        assert isinstance(input_latex_text, str), f'input_latex_text must be string type but is type="{type(input_latex_text)}"'
        assert isinstance(docname, str), f'docname must be string type but is type="{type(docname)}"'


        if latex_compiler is None:
            
            latex_compiler = config_latex_compiler_get()
        else:
            assert test_latex_compiler(latex_compiler), f'The given Latex Compiler "{latex_compiler}" was not found in PATH'

        assert latex_compiler, 'No latex compiler found on the system'
        
        if n_times_make is None:
            n_times_make = 1 if latex_compiler == 'pandoc' else 3
            
        if verb: log.info(f'Running with {latex_compiler=}')

        if r"\providecommand{\tightlist}" not in input_latex_text and r"\tightlist" in input_latex_text:
            if verb: log.warning(r'found "\tightlist" in tex source but no "\providecommand{\tightlist}" will replace all occurances')
            input_latex_text = input_latex_text.replace(r"\tightlist", "")


        # open a temp folder at base dir which will be deleted after completion
        with tempfile.TemporaryDirectory(dir=base_dir) as od:
            output_dir = Path(od).resolve() # should remove tilde
            out_file_tex = f'{docname}.tex'
            out_path_tex = os.path.join(output_dir, out_file_tex)
            out_path_pdf = os.path.join(output_dir, f'{docname}.pdf')

            if verb: log.info(f'Writing file: {out_file_tex}')
            # write the tex file to the folder
            with open(out_path_tex, 'w') as fp:
                fp.write(input_latex_text)
        
            # write all attachments to the folder
            for filename, file_content_bytes in attachments_dc.items():
                assert isinstance(filename, str) and isinstance(file_content_bytes, (bytes, str)), f'attachments_dc must only contain path:bytes pairs but given was {filename=} with content type {type(file_content_bytes)}'
                if verb: log.info(f'Writing file: {filename}')
                out_path = os.path.join(output_dir, filename)
                # attachment keys may contain subpaths (e.g. "images/logo.png")
                if os.path.dirname(filename):
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)

                with open(out_path, 'wb' if isinstance(file_content_bytes, bytes) else 'w') as fp:
                    fp.write(file_content_bytes)

            # bring along files that are referenced by the source but are not
            # part of the attachments (e.g. local images referenced by
            # markdown-converted document content)
            _copy_missing_file_refs(input_latex_text, output_dir)

            # Convert the TeX document to a PDF using the selected latex compiler

            if latex_compiler == 'pandoc':
                _procrun(['pandoc', '-o', out_path_pdf, out_path_tex], verb=verb, ignore_error=ignore_error,  cwd=output_dir)
            elif latex_compiler in ["tectonic"]:
                chatter =  "default" if verb else "minimal"
                _procrun([latex_compiler, "--chatter", chatter, "--reruns", str(n_times_make), out_file_tex], verb=verb, ignore_error=ignore_error, cwd=output_dir)
            elif latex_compiler in _allowed_compilers:
                for i in range(1, n_times_make+1):
                    ir = ignore_error or (i < n_times_make) # only assure the last run did not fail if requested
                    if verb: log.info(f'Compilation run {i}')
                    _procrun([latex_compiler, "-interaction", "nonstopmode", out_file_tex], verb=verb, ignore_error=ir, cwd=output_dir)
            else:
                raise ValueError(f'Given was {latex_compiler=}. But need to specify a valid latex compiler! allowed are {_allowed_compilers!r}, or "pandoc".')
        
            if out_format.lower() == 'zip':
                if verb: log.info(f'Zipping folder to bytes: {output_dir}')
                return zip_folder(output_dir)
            elif out_format.lower() == 'pdf':
                if verb: log.info(f'Reading PDF to bytes: {output_dir}')
                logfile = os.path.join(output_dir, f'{docname}.log')

                showlog = False
                if not os.path.exists(out_path_pdf) and verb > 2:
                    showlog = True
                if verb > 3:
                    showlog = True
                if not os.path.exists(logfile):
                    showlog = False
                if showlog:
                    with open(logfile, 'r') as fp:
                        log.warning(f"{'='*100}\nPDF FILE NOT FOUND! HERE IS THE LOG\n{'_'*20}\n{fp.read()}\n{'='*100}")
                        
                if not os.path.exists(out_path_pdf):
                    info_string = f"The file {out_path_pdf} does not exist."
                    if os.path.exists(output_dir):
                        files_in_dir = os.listdir(output_dir)
                        sep = '\n-'
                        info_string += f"\The directory '{output_dir}' exists and contains the following files:\n{sep.join(files_in_dir)}"
                    else:
                        info_string += f"\nThe directory {output_dir} does not exist either."
                    if os.path.exists(logfile):
                        with open(logfile, 'r') as fp:
                            s = fp.read()
                            info_string += '\nHere are the first and last 500 chars from the log file:\n---------\n' + s[:500] + '\n (...) \n' + s[-500:]
                            if verb and os.environ.get('PYDOCMAKER_TESTFULL'):
                                s2 = (('>'*100) + '\n')*10
                                s2 += s
                                s2 += (('<'*100) + '\n')*10
                                log.error(s2)

                    info_string += '\n To debug the latex code you can have a look at doc.to_tex() or doc.show("tex") directly to see the source. You can also call doc.to_pdf("myfolder/mydoc.zip") to get the full folder directly'

                    raise FileNotFoundError(info_string)
                
                with open(out_path_pdf, 'rb') as fp:
                    bts = fp.read()
                return bts
            else:
                raise ValueError(f'Unknown format requested: {out_format}. Allowed are only "zip" or "pdf"')


    except Exception as err:
        try:
            from pydocmaker import util
            err.context = util.get_inp_context('main.tex', input = {'main.tex': input_latex_text, **(attachments_dc or {})})    
        except Exception as err:
            err.context = {}
        
        raise

    