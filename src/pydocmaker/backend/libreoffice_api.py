import shutil
import subprocess
from pathlib import Path
import os
import threading
import shlex

allow_libreoffice = True

_is_libreoffice_installed = None

_done = threading.Event()
_testing_thread = None

_libreoffice_path = "libreoffice"

PATH_OPTIONS= [
    "C:\Program Files\LibreOffice\program\soffice.exe",
    "C:\Program Files (x86)\LibreOffice\soffice.exe",
    "soffice.exe"
    "libreoffice.exe",
]

def config_libreoffice_path_set(path):
    """sets a new path for the libreoffice executeable (use None to force the backend to try to resolve it anew)

    Returns:
        str|None: the newly set path for the libreoffice executeable or None, if it has not been resolved yet.
    """
    global _libreoffice_path
    _libreoffice_path = path
    return _libreoffice_path

def config_libreoffice_path_get():
    """gets the currently set path for the libreoffice executeable or None, if it has not been resolved yet.

    Returns:
        str|None: the currently set path for the libreoffice executeable or None, if it has not been resolved yet.
    """
    s = _libreoffice_path
    return s


def _test_is_libreoffice_installed():
    global _libreoffice_path

    if os.name == 'nt':  # Check if the OS is Windows
        _libreoffice_path = next((p for p in PATH_OPTIONS if os.path.exists(p)), None)
        return not _libreoffice_path is None

    for option in ["libreoffice", "soffice"]:
        if shutil.which(option):
            
            try:
                subprocess.run(
                    [option, "--version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=True,
                )
                _libreoffice_path = option
                return True
            except Exception:
                continue
    return False


def _test_is_libreoffice_installed_threadfun():
    global _available
    try:
        _available = _test_is_libreoffice_installed()   # may take up to 5 seconds
    except Exception:
        _available = False
    finally:
        _done.set()

# load in the background so the user will not have to wait
_testing_thread = threading.Thread(target=_test_is_libreoffice_installed_threadfun, daemon=True)
_testing_thread.start()


def can_use_libreoffice(force_reload=False):
    if not allow_libreoffice:
        return False
    
    global _is_libreoffice_installed, _testing_thread
    if _testing_thread and _testing_thread.is_alive():
        _done.wait()

    if _is_libreoffice_installed is None or force_reload:
         _is_libreoffice_installed = _test_is_libreoffice_installed()
    r = _is_libreoffice_installed # copy
    return r




def to_pdf(input_file, output_pdf):
    input_file = Path(input_file).resolve()
    output_pdf = Path(output_pdf).resolve()
    if _libreoffice_path is None:
        _test_is_libreoffice_installed()

    if _libreoffice_path is None:
        raise ValueError("No Libreoffice installation found on the system! You can hack this, by calling config_libreoffice_path_set(your_path) before using this function")
    cmd = [
            _libreoffice_path,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_pdf.parent),
            str(input_file),
        ]
    
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    generated = output_pdf.parent / (input_file.stem + ".pdf")
    generated.rename(output_pdf)
    if not output_pdf.exists():
        raise FileNotFoundError(f"File {output_pdf} was not created successfully")
    
