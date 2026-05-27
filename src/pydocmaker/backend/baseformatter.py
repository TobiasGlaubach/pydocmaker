import abc
import traceback
import os
from typing import Tuple

from jinja2 import Template

def _handle_template(template, default_template) -> Tuple[Template, dict]:
    if template is None:
        template = default_template

    attachments = {}
    if hasattr(template, 'render'):
        template_obj = template
        template_str = ''
    elif isinstance(template, str) and os.path.exists(template):
        with open(template, 'r') as fp:
            template_str = fp.read()
            template_obj = Template(template_str)
    elif isinstance(template, str) and not template:
        template_str = '{{ body }}'
        template_obj = Template(template_str)
    elif isinstance(template, str):
        template_obj = Template(template)
        template_str = str(template)
    
    else:
        raise KeyError(f'Unknown template type! {type(template)=}')    
    return template_obj, attachments, template_str



class BaseFormatter(abc.ABC):

    default_linebreak = '\n\n'

    def digest_iterator(self, **kwargs):
        content = kwargs.get('children', kwargs.get('content'))
        return f''.join([self.digest(c) for c in content])

    def digest_str(self, el):
        return str(el)

    def digest_text(self, children='', **kwargs) -> list:
        return self.digest(children) # will result in digest_str being called
    
    def digest_line(self, **kwargs):
        return self.digest_text(**kwargs) 
    
    def digest_meta(self, **kwargs):
        return '' # meta element will not influence the rendering and is just ignored
    
    @abc.abstractmethod
    def digest_table(self, children=None, **kwargs) -> str:
        pass

    @abc.abstractmethod
    def digest_markdown(self, children='', **kwargs) -> str:
        pass

    @abc.abstractmethod
    def digest_image(self, children='', width=None, caption='', imageblob='', **kwargs) -> str:
        pass

    @abc.abstractmethod
    def digest_verbatim(self, children='', **kwargs) -> str:
        pass

    @abc.abstractmethod
    def digest_latex(self, children:str, **kwargs):
        pass

    def digest(self, children, **kwargs) -> str:
        try:

            if not isinstance(children, (str, dict, list)) and hasattr(children, 'dump'):
                children = children.dump()
            
            if not children:
                ret = ''
            elif isinstance(children, str):
                ret = self.digest_str(children)
            elif isinstance(children, dict) and children.get('typ', None) == 'meta':
                ret = self.digest_meta(children=children, **kwargs)
            elif isinstance(children, dict) and children.get('typ', None) == 'table':
                ret = self.digest_table(**children, **kwargs)
            elif isinstance(children, dict) and children.get('typ', None) == 'iter':
                ret = self.digest_iterator(children=children, **kwargs)
            elif isinstance(children, list) and children:
                ret = self.digest_iterator(children=children, **kwargs)
            elif isinstance(children, dict) and children.get('typ', None) == 'image':
                ret = self.digest_image(**children)
            elif isinstance(children, dict) and children.get('typ', None) == 'text':
                ret = self.digest_text(**children)
            elif isinstance(children, dict) and children.get('typ', None) == 'latex':
                ret = self.digest_latex(**children)
            elif isinstance(children, dict) and children.get('typ', None) == 'line':
                ret = self.digest_line(**children)
            elif isinstance(children, dict) and 'typ' in children and children['typ'] == 'verbatim':
                ret = self.digest_verbatim(**children)
            elif isinstance(children, dict) and 'typ' in children and children['typ'] == 'markdown':
                ret = self.digest_markdown(**children)
            else:
                ret = self.handle_error(f'the element of type {type(children)} {children=}, could not be parsed.', children)
            
            if isinstance(ret, str):
                linebreak = self.default_linebreak
                if isinstance(children, dict):
                    tmp = children.get('end', None) 
                    if not tmp is None:
                        linebreak = tmp

                tmp = kwargs.get('end', None) 
                if not tmp is None:
                    linebreak = tmp

                ret += linebreak

            return ret
        
        except Exception as err:
            return self.handle_error(err, children)


    def handle_error(self, err, el=None) -> list:
        e = str(el)
        if len(e) > 300:
            e = e[:300] + f'... (n={len(e)-300} more chars hidden)'

        txt = 'ERROR WHILE HANDLING ELEMENT:\n{}\n\n'.format(e)
        if not isinstance(err, str):
            txt += '\n'.join(traceback.format_exception(type(err), value=err, tb=err.__traceback__, limit=5))
        else:
            txt += err
        return self.digest_verbatim(children=(txt + '\n'), color='red')
    
        
    def format(self, doc:list) -> str:
        if hasattr(doc, 'dump'):
            doc = doc.dump()
        if not isinstance(doc, list):
            doc = [doc]
        return ''.join([self.digest(p) for p in doc])
    


    def _map_table2mat(self, children=None, fun=None, **kwargs) -> str:
        if children is None:
            children = [[]]

        if fun is None:
            fun = self.digest

        assert isinstance(children, (list, tuple)), f'children must be of type list! but was {type(children)=} {children=}'
        header = kwargs.get('header', None)
        header = list(header) if header else []

        assert isinstance(header, (list, tuple)), f'header must be of type list! but was {type(header)=} {header=}'
        data = list(children)
        wrong_rows = [row for row in children if not isinstance(row, (list, tuple))]
        assert not wrong_rows, f'all rows must be of type list! but found {wrong_rows=}'

        n_rows = kwargs.get('n_rows', None)
        if n_rows is None:
            n_rows = len(data)
        n_cols = kwargs.get('n_cols', None)
        if n_cols is None:
            n_cols = max(len(header), max([len(row) for row in data]))
        
        head = [fun(el) for el in header]
        if len(head) < n_cols:
            head += ['']*(n_cols-len(head))

        mat = []
        for i in range(n_rows):
            mat.append(['']*n_cols)

        for irow, row in enumerate(data):
            for icol, el in enumerate(row):
                mat[irow][icol] = fun(el)

        return head, mat
    