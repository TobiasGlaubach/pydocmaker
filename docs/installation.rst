.. _installation:

Installation
------------

Install via:

.. code-block:: bash

   pip install pydocmaker

**NOTE**: This will actually install the package will all subpackages, most of which are not needed, but kept for compatibility reasons. 
If you want to install only the core package, you can do so via manually downloading the source , commenting out all the optional 
dependencies in requirements.txt, and installing via:

.. code-block:: bash

   pip install -e .



Install Optional Requirements
-----------------------------

Optional Requirement ``pandoc``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to get all functionality, ``pandoc`` needs to be available. Please follow the recommended installation steps on the software project's webpage. For convenience, the minimal installation is listed here:

On Linux (Debian/Ubuntu), install via:

.. code-block:: bash

   sudo apt update
   sudo apt install pandoc

On MacOS:

.. code-block:: bash

   brew install pandoc

On Windows:

.. code-block:: bash

   winget install JohnMacFarlane.Pandoc


Optional Requirement ``Latex``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to get all functionality, a LaTeX compiler needs to be available. Please follow the recommended installation steps on the webpage. For convenience, the minimal installation is listed here:

On Linux (Debian/Ubuntu), install via:

.. code-block:: bash

   sudo apt update
   sudo apt install texlive-full

On MacOS:

.. code-block:: bash

   brew install --cask mactex

On Windows:

.. code-block:: bash

   winget install MiKTeX.MiKTeX


Optional Requirement for DOCX either ``libreoffice`` or ``win32com``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some DOCX functionality requires either Microsoft Windows and Microsoft Word and the ``win32com`` library or ``libreoffice`` available.


Installing ``pywin32`` (Windows only)
"""""""""""""""""""""""""""""""""""""""

Install via:

.. code-block:: bash

   pip install pywin32


Installing ``libreoffice``
"""""""""""""""""""""""""""

On a Linux (Debian/Ubuntu) system, install via:

.. code-block:: bash

   sudo apt update
   sudo apt-get install libreoffice

On MacOS:

.. code-block:: bash

   brew install --cask libreoffice

On Windows:

.. code-block:: bash

   winget install TheDocumentFoundation.LibreOffice

