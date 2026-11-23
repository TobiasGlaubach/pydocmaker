
import os
import json
from typing import Iterable, List, Tuple, Union
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, ChoiceLoader, Undefined, meta, TemplateNotFound, Template

TEMPLATE_EXTS = 'jinja2 j2 jinja j'.split() 

# the priority in which to resolve templates
TEMPLATE_PRIORITY = ['.typ', '.tex', '.html']


default_template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

registered_template_dirs = set()


try:
    from pydocmaker import util
except Exception as err:
    from . import util

try:
    from pydocmaker import blocktmpl
except Exception as err:
    from . import blocktmpl

BlockDocTemplate = blocktmpl.BlockDocTemplate
detect_block_template = blocktmpl.detect_block_template
parse = blocktmpl.parse
scaffold = blocktmpl.scaffold
update_params = blocktmpl.update_params
render = blocktmpl.render
detect = blocktmpl.detect

__all__ = ['DocTemplate', 'BlockDocTemplate', 'TemplateDirSource', 'handle_template',
           'get_template_source', 'register_new_template_dir', 'remove_from_template_dir',
           'get_registered_template_dirs', 'get_available_template_ids', 'test_template_exists',
           'get_template_params', 'resolve_template_id', 'determine_engine_from_template',
           'parse', 'scaffold', 'update_params', 'render', 'detect']
    
def determine_engine_from_template(template: Union[Template, str, Path], tformat=None) -> str:
    """Detect the template engine type from a template string or file path.

    Accepts a Jinja2 Template object (extracts ``filename``), a file path string,
    or a raw template source string. Returns one of ``'html'``, ``'typ'``, or
    ``'tex'``, or ``None`` if the engine cannot be determined.

    For file paths the engine is inferred from the file extension. For raw source
    strings the function looks for engine-specific markers such as ``<html>``,
    ``#set ``, or ``\documentclass``.

    Args:
        template: A Jinja2 Template object, a file path string, or a raw template
            source string.

    Returns:
        str or None: One of ``'html'``, ``'typ'``, ``'tex'``, or ``None``.
    """
    engine = None
    if hasattr(template, "filename"): # jinja2 template has a filename attribute
        template = template.filename
    if isinstance(template, Path):
        template = str(template)

    if isinstance(template, str):
        template = resolve_template_id(template, tformat=tformat, on_error=template) # e.G. "base" to "base.tex.j2" if found else keep "base"
        
        _, match_ = _remove_template_ext_match(template)
        if os.path.exists(template) or match_:
            eng = Path(template).suffixes[0]
            if eng.startswith('.'):
                eng = eng[1:]
            eng = eng.lower()

            if eng == 'html':
                engine = 'html'
            elif eng.startswith('typ'):
                engine = "typ"
            elif eng.endswith('tex'):
                engine = "tex"
        else:
            if '<html>' in template or '<!DOCTYPE html>' in template:
                engine = 'html'
            elif '#set ' in template:
                engine = 'typ'
            elif r'\documentclass' in template or r'\begin{document}' in template or r'\end{document}' in template:
                engine = 'tex'
    
    return engine

def get_template_source(template_obj:Template):
    if isinstance(template_obj, BlockDocTemplate):
        return template_obj.template
    loader = getattr(template_obj.environment, 'loader', None)
    if loader is None:
        template_str = ''
    else:
        template_str, _, _ = loader.get_source(template_obj.environment, template_obj.name)

    template_str, _, _ = loader.get_source(template_obj.environment, template_obj.name)
    return template_str


def _block_template_from_source(source, tformat, template_id=None, attachments=None):
    """Build a BlockDocTemplate from a source string, scaffolding the blocks
    in memory when the source carries no markers."""
    if not detect_block_template(source):
        source = scaffold(source, tformat=tformat)
    return BlockDocTemplate(source, tformat=tformat, template_id=template_id), (attachments if attachments is not None else {}), source


