.. _installation:

Installation
------------

Install via:

.. code-block:: bash

   pip install pydocmaker



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
   sudo apt install texlive-latex-base

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

