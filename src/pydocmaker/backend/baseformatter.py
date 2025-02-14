import abc
import traceback



class BaseFormatter(abc.ABC):
    @abc.abstractmethod
    def digest_markdown(self, children='', **kwargs) -> str:
        pass

    @abc.abstractmethod
    def digest_image(self, children='', width=0.8, caption='', imageblob='', **kwargs) -> str:
        pass

    @abc.abstractmethod
    def digest_verbatim(self, children='', **kwargs) -> str:
        pass

    @abc.abstractmethod
    def digest_iterator(self, el) -> str:
        pass

    def digest_str(self, el):
        return el

    @abc.abstractmethod
    def digest_text(self, children:str, **kwargs):
        pass

    @abc.abstractmethod
    def digest_latex(self, children:str, **kwargs):
        pass

    @abc.abstractmethod
    def digest_line(self, children:str, **kwargs):
        pass

    def digest(self, el, **kwargs) -> list:
        try:
            
            if not el:
                return ''
            elif isinstance(el, str):
                ret = self.digest_str(el)
            elif isinstance(el, dict) and 'typ' in el and el['typ'] == 'iter':
                ret = self.digest_iterator(el)
            elif isinstance(el, list) and el:
                ret = self.digest_iterator(el)
            elif isinstance(el, dict) and 'typ' in el and el['typ'] == 'image':
                ret = self.digest_image(**el)
            elif isinstance(el, dict) and 'typ' in el and el['typ'] == 'text':
                ret = self.digest_text(**el)
            elif isinstance(el, dict) and el.get('typ', None) == 'latex':
                ret = self.digest_latex(**el)
            elif isinstance(el, dict) and el.get('typ', None) == 'line':
                ret = self.digest_line(**el)
            elif isinstance(el, dict) and 'typ' in el and el['typ'] == 'verbatim':
                ret = self.digest_verbatim(**el)
            elif isinstance(el, dict) and 'typ' in el and el['typ'] == 'markdown':
                ret = self.digest_markdown(**el)
            else:
                return self.handle_error(f'the element of type {type(el)} {el=}, could not be parsed.')
            
            return ret
        
        except Exception as err:
            return self.handle_error(err, el)


    @abc.abstractmethod
    def format(self, doc:list) -> str:
        pass
    
    def format(self, doc:list):
        raise NotImplementedError()
    
    @abc.abstractmethod
    def handle_error(self, err, el) -> list:
        pass
