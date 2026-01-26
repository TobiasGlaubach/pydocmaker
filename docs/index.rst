.. devicelib documentation master file, created by
   sphinx-quickstart on Wed Jan 14 13:17:17 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

MPIfR `devicelib` Documentation
====================================

.. .. include:: ../README.md


.. image:: ../icon.png
   :alt: Icon


a minimal python document maker to create reports in the following formats:

- `pdf`: PDF
- `md`: Markdown
- `html`: HTML
- `json`: JSON
- `docx`:: Word docx
- `textile`: Textile Markup language (with images as attachments)
- `ipynb`: Jupyter/ IPython Notebooks
- `tex`: Latex Documents (with external images)
- `redmine`: Textile Markup language ready for uplaod to Redmine 


Written in pure python 

**NOTE:** some functions will try to call pandoc and fall back if not found.

**NOTE:** exporting PDFs need a latex compiler such as pdflatex, lualatex, xelatex

Install:
--------

Install via:

.. code-block:: bash

   pip install pydocmaker


Install Optional Requirement `pandoc`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to get all functionality ``pandoc`` needs to be available. Please follow the recommended installation steps on the software projects webpage. For convenience the minimal installation is listed here:

On Linux (Debian/Ubuntu) install via:

.. code-block:: bash

   sudo apt update
   sudo apt install pandoc

On MacOS:

.. code-block:: bash

   brew install pandoc

On Windows:

.. code-block:: bash

   winget install JohnMacFarlane.Pandoc


Install Optional Requirement `Latex`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to get all functionality a LaTeX compiler needs to be available. Please follow the recommended installation steps on the webpage. For convenience the minimal installation is listed here:

On Linux (Debian/Ubuntu) install via:

.. code-block:: bash

   sudo apt update
   sudo apt install texlive-latex-base

On MacOS:

.. code-block:: bash

   brew install --cask mactex

On Windows:

.. code-block:: bash

   winget install MiKTeX.MiKTeX


TLDR:
-----

This is a very small example if you're lazy ;-)

.. code-block:: python

    doc = pyd.Doc() # basic doc where we always append to the end
    doc.add('dummy text') # adds raw text

    # this is how to add parts to the document
    doc.add_pre('this will be shown as preformatted') # preformatted
    doc.add_md('This is some *fancy* `markdown` **text**') # markdown
    doc.add_tex(r'\textbf{Hello, LaTeX!}') # latex
    colors = ['blue', 'red', 'green']
    rows = [[pyd.mk_md(f'Row {irow} Col {icol}', color=c) for icol, c in enumerate(colors)] for irow in range(3)]
    doc.add_table(rows, header=colors)
    # this is how to add an image from link
    doc.add_image("https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png", caption='', children='', width=0.8)

    doc.show()



Getting Started:
----------------


.. toctree::
   :maxdepth: 4
   
   s01_getting_started

Examples
========

.. toctree::
    :maxdepth: 4
    :glob:
    :caption: Examples

    s02_word_examples
    
    s03_template_examples

    s04_redmine_examples

    s05_detailed_examples


API Reference
-------------


.. toctree::
   :maxdepth: 3

   pydocmaker



pydocmaker (convenience functions)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: pydocmaker
   :members:
   :undoc-members:
   :show-inheritance:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`