def handle_template(template, default_template, tformat=None, template_engine='auto') -> Tuple[Template, dict, str]:
    if template_engine not in ('auto', 'blocks', 'jinja2'):
        raise ValueError(f"template_engine must be one of 'auto', 'blocks', 'jinja2', got {template_engine!r}")

    if template is None:
        template = default_template

    template_str = None
    attachments = {}
    if hasattr(template, 'render'):
        template_obj:Template = template
        template_str = get_template_source(template_obj)
    elif isinstance(template, str) and os.path.exists(template):
        if template_engine in ('auto', 'blocks'):
            with open(template, 'r', encoding='utf-8-sig') as f:
                src = f.read()
            if detect_block_template(src) or template_engine == 'blocks':
                return _block_template_from_source(src, tformat, template_id=os.path.basename(template))
        template_obj = Template(template)
    elif template is None or (isinstance(template, str) and not template):
        template_str = '{{ body }}'
        template_obj = Template(template_str)
    elif isinstance(template, str):
        if template_engine in ('auto', 'blocks') and detect_block_template(template):
            return _block_template_from_source(template, tformat)
        # resolve the id the same way DocTemplate.from_tid does (format
        # candidates first) so the direct and the metadata template flows
        # always end up on the same template file
        template_obj = None
        tdir = TemplateDirSource(tformat=tformat)
        for cand in _candidate_template_ids(template, tformat):
            template_obj = tdir.get(cand, None)
            if template_obj is not None:
                break
        if template_obj is None:
            template_obj = tdir.get(template, None)
        if template_obj is None:
            template_obj = Template(template)
            template_str = str(template)

    else:
        raise KeyError(f'Unknown template type! {type(template)=}')

    if template_str is None:
        template_str = get_template_source(template_obj)

    if template_engine == 'blocks' or (template_engine == 'auto' and detect_block_template(template_str)):
        template_id = getattr(template_obj, 'template_id', None)
        return _block_template_from_source(template_str, tformat, template_id=template_id, attachments=attachments)

    if detect_block_template(template_str):
        util.log.warning(
            "template_engine='jinja2' was forced but the template source contains block markers; "
            'the markers will be ignored by the Jinja2 engine')

    return template_obj, attachments, template_str


def _remove_template_ext(filename):
    parts = str(filename).split('.')
    if parts[-1] in TEMPLATE_EXTS:
        return '.'.join(parts[:-1])
    else:
        return filename

def _remove_template_ext_match(filename):
    if isinstance(filename, Path):
        filename = str(filename)
    if isinstance(filename, str):
        match_ = next((f'.{k}' for k in TEMPLATE_EXTS if filename.endswith(k)), '')
        # NOTE: slicing with -0 would return the empty string, so only slice
        # when a template extension actually matched
        fn = filename[:len(filename) - len(match_)] if match_ else filename
    else:
        match_ = False
        fn = filename
    return fn, True if match_ else False


def _candidate_template_ids(template_id, tformat=''):
    """Build the candidate template ids for a lookup, in priority order.

    1. The id combined with the format suffix, without double-appending it
       (``"base" + ".tex"`` -> ``"base.tex"``; ``"base.tex" + ".tex"`` stays
       ``"base.tex"``; ``"base.tex.j2" + ".tex"`` stays ``"base.tex.j2"``).
    2. When the id carries a *different* format suffix, the id with that suffix
       swapped for the requested one (``"base.tex"`` looked up as ``"html"``
       -> ``"base.html"``), so cross-format lookups still find the variant.

    With no ``tformat`` given the id is used as-is.
    """
    template_id = str(template_id)
    tformat = '' if tformat is None else tformat
    if tformat and not tformat.startswith('.'):
        tformat = '.' + tformat

    if not tformat:
        return [template_id]

    base, _had_tpl_ext = _remove_template_ext_match(template_id)
    if base.endswith(tformat):
        return [template_id]
    candidates = [template_id + tformat]
    if '.' in base:
        candidates.append(base.rsplit('.', 1)[0] + tformat)
    return candidates


def register_new_template_dir(new_template_dir:str, check_exists=True) -> bool:
    """Register a new template directory if its not already registered. 
    NOTE: If its already registered this function does nothing without much overhead. 

    Args:
        new_template_dir (str): The path to the new template directory.
        check_exists (bool, optional): Whether to check if the directory exists. Defaults to True.

    Raises:
        FileNotFoundError: If the directory does not exist and check_exists is True.

    Returns:
        bool: True if the directory was successfully registered, False otherwise.
    """
    if isinstance(new_template_dir, Path):
        new_template_dir = str(new_template_dir)
    if check_exists and not os.path.exists(new_template_dir):
        raise FileNotFoundError(f'The directory "{new_template_dir}" does not exist.')
    global registered_template_dirs
    registered_template_dirs.add(new_template_dir)
    return new_template_dir in registered_template_dirs

def remove_from_template_dir(to_remove:str) -> bool:
    """Removes an existing template directory if it exists.

    Args:
        to_remove (str): The path to remove from the template dirs.

    Returns:
        bool: Always True
    """

    global registered_template_dirs
    if to_remove in registered_template_dirs:
        registered_template_dirs.remove(to_remove)
    return True



