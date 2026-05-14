Data Model
==========

The underlying data model for ``pydocmaker`` is a list of dictionaries. Each dictionary represents a document element with a specific type (``typ``) and associated properties.

Element Properties
------------------

Most elements share a common set of properties:

*   ``typ``: The string identifier of the element type (e.g., "markdown", "image").
*   ``children``: The main content of the element. For text-based types, this is a string. For containers like ``iter`` or ``table``, this is a list.
*   ``color``: (Optional) A string representing a color (e.g., "red", "#FF0000") that backends will attempt to apply to the text content.
*   ``end``: (Optional) A string to append after the element content, such as a custom line break.

Supported Types
---------------

Based on the ``constr`` class in ``core.py``, here are the available types and their specific roles:

*   **meta**:
    Used to store document-wide metadata.
    *   ``data``: A dictionary containing key-value pairs (e.g., ``title``, ``author``, ``template_id``).

*   **markdown**:
    Text content that should be parsed using Markdown syntax.

*   **text**:
    Basic plain text content.

*   **line**:
    Similar to ``text``, but defaults to appending a newline (``\n``).

*   **latex**:
    Raw LaTeX code. Backends that support LaTeX (like the PDF or TeX exporters) will pass this through directly.

*   **verbatim**:
    Preformatted text, typically rendered in a fixed-width font (like a code block).

*   **iter**:
    A container type used to group multiple document elements together.
    *   ``children``: A list of other element dictionaries.

*   **table**:
    Represents tabular data.
    *   ``children``: A list of lists (a matrix) containing the cell contents.
    *   ``header``: (Optional) A list of strings for the table header row.
    *   ``caption``: (Optional) A string description for the table.
    *   ``borders``: (Boolean) Whether to render cell borders.
    *   ``n_cols`` / ``n_rows``: (Optional) Dimensions of the table.

*   **image**:
    Embedded graphical content.
    *   ``imageblob``: A base64-encoded string of the image data (prefixed with data URI scheme).
    *   ``caption``: (Optional) Text to display under the image.
    *   ``width``: (Optional) A number representing the scale or width of the image (often 0.0 to 1.0).
    *   ``children``: Used as a filename or unique identifier for the image asset.

JSON Definition
---------------

The following JSON file defines the structure for each supported element type:

.. literalinclude:: ../src/pydocmaker/datamodel.json
   :language: json
   :caption: datamodel.json