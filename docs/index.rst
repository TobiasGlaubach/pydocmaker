.. _index:



``pydocmaker`` Simple Document Creation in Python 
=================================================

.. image:: ../icon.png
   :alt: Icon
   :align: center

a minimal python document maker to create reports in the following formats:

- ``pdf``: PDF
- ``md``: Markdown
- ``html``: HTML
- ``json``: JSON
- ``docx``: Word docx
- ``textile``: Textile Markup language (with images as attachments)
- ``typst``: Typst Documents (with inline images)
- ``ipynb``: Jupyter/ IPython Notebooks
- ``tex``: Latex Documents (with external images)
- ``redmine``: Textile Markup language ready for upload to Redmine 

Written purely in python, but with **optional** external non python dependencies.

**NOTES:** 
   - some functions will try to call pandoc and fall back if not found.
   - exporting PDFs works with typst under the hood if its installed. Else a latex compiler such as pdflatex, lualatex, xelatex is needed
   - a subset of functions when working with docx documents (such as creating PDFs or updating references) need the ``win32com`` library and Microsoft Word installed in order to work.

**Install** via:

.. code-block:: bash

   pip install pydocmaker

**Optional requirements**: Some features only work with optional requirements such as ``pandoc``, LaTeX, ``pywin32com``, and ``libreoffice`` for details see :ref:`installation`.

Links
-----

.. toctree::
   :maxdepth: 2
   :glob:
   
   index
   installation
   tldr
   examples
..    high_level


.. toctree::
   :maxdepth: 3
   :caption: API-Reference

   pydocmaker



Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`