def get_registered_template_dirs(include_default=True):
    """Returns a list of registered template directories.

    Args:
        include_default (bool, optional): Whether to include the default template directory.
            Defaults to True.

    Returns:
        list: A list of registered template directories. If include_default is True, the default
            template directory is the first element in the list.
    """
    if include_default:
        return [default_template_dir] + [d for d in registered_template_dirs]
    else:
        return [d for d in registered_template_dirs]

def test_template_exists(template_id, tformat = '', template_dir=None):
    """tests if a template with a given id and optional in a given format exists

    Args:
        template_id (str): the template id to search for e.G. 'base' or 'base.tex'
        tformat (str, optional): optinal the template format to look for (e.g. 'html', 'typ', 'tex') if nothing is given the first found template with that name independent of the format is returned. Defaults to ''.
        template_dir (str, optional): if this is given only the given template directory is mounted to load jinja templates. Defaults to ''.

    Returns:
        bool: True if found False otherwise
    """
    tds = TemplateDirSource(template_dir)
    return any(tid in tds for tid in _candidate_template_ids(template_id, tformat))


def get_available_template_ids(template_dir=None, tformat=None) -> list:
    """Retrieve the template IDs from the registered template directories.

    Args:
        template_dir (str, optional): A specific template directory to search.
            If None, all registered template directories are searched.
        tformat (str, optional): Template format filter (e.g. 'html', 'typ', 'tex').
            If None, no format filtering is applied.

    Returns:
        list: A list of template IDs (names without file extensions).
    """
    return TemplateDirSource(template_dir, tformat=tformat).get_template_ids()


def get_template_params(template_id=None, template_dir=None, allow_fallback_jinja=True, tformat=None) -> dict:
    """Retrieve the parameters for one or more templates.
    
        When a .params.json file is found for a template, its contents are used as-is.
        When no .params.json file exists and ``allow_fallback_jinja`` is True, parameters
        are inferred from the template source via ``find_undeclared_variables``, in which
        case all parameter values are set to ``jinja2.Undefined`` which will be ignored 
        on render.

    Args:
        template_id (str, optional): A specific template ID to get parameters for.
            If None, parameters for all templates are returned.
        template_dir (str, optional): A specific template directory to search.
            If None, all registered template directories are searched.
        allow_fallback_jinja (bool, optional): If True and no .params.json file is found,
            infer parameters from undeclared variables in the template source. Defaults to True.
        tformat (str, optional): Template format filter (e.g. 'html', 'typ', 'tex').
            If None, no format filtering is applied.

    Returns:
        dict: A dictionary of template parameters. If template_id is provided, the parameter dicts 
            is returned directly for template_id. If template_id is None, keys are
            template IDs mapping to their parameter dicts (including all templates).
    """
    return TemplateDirSource(template_dir, tformat=tformat).get_params(template_id, allow_fallback_jinja=allow_fallback_jinja)
    
def resolve_template_id(template_id, template_dir=None, tformat=None, on_error='raise'):
    """Resolve a template ID to its full file name.

    Args:
        template_id (str): The template ID to resolve (e.g. 'base', 'base.html', 'base.html.j2').
        template_dir (str, optional): A specific template directory to search.
            If None, all registered template directories are searched.
        tformat (str, optional): Template format filter (e.g. 'html', 'typ', 'tex').
            If None, no format filtering is applied.
        on_error (str|Any, optional): if this is anything but "raise" the given value will be 
            returned on a KeyError.
    Returns:
        str: The actual template file name resolved from the available templates.
    """
    try:
        return TemplateDirSource(template_dir, tformat=tformat).resolve_template_id(template_id)    
    except KeyError as err:
        if on_error == 'raise':
            raise err
        else:
            return on_error
    


