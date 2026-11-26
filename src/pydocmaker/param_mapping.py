"""Legacy template-parameter name mapping for the templating engines.

Historic documents (e.g. produced by the JupyRun test system) carry their
template parameters under plain, unprefixed names ("project", "title",
"doc_no", ...). The current template generation uses the "p"-prefixed names
("pProject", "pDocTitle", "pDocNo", ...).

This module bridges the two schemes: :func:`map_legacy_params` checks a
parameter mapping for legacy names and makes the same values available under
the new names, so old documents keep rendering correctly with new templates.

Rules:

* the check runs automatically on every render (both the block templating
  engine and the Jinja2 engine) -- see the integration notes below;
* a legacy name is only converted when it is actually present in the
  parameters (legacy names that are not given are not invented);
* a new name that is already present with a non-empty *user-set* value is
  never overwritten (explicit new-name values always win over legacy values);
* an empty new-name value (``None``, ``""``, empty dict/list) counts as
  "not set" and is filled from the legacy value;
* parameter values that merely mirror the template's own (placeholder)
  defaults count as "not user-set" as well and do not block the conversion
  (see the ``defaults`` argument);
* the conversion is non-destructive: the legacy keys are kept so that
  templates of the old generation (which render e.g. ``{{ title }}``) keep
  working unchanged.

Integration points (applied automatically, no user action needed):

* ``pydocmaker.blocktmpl.render`` and ``pydocmaker.blocktmpl.update_params``
  (module level functions of the block engine). The block engine converts
  template-aware: a legacy name is only converted when the template actually
  declares the new name, and legacy keys that the template does not declare
  are dropped once their new name is declared (they would only produce
  unused assignments in the rendered document).
* ``pydocmaker.blocktmpl.BlockDocTemplate.render``,
* ``pydocmaker.templating.DocTemplate.render``,
* the backend exporters ``to_html`` / ``to_tex`` / ``to_typst``
  (``pydocmaker.backend.ex_html`` / ``ex_tex`` / ``ex_typst``) for
  non-block (plain Jinja2) templates.
"""

#: mapping of legacy (old) parameter names to the new parameter names.
#: Legacy names without a new counterpart (e.g. "purpose", "scope") are
#: deliberately not listed and are passed through unchanged.
LEGACY_PARAM_MAP = {
    'project': 'pProject',
    'title': 'pDocTitle',
    'doc_no': 'pDocNo',
    'revision': 'pDocRevision',
    'status': 'pDocStatus',
    'date': 'pDate',
    'author': 'pAuthorName',
    'approved_by': 'pApprovedBy',
    'released_by': 'pReleasedBy',
    'confidential': 'pIsConfidential',
    'acronyms': 'pAcronyms',
    'applicables': 'pApplicables',
    'references': 'pReferences',
}


def is_empty_param_value(value) -> bool:
    """Whether a parameter value counts as "not set".

    ``None``, empty strings and empty collections (dict, list, tuple, set)
    count as empty; everything else (including ``False``, ``0`` and ``0.0``)
    counts as set.

    Args:
        value: the parameter value to test.

    Returns:
        bool: True when the value counts as "not set".
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value == ''
    if isinstance(value, (dict, list, tuple, set)):
        return not value
    return False


def _values_equal(a, b) -> bool:
    try:
        return bool(a == b)
    except Exception:
        return False


def map_legacy_params(params, mapping=None, available_new_names=None, drop_converted=False,
                      defaults=None) -> dict:
    """Map legacy parameter names onto the new parameter names.

    Checks ``params`` for legacy names (see :data:`LEGACY_PARAM_MAP`) and adds
    the same value under the new name for every legacy name found. A new name
    that is already present with a non-empty user-set value is never
    overwritten; an empty new-name value counts as "not set" and is filled
    from the legacy value. The legacy keys themselves are kept (non-destructive
    conversion) so old-generation templates referencing them keep working.

    The function is idempotent: applying it to an already mapped mapping
    returns an equal mapping.

    Args:
        params (dict): the parameter mapping to convert. Must be a dict (or None).
        mapping (dict, optional): the legacy -> new name mapping to apply.
            Defaults to :data:`LEGACY_PARAM_MAP`.
        available_new_names (collection, optional): the parameter names the
            target template knows (e.g. the parameters declared in the
            template). When given, a legacy name is only converted when its
            new name is in this collection -- i.e. when the template can
            actually use the converted value. When None, every legacy name
            found is converted.
        drop_converted (bool, optional): when True (together with
            ``available_new_names``), legacy keys whose new name is known to
            the template but which the template itself does not declare are
            removed from the result: their value lives on under the new name,
            the legacy key would only produce an unused assignment.
        defaults (mapping, optional): the template's declared default values
            (name -> default value). A new-name entry whose value merely
            mirrors such a default counts as "not user-set": it is removed
            (but only when the corresponding legacy name is present, so it
            cannot block the conversion). Without a legacy name the template
            defaults are left untouched.

    Returns:
        dict: a new dict with the legacy names converted to the new names
            (the input dict is not modified).

    Raises:
        TypeError: when ``params`` is not None and not a dict.
    """
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise TypeError(f'params must be a dict, got {type(params).__name__}')
    mapping = LEGACY_PARAM_MAP if mapping is None else mapping

    out = dict(params)
    for old, new in mapping.items():
        if old not in out:
            continue
        convert = available_new_names is None or new in available_new_names
        if convert:
            # a new-name entry that merely mirrors the template's own
            # (placeholder) default is not user-set -> remove it so it does
            # not block the conversion; without a legacy name the template
            # defaults are never touched
            if defaults and new in out and out[new] is not None \
                    and _values_equal(defaults.get(new), out[new]):
                del out[new]
            if new not in out or is_empty_param_value(out[new]):
                out[new] = out[old]
        if drop_converted and available_new_names is not None \
                and new in available_new_names and old not in available_new_names:
            del out[old]
    return out
