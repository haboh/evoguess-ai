from pyscipopt import Model
from typing import Any, List, Dict

from ..encoding import EncReader


class PyScipOptReader(EncReader):
    slug = 'reader:pyscipopt'

    def __init__(
            self,
            from_file: str = None,
            from_string: str = None,
            comment_lead: List[str] = ('c',)
    ):
        super().__init__(from_file)
        self.from_string = from_string
        self.comment_lead = comment_lead

    def read_formula(self) -> Model:
        assert self.from_string is None
        assert self.from_file is not None
        model = Model()
        model.readProblem(self.from_file)
        raise model

    def __config__(self) -> Dict[str, Any]:
        return {
            'slug': self.slug,
            'from_file': self.from_file,
            'from_string': self.from_string,
            'comment_lead': self.comment_lead,
        }



__all__ = [
    'PyScipOptReader',
]