class TemplateDirSource():
    """Manage templates, parameters, and attachments from specified directories.

    ...

    Attributes
    ----------
    template_dirs : list
        a list of directory paths where templates are located
    env : Environment
        an Environment object from the jinja2 library used to load templates
    engine : str or None
        The template engine type filter. When set, only templates matching the engine
        type are loaded ("html", "typ" for templates starting with "typ", or "tex"
        for templates ending with "tex").

    Methods
    -------
    get_params(templates=None, allow_fallback_jinja=True)
        Returns a dictionary of parameters for the specified templates.
    get_templates()
        Returns a dictionary of Jinja2 Template objects keyed by template name.
    get_template_ids()
        Returns a list of template IDs (names without file extensions).
    get_attachments(templates=None)
        Returns a dictionary of attachments for the specified templates.
    get_all(load_params=True, load_attachments=True)
        Returns a tuple of (templates dict, params dict, attachments dict).
    resolve_template_id(my_template_id)
        Returns the full template file name corresponding to the given template ID.
    find_undeclared_variables(template)
        Returns a set of variable names used in the template but not declared.
    """


    VALID_ENGINES = ("html", "typ", "tex")

    def __init__(self, template_dirs:List[str]=None, tformat=None) -> None:
        
        if template_dirs is None:
            template_dirs = get_registered_template_dirs(include_default=True)
        elif isinstance(template_dirs, str):
            template_dirs = [template_dirs]
        self.template_dirs = template_dirs

        if tformat is None:
            tform = tformat
        elif isinstance(tformat, str) and tformat.lower().startswith('html'):
            tform = 'html'
        elif isinstance(tformat, str) and tformat.lower().startswith('typ'):
            tform = 'typ'
        elif isinstance(tformat, str) and tformat.lower().endswith('tex'):
            tform = 'tex'
        else:
            raise ValueError(f"engine must be one of {self.VALID_ENGINES}, got '{tformat}'")
        self.tformat = tform

        loaders = [FileSystemLoader(template_dir) for template_dir in self.template_dirs]
        self.env = Environment(loader=ChoiceLoader(loaders))
             

    def find_undeclared_variables(self, template:Union[Template, str]):
        """Find undeclared variables in a Jinja2 template.

        Accepts the ``template`` argument as any of the following:

        * a :class:`pathlib.Path` or ``str`` **template ID** (e.g. ``"base.tex"``,
          ``"base.html.j2"``) â€” the ID is resolved via ``resolve_template_id``
          so that ``{% extends %}``, ``{% include %}``, etc. are followed
          through by jinja2's loader.
        * a ``str`` containing raw Jinja2 template source code
        * a Jinja2 ``Template`` object loaded from a file (has a ``filename``
          attribute pointing to an on-disk file)

        Jinja2's ``env.parse()`` is used for all paths that go through the
        loader, which automatically traces ``{% extends %}`` / ``{% include %}``
        and collects variables from all included/extended templates.

        Note: Jinja2 does not expose the original source of templates created
        via ``Environment.from_string()`` (``name`` is ``None`` and there is
        no ``filename``).  Passing such templates raises ``ValueError``.  Use
        a raw source string instead.

        Args:
            template: The template to analyze. See above for accepted types.

        Returns:
            set: A set of undeclared variable names used in the template.
        """
        # --- Case: already a Jinja2 Template object ---
        if isinstance(template, BlockDocTemplate):
            return set(template.params.keys()) | {'body'}

        if isinstance(template, Template):
            env = getattr(template, "environment", None) or self.env
            # Try to reconstruct the template ID (the "name" attribute) and
            # re-load through the loader so that includes/extends are resolved.
            tmp_name = getattr(template, "name", None)
            if tmp_name is not None:
                try:
                    raw_source, _, _ = env.loader.get_source(env, tmp_name)
                    return meta.find_undeclared_variables(env.parse(raw_source))
                except Exception:
                    pass
            # If name is None (from_string) or loader can't resolve it,
            # try filename as a last resort (read raw file directly).
            fn = getattr(template, "filename", None)
            if fn and os.path.exists(fn):
                with open(fn, "r", encoding="utf-8") as f:
                    raw_source = f.read()
                return meta.find_undeclared_variables(env.parse(raw_source))
            raise ValueError(
                "Cannot extract source from template object. "
                "Pass the template source as a string or use a template "
                "loaded from a file."
            )

        # --- Case: Path / string ---
        file_path = None
        if isinstance(template, Path):
            file_path = template
            template = str(template)

        if isinstance(template, str):
            env = self.env
            stripped = template.strip()

            # Comment-delimited block templates: return the declared parameter
            # names (plus the reserved 'body') instead of jinja2 analysis.
            try:
                block_templates = self.get_block_templates()
            except Exception as err:
                block_templates = {}
            if stripped in block_templates:
                return set(block_templates[stripped].params.keys()) | {'body'}

            # If we got an absolute file path from a Path object, use it
            # directly via a temporary loader so that jinja2's include/extends
            # resolution works correctly.
            if file_path and file_path.is_file():
                abs_dir = str(file_path.parent)
                abs_base = file_path.name
                # Build a temporary loader hierarchy where the file's own
                # directory is the first (highest-priority) search path so
                # that relative includes/extends from the file itself work.
                if isinstance(env.loader, ChoiceLoader):
                    existing = env.loader.loaders.copy()
                    new_loader = FileSystemLoader(abs_dir)
                    env = Environment(loader=ChoiceLoader([new_loader] + existing))
                else:
                    env = Environment(
                        loader=ChoiceLoader(
                            [FileSystemLoader(abs_dir), env.loader]
                        )
                    )
                # Now try resolving through the loader so includes are traced.
                try:
                    raw_source, _, _ = env.loader.get_source(env, abs_base)
                    return meta.find_undeclared_variables(env.parse(raw_source))
                except TemplateNotFound:
                    pass

            # --- Try to resolve via the loader (handles template IDs) ---
            if env and env.loader:
                try:
                    actual_name = self.resolve_template_id(stripped)
                    raw_source, _, _ = env.loader.get_source(env, actual_name)
                    return meta.find_undeclared_variables(env.parse(raw_source))
                except (KeyError, TemplateNotFound):
                    pass

                # Try get_source with the name as-is (handles e.g.
                # "templates/base.html.j2" if a sub-loader knows that dir).
                try:
                    raw_source, _, _ = env.loader.get_source(env, stripped)
                    return meta.find_undeclared_variables(env.parse(raw_source))
                except TemplateNotFound:
                    pass

            # --- Fall back: raw source ---
            return meta.find_undeclared_variables(env.parse(stripped))

        raise TypeError(
            f"template must be a Path, str, or Jinja2 Template object, "
            f"got {type(template).__name__}"
        )
    

    
    def get_params(self, templates:Iterable[str]=None, allow_fallback_jinja=True) -> dict:
        """
        Returns a dictionary of (default) parameters for the specified templates.

        When a .params.json file is found for a template, its contents are used as-is.
        When no .params.json file exists and ``allow_fallback_jinja`` is True, parameters
        are inferred from the template source via ``find_undeclared_variables``, in which
        case all parameter values are set to ``jinja2.Undefined`` which will be ignored on render.

        Args:
            templates (iterable str): An iterable of template ids/names. If None, all templates are loaded.
            allow_fallback_jinja (bool, optional): If True and no .params.json file is found for a template,
                infer parameters from undeclared variables in the template source with ``None`` values.
                Defaults to True.

        Returns:
            dict: A dictionary keyed by template_id, where each value is a dict of
                param_name to param_value. When parameters come from a .params.json file,
                values are as defined in that file. When inferred via the Jinja2 fallback,
                all values are ``None``.
        """
        if isinstance(templates, (str, Template)):
            return next(iter(self.get_params([templates], allow_fallback_jinja).values()))
        
        if templates is None:
            templates = {**self.get_block_templates(), **self.get_templates()}
        block_templates = self.get_block_templates()
        params = {}
        for template_id in templates:
            # if its a Template and it has a filename use the filename instead
            if hasattr(template_id, 'filename'):
                template_id = Path(template_id.filename).name.split('.')[0]

            # comment-delimited block templates: params come from the parsed block
            # (a <id>.params.json file, if present, stays authoritative)
            if isinstance(template_id, str) and template_id in block_templates:
                template_param_name = Path(template_id).name.split('.')[0] + '.params.json'
                loaded = False
                for template_dir in self.template_dirs:
                    fpath = os.path.join(template_dir, template_param_name)
                    if os.path.exists(fpath) and os.path.isfile(fpath):
                        with open(fpath, 'r') as f:
                            params[template_id] = json.load(f, cls=util.MyJSONDecoder)   
                        loaded = True
                        break
                if not loaded:
                    params[template_id] = dict(block_templates[template_id].params)
                continue

            template_param_name = Path(template_id).name.split('.')[0] + '.params.json'
            for template_dir in self.template_dirs:
                fpath = os.path.join(template_dir, template_param_name)
                if os.path.exists(fpath) and os.path.isfile(fpath):
                    with open(fpath, 'r') as f:
                        params[template_id] = json.load(f, cls=util.MyJSONDecoder)   
                    break
            if not template_id in params and allow_fallback_jinja:
                undeclared_vars = None
                try:
                    undeclared_vars = self.find_undeclared_variables(template_id)
                except TypeError as err:
                    template = self.get(template_id, None)
                    undeclared_vars = self.find_undeclared_variables(template)

                if not undeclared_vars is None:
                    params[template_id] = {k:util.undefined_name2str(k) for k in undeclared_vars if k != 'body'}


        return params
    
    def get(self, template_id:str, default=None):
        try:
            template_id = self.resolve_template_id(template_id)
            templates = {**self.get_block_templates(), **self.get_templates()}
            return templates.get(template_id, default)
        except KeyError as err:
            return default

    def _template_matches_engine(self, template_name):
        """Check if a template name matches the configured engine filter."""
        # Strip .j2 suffix for analysis
        base, is_template_ext = _remove_template_ext_match(template_name)
        
        # only take parameters that match the .j2 syntax or similar
        if not is_template_ext:
            return False
        
        # Exclude params files
        if base.endswith('.params.json'):
            return False
        # Exclude hidden/git files
        if base.startswith('.git') or base.startswith('.'):
            return False
        # Exclude block_ prefixed templates
        if base.startswith('block_'):
            return False
        # Apply tformat filter
        if not (self.tformat is None or base.endswith(f'.{self.tformat}')):
            return False
        
        return True

    def _block_template_matches_engine(self, template_name):
        """Check if a native (non-jinja) template file name qualifies as a block
        template candidate for the configured engine filter."""
        base = os.path.basename(template_name.replace('\\', '/'))
        root, ext = os.path.splitext(base)
        if ext.lower() not in ('.html', '.tex', '.typ'):
            return False
        # Exclude params files (defensive; .json has a different extension anyway)
        if base.endswith('.params.json'):
            return False
        # Exclude hidden/git files
        if base.startswith('.git') or base.startswith('.'):
            return False
        # Exclude block_ prefixed templates (reserved prefix for both engines)
        if base.startswith('block_'):
            return False
        # Apply tformat filter
        if not (self.tformat is None or ext.lower() == f'.{self.tformat}'):
            return False
        return True

    def get_block_templates(self) -> dict:
        """Retrieves all comment-delimited block templates (``*.html``/``*.tex``/``*.typ``
        files whose source contains ``pydocmaker:`` markers) from the template directories.

        Excludes ``.j2`` files, ``block_``-prefixed files, ``.params.json`` files and
        dotfiles. When the same relative file name exists in several directories the
        first directory (in registration order) wins.

        Returns:
            dict: A dictionary of block templates where the keys are the template file
                names and the values are BlockDocTemplate objects.
        """
        result = {}
        for template_dir in self.template_dirs:
            if not os.path.isdir(template_dir):
                continue
            for root, dirs, files in os.walk(template_dir):
                dirs[:] = [d for d in dirs if d != '.git' and not d.startswith('.')]
                for file in sorted(files):
                    rel = os.path.relpath(os.path.join(root, file), template_dir).replace(os.sep, '/')
                    if not self._block_template_matches_engine(rel):
                        continue
                    if rel in result:
                        continue
                    fpath = os.path.join(root, file)
                    try:
                        with open(fpath, 'r', encoding='utf-8-sig') as f:
                            source = f.read()
                    except OSError as err:
                        continue
                    if not detect_block_template(source):
                        continue
                    try:
                        result[rel] = BlockDocTemplate(source, tformat=self.tformat, template_id=rel)
                    except Exception as err:
                        util.log.warning(f'failed to load block template "{rel}": {err}')
        return result

    def get_templates(self) -> dict:
        """Retrieves all the templates from the directory.

       Returns:
           dict: A dictionary of templates where the keys are the template names
               and the values are the corresponding Jinja2 Template objects.
        """

        templates = self.env.list_templates(filter_func=self._template_matches_engine)
        templates = {template: self.env.get_template(template) for template in templates}
        return templates

    def get_template_ids(self):
        """
        This function retrieves the template IDs from the list of templates.

        Returns:
            list: A list of template IDs, which are the names of the templates without the file extension.
                Includes both jinja2 templates and comment-delimited block templates (jinja2 priority).
        """
        templates = self.get_templates()
        block_templates = self.get_block_templates()
        template_ids = {t.rsplit('.')[0]:t for t in block_templates}
        template_ids.update({t.rsplit('.')[0]:t for t in templates})
        return list(template_ids.keys())


    def get_attachments(self, templates=None):
        """Get attachments from the template directory.

        Args:
            templates (list or dict, optional): A list or dictionary of templates.
                If None, all templates will be used. Defaults to None.

        Returns:
            dict: A dictionary of attachments, where the keys are the template names
                and the values are dictionaries of attachments for that template.
        """
        if templates is None:
            templates = self.get_templates()
        if isinstance(templates, dict):
            templates = list(templates.keys())
        
        def helper(folder, template_dir):
            dc = {}
            folderpath = os.path.join(template_dir, folder) 
            if os.path.exists(folderpath) and os.path.isdir(folderpath):
                for file in os.listdir(folderpath):
                    with open(os.path.join(folderpath, file), 'rb') as f:
                        dc[file] = f.read()
            return dc
        

        attachments = {'': {}}
        for template_dir in self.template_dirs:
            attachments[''].update(helper('assets', template_dir))

        # HACK: this overwrites files with the same names if they are in multiple assets folders... 
        # Solving this with absolut pathes would be a mess though, so I rather keep it like this
        for template in (templates):
            attachments[template] = {}
            for template_dir in self.template_dirs:
                folder = template.rsplit('.')[0] + '.assets'
                attachments[template].update(helper(folder, template_dir))
        return attachments
    
    def get_all_filenames(self):
        """Get all filenames in all template directories."""
        filenames = []
        for template_dir in self.template_dirs:
            for root, foldr, files in os.walk(template_dir):
                if '.git' in root:
                    continue
                for file in files:
                    filenames.append(os.path.join(root, file))
        return filenames
    
    def get_all(self, load_params=True, load_attachments=True):
        """Get all templates (jinja2 and comment-delimited block templates),
        parameters, and attachments.

        Args:
            load_params (bool, optional): Whether to load parameters. Defaults to True.
            load_attachments (bool, optional): Whether to load attachments. Defaults to True.

        Returns:
            tuple: A tuple containing templates, parameters, and attachments.
        """
        templates = {**self.get_block_templates(), **self.get_templates()}
        params = self.get_params(templates) if load_params else {}
        attachments = self.get_attachments(templates) if load_attachments else {}
        return templates, params, attachments

    def resolve_template_id(self, my_template_id):
        """Resolve the template ID to the actual template file name.

        An exact file name match always wins (so ``base.tex`` can force a block
        template file even when ``base.tex.j2`` also exists); short IDs prefer the
        first available format variant in priority order (tex > typ > html).

        Args:
            my_template_id (str): The template ID to resolve.

        Returns:
            str: The actual template file name.

        Raises:
            KeyError: If the template ID is not found in the available templates.
        """
        templates = self.get_templates()
        block_templates = self.get_block_templates()
        if my_template_id in templates:
            return my_template_id
        if my_template_id in block_templates:
            return my_template_id

        # Collect all templates keyed by short name (without last extension)
        short_map = {}
        for t in templates:
            base = t.rsplit('.', 1)[0]
            short_map.setdefault(base, []).append(t)
        for t in block_templates:
            base = t.rsplit('.', 1)[0]
            short_map.setdefault(base, []).append(t)

        # Check if we have multiple format variants of the same template
        base_name = my_template_id.rsplit('.', 1)[0] if '.' in my_template_id else my_template_id
        variants = short_map.get(base_name, [])

        if len(variants) > 1:
            
            for ext in TEMPLATE_PRIORITY:
                for v in variants:
                    if v.endswith(ext) or v.endswith(ext + '.j2'):
                        return v
            return variants[0]

        # No multiple variants - use existing logic
        template_ids = {t.rsplit('.')[0]:t for t in templates}
        template_ids.update({_remove_template_ext(t):t for t in templates})
        block_ids = {}
        for t in block_templates:
            block_ids.setdefault(t.rsplit('.')[0], t)
            block_ids.setdefault(_remove_template_ext(t), t)
        for k, v in block_ids.items():
            template_ids.setdefault(k, v)
        if not my_template_id in template_ids:
            raise KeyError(f'{my_template_id=} was not found in {template_ids.keys()=}')
        return template_ids[my_template_id]

    def __contains__(self, template_id):
        """Check if a template_id is in any of the template directories."""
        try:
            self.resolve_template_id(template_id)
            return True
        except KeyError as err:
            return False

