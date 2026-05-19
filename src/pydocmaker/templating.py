
import os
import json
from typing import List
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, ChoiceLoader, meta


default_template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

registered_template_dirs = set()

def register_new_template_dir(new_template_dir:str, check_exists=True) -> bool:
    """Register a new template directory.

    Args:
        new_template_dir (str): The path to the new template directory.
        check_exists (bool, optional): Whether to check if the directory exists. Defaults to True.

    Raises:
        FileNotFoundError: If the directory does not exist and check_exists is True.

    Returns:
        bool: True if the directory was successfully registered, False otherwise.
    """
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
        template_id (str): the template id to search for e.G. 'base'
        tformat (str, optional): optinal the template format to look for (either 'tex', or 'html') if nothing is given the first found template with that name independent of the format is returned. Defaults to ''.
        template_dir (str, optional): if this is given only the given template directory is mounted to load jinja templates. Defaults to ''.

    Returns:
        bool: True if found False otherwise
    """

    if tformat and not tformat.startswith('.'):
        tformat = '.' + tformat
    return (template_id + tformat) in TemplateDirSource(template_dir)


def get_available_template_ids(template_dir=None):
    """
        This function retrieves the template IDs from the list of templates.

        Returns:
            list: A list of template IDs, which are the names of the templates without the file extension.
    """
    return TemplateDirSource(template_dir).get_template_ids()


class TemplateDirSource():
    """
    A class used to manage templates, parameters, and attachments from a specified directory.

    ...

    Attributes
    ----------
    template_dir : str
        a string representing the directory path where the templates are located
    env : Environment
        an Environment object from the jinja2 library used to load templates

    Methods
    -------
    get_params(templates=None)
        Returns a dictionary of parameters for the specified templates.
    get_templates()
        Returns a dictionary of templates in the directory.
    get_template_ids()
        Returns a list of template IDs.
    get_attachments(templates=None)
        Returns a dictionary of attachments for the specified templates.
    get_all(load_params=True, load_attachments=True)
        Returns a tuple containing dictionaries of templates, parameters, and attachments.
    resolve_template_id(my_template_id)
        Returns the full template name corresponding to the given template ID.
    """


    def __init__(self, template_dirs:List[str]=None) -> None:
        
        if template_dirs is None:
            template_dirs = get_registered_template_dirs(include_default=True)
        elif isinstance(template_dirs, str):
            template_dirs = [template_dirs]
        self.template_dirs = template_dirs

        loaders = [FileSystemLoader(template_dir) for template_dir in self.template_dirs]
        self.env = Environment(loader=ChoiceLoader(loaders))
            

    def find_undeclared_variables(self, template):
        """Find undeclared variables in a template.

        Args:
            template (str): The template to analyze.

        Returns:
            set: A set of undeclared variable names used in the template.
        """
        ast = self.env.parse(template)
        return meta.find_undeclared_variables(ast)
    

    
    def get_params(self, templates=None) -> dict:
        """
        Returns a dictionary of (default) parameters for the specified templates.

        Args:
            templates (iterable str): A dictionary of template params. If None, all templates are loaded.

        Returns:
            dict: A dictionary of parameters for the specified templates with dict[template_id, dict[param_name,param_value]].
        """
        if templates is None:
            templates = self.get_templates()
        params = {}
        for template in templates:
            template_param_name = template.rsplit('.')[0] + '.params.json'
            for template_dir in self.template_dirs:
                fpath = os.path.join(template_dir, template_param_name)
                if os.path.exists(fpath) and os.path.isfile(fpath):
                    with open(fpath, 'r') as f:
                        params[template] = json.load(f)
                    break

        return params
    
    def get_templates(self) -> dict:
        """Retrieves all the templates from the directory.

       Returns:
           dict: A dictionary of templates where the keys are the template names
               and the values are the corresponding Jinja2 Template objects.
       """
        
        # List all templates in the directory
        filter = lambda t: (not t.startswith('block_') and t.endswith('.j2') and not t.startswith('.git'))
        templates = self.env.list_templates(filter_func=filter)

        #templates = [t for t in templates if t.endswith('tex.j2') and (not t.startswith('block_') and not t.endswith('.params.json'))]
        templates = {template: self.env.get_template(template) for template in templates}
        return templates

    def get_template_ids(self):
        """
        This function retrieves the template IDs from the list of templates.

        Returns:
            list: A list of template IDs, which are the names of the templates without the file extension.
        """
        templates = self.get_templates()
        template_ids = {t.rsplit('.')[0]:t for t in templates}
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
        """Get all templates, parameters, and attachments.

        Args:
            load_params (bool, optional): Whether to load parameters. Defaults to True.
            load_attachments (bool, optional): Whether to load attachments. Defaults to True.

        Returns:
            tuple: A tuple containing templates, parameters, and attachments.
        """
        templates = self.get_templates()
        params = self.get_params(templates) if load_params else {}
        attachments = self.get_attachments(templates) if load_attachments else {}
        return templates, params, attachments

    def resolve_template_id(self, my_template_id):
        """Resolve the template ID to the actual template file name.

        Args:
            my_template_id (str): The template ID to resolve.

        Returns:
            str: The actual template file name.

        Raises:
            KeyError: If the template ID is not found in the available templates.
        """
        templates = self.get_templates()
        if my_template_id in templates:
            return my_template_id
        template_ids = {t.rsplit('.')[0]:t for t in templates} # filename no extension only
        template_ids.update({t[:-3]:t for t in templates}) # remove ".j2" only
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
        attachments (dict): A dictionary of attachments to be used in the template.
        env (Environment): An instance of the jinja2 Environment class.
    """
    @staticmethod
    def from_tid(template_id:str, tformat='', template_dir=None):
        """Load a template by supplying a template_id and possibly a template format

        Args:
            template_id (str): The ID of the template to load e.G. "base"
            tformat (str, optional): optinal the template format to get e.G. ".tex" or ".html". Defaults to '' which means first of any format being found.
            template_dir (str, optional): The directory containing the templates.
                If not provided, the default template directory is used.
        Returns:
            DocTemplate: An instance of the DocTemplate class.
        """

        if tformat and not tformat.startswith('.'):
            tformat = '.' + tformat

        t = TemplateDirSource(template_dir)
        template_id = t.resolve_template_id(template_id + tformat)
        templates, params, attachments_all = t.get_all()
        # global assets and template specific assets
        attch = {**attachments_all[''], **attachments_all[template_id]} 
        if template_id not in params:
            params[template_id] = {k:None for k in t.find_undeclared_variables(templates[template_id])}

        template, params = templates[template_id], params[template_id]
        return DocTemplate(template, params, attch, t.env, template_id)

    @staticmethod
    def test_tid_exists(template_id:str, tformat='', template_dir=None):
        return test_template_exists(template_id, tformat, template_dir)
    
    @staticmethod
    def get_available_tids(template_dir=None):
        return TemplateDirSource(template_dir).get_template_ids()

    def __init__(self, template, params=None, attachments = None, env=None, template_id=None) -> None:
        """Initialize a DocTemplate instance.

        Args:
            template (str): A string representation of the template.
            params (dict, optional): A dictionary of parameters to be used in the template.
                If not provided, an empty dictionary is used.
            attachments (dict, optional): A dictionary of attachments to be used in the template.
                If not provided, an empty dictionary is used.
            env (Environment, optional): An instance of the jinja2 Environment class. NOT NEEDED. ONLY FOR CONVENIENCE
            template_id (str, optional): the actual template id for this template
        """
        self.template = template
        self.params = params if not params is None else {}
        self.attachments = attachments if not attachments is None else {}
        self.env = env or Environment()
        self.template_id = template_id

    def __str__(self):
        return f"TemplateObject(id={self.template_id}, template={self.template}, params.keys()={self.params.keys()})"

    def __repr__(self):
        return self.__str__()

    def find_undeclared_variables(self):
        """Find undeclared variables in the template.

        Returns:
            set: A set of undeclared variable names used in the template.
        """
        if self.env is None:
            raise ValueError("Environment is not set. Cannot find undeclared variables.")
        
        # 1. Safely extract the raw string source from the Template object
        source_str = None
        
        if hasattr(self.template, 'source') and self.template.source is not None:
            # Template was loaded directly from a string source
            source_str = self.template.source
        elif hasattr(self.template, 'filename') and self.template.filename is not None:
            # Template was loaded from a file; read its raw string representation
            with open(self.template.filename, "r", encoding="utf-8") as f:
                source_str = f.read()
        elif hasattr(self.template, 'name') and self.template.name is not None:
            # Fail-safe: ask the environment loader directly for the source
            try:
                source_str, _, _ = self.env.loader.get_source(self.env, self.template.name)
            except Exception:
                pass

        # If it was already a raw string passed to your class, use it directly
        if source_str is None and isinstance(self.template, str):
            source_str = self.template

        if source_str is None:
            raise ValueError("Could not extract raw source text from the provided template.")

        # 2. Parse the raw text string into an Abstract Syntax Tree (AST)
        ast = self.env.parse(source_str)
        return meta.find_undeclared_variables(ast)
    
    def render(self, **kwargs):
        """Render the Jinja2 template with given parameters.

        Args:
            **kwargs: Additional parameters to be used in the template.

        Returns:
            str: The rendered template as a string.
        """
        
        params = {**self.params, **kwargs}
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