TL;DR; Example
===============

This is a very small example if you're lazy ;-)

.. code-block:: python
    
    import pydocmaker as pyd
    
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



Configuring Options:
====================

All configurable options for this package are in ``pydocmaker.options``. They are always callable 
functions with "*_get", "*_set", "*_scan" etc. 

.. code-block:: python

    import pydocmaker as pyd

    pyd.options.pandoc_allowed_set(False)
    print(pyd.options.pandoc_allowed_get())

    pyd.options.pdf_engine_set('typst') # default
    print(pyd.options.pdf_engine_get())