class DocTemplate():
    """A class used to represent a document template.

    This class provides methods to load a template from a template directory,
    render the template with given parameters, and manage attachments.

    Attributes:
        template (str): A string representation of the template.
        params (dict): A dictionary of parameters to be used in the template.
        attachments (dict): A dictionary of attachments to be used with the template.
        env (Environment): An instance of the jinja2 Environment class.
    """
    @staticmethod
    def from_tid(template_id:str, tformat='', template_dir=None):
        """Load a template by supplying a template_id and possibly a template format

        Args:
            template_id (str): The ID of the template to load e.G. "base" or "base.tex"
            tformat (str, optional): optinal the template format to get e.G. ".tex" or ".html". Defaults to '' which means first of any format being found.
            template_dir (str, optional): The directory containing the templates.
                If not provided, the default template directory is used.
        Returns:
            DocTemplate: An instance of the DocTemplate class.
        """
        t = TemplateDirSource(template_dir)
        err = None
        for cand in _candidate_template_ids(template_id, tformat):
            try:
                template_id = t.resolve_template_id(cand)
                break
            except KeyError as e:
                err = e
        else:
            raise err
        templates, params, attachments_all = t.get_all()
        # global assets and template specific assets
        attch = {**attachments_all[''], **attachments_all[template_id]} 

        template, params = templates[template_id], params[template_id]
        if isinstance(template, BlockDocTemplate):
            return BlockDocTemplate(template.template, params=params, attachments=attch, tformat=None, template_id=template_id)
        return DocTemplate(template, params, attch, t.env, template_id)

    @staticmethod
    def test_tid_exists(template_id:str, tformat='', template_dir=None):
        """Test if a template with the given ID and optional format exists.

        Args:
            template_id (str): The template ID to search for (e.g. 'base').
            tformat (str, optional): The template format to look for ('tex', 'html', etc.).
                If empty, checks for any format. Defaults to ''.
            template_dir (str, optional): If given, only the specified template directory
                is searched. Defaults to None.

        Returns:
            bool: True if a template with the given ID (and optional format) exists.
        """
        return test_template_exists(template_id, tformat, template_dir)
    
    @staticmethod
    def get_available_tids(template_dir=None):
        """Get the list of available template IDs.

        Args:
            template_dir (str, optional): A specific template directory to search.
                If None, all registered template directories are searched.

        Returns:
            list: A list of template IDs (names without file extensions).
        """
        return TemplateDirSource(template_dir).get_template_ids()

    def __init__(self, template, params=None, attachments = None, env=None, template_id=None) -> None:
        """Initialize a DocTemplate instance.

        Args:
            template (str): A string representation of the template.
            params (dict, optional): A dictionary of parameters to be used in the template.
                If not provided, an empty dictionary is used.
            attachments (dict, optional): A dictionary of attachments to be used with the template.
                If not provided, an empty dictionary is used.
            env (Environment, optional): An instance of the jinja2 Environment class. NOT NEEDED. ONLY FOR CONVENIENCE
            template_id (str, optional): the actual template id for this template
        """
        self.template = template
        self.params = params if not params is None else {}
        self.attachments = attachments if attachments is not None else {}
        self.env = env or Environment(cache_size=0)
        self.template_id = template_id

    @property
    def tformat(self):
        if not self.template_id:
            return ''
        tid = self.template_id
        tid = _remove_template_ext(tid)
        
        if not '.' in tid:
            return ''
        return tid.split('.')[-1]
        
    def __str__(self):
        return f"TemplateObject(id={self.template_id}, template={self.template}, params.keys()={self.params.keys()})"

    def __repr__(self):
        return self.__str__()

    def render(self, **kwargs):
        """Render the Jinja2 template with given parameters.

        If the template source contains comment-delimited block markers the render
        is delegated to the block templating engine (``BlockDocTemplate``) instead.

        Args:
            **kwargs: Additional parameters to be used in the template.

        Returns:
            str: The rendered template as a string.
        """
        if isinstance(self.template, str) and detect_block_template(self.template):
            block_template = BlockDocTemplate(
                self.template, params=self.params, attachments=self.attachments,
                tformat=self.tformat or None, template_id=self.template_id)
            return block_template.render(**kwargs)

        params = {**self.params, **kwargs}
        params = util.remove_undefined(params)
        return self.template.render(**params)

if __name__ == '__main__':
    res = register_new_template_dir(r"C:\Users\tglaubach\repos\jupyter-script-runner\doc_templates")

    print(f"{res=}")
    print(get_registered_template_dirs())
    d = TemplateDirSource()
    print(d.template_dirs)
    # print(d.get_all_filenames())
    print(d.get_templates().keys())
    print({k:v.keys() for k, v in d.get_attachments().items()})
          

    # print(f'{("base" in d)=}')
    # print(f'{("mke" in d)=}')
    # t = DocTemplate.from_tid('base')
    # print(d.resolve_template_id("base"))
    # print(f'{DocTemplate.test_tid_exists("base", "tex")=}')
    # print(f'{DocTemplate.test_tid_exists("base", "html")=}')