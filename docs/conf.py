# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html


import os
import sys
import toml
from pathlib import Path

srcdir = str(Path(os.path.join(os.path.dirname(__file__), '../src')).resolve())

print(srcdir)
sys.path.insert(0, srcdir)

# Path to the __init__.py file
init_path = os.path.join(os.path.dirname(__file__), '../src/pydocmaker/__init__.py')

# Read the __init__.py file and extract the version
with open(init_path, 'r', encoding='utf-8') as f:
    init_content = f.readlines()
    version_line = next(line for line in init_content if line.startswith('__version__'))
    version = version_line.split('=')[-1].strip().strip('"')



# Path to the pyproject.toml file
pyproject_path = os.path.join(os.path.dirname(__file__), '../pyproject.toml')

# Load the pyproject.toml file
with open(pyproject_path, 'r', encoding='utf-8') as f:
    pyproject_data = toml.load(f)

# Extract project metadata
project = pyproject_data['project']['name']
project_description = pyproject_data['project'].get('description', '')
project_authors = pyproject_data['project'].get('authors', [])

# Convert authors to a string format
author = ', '.join([author['name'] for author in project_authors])

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# -- Project information -----------------------------------------------------
copyright = f'2025, {author}'
release = version


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    # 'sphinx.ext.autodoc',       # For automatic documentation generation
    'autoapi.extension',       # For automatic documentation generation
    'sphinx.ext.napoleon',      # For Google-style and NumPy-style docstrings
    'myst_parser',              # For parsing Markdown files
    'versionwarning.extension',
    "nbsphinx"
]

source_suffix = {
    '.rst': 'restructuredtext',
    '.txt': 'markdown',
    '.md': 'markdown',
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'requirements.txt', 'any_path_to_my*']


autoapi_dirs = [
    srcdir
]

autoapi_ignore = ['*/tests/*', '*/examples/*']

autoapi_add_toctree_entry = False

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'classic'
# html_theme = 'pydata_sphinx_theme'
html_theme = "sphinx_rtd_theme"

# html_static_path = ['_static']

# -- Additional HTML Theme Options ------------------------------------------
# html_theme_options = {
#     'sidebarwidth': '320px',  # Set the sidebar width
# }

#nbsphinx_allow_errors = True
nbsphinx_execute = 'never'

# html_sidebars = {
#     'index': [
#         'globaltoc.html',  # Include the global TOC in the sidebar for the index page
#         'relations.html',  # Provides links to the previous and next documents
#         'sourcelink.html', # Provides a link to the source of this document
#         'searchbox.html',  # Displays a search box in the sidebar
#     ],
# }

# # -- MyST Parser Configuration ----------------------------------------------
# myst_heading_anchors = 3  # Add anchors to headings for linking

html_theme_options = {
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

html_sidebars = {
    '**': [
        'globaltoc.html',
        'relations.html',
        'sourcelink.html',
        'searchbox.html',
    ]
}