# Unit test package with Python 3.14 Django compatibility patch
from django.template.context import BaseContext

def safe_context_copy(self):
    """
    Python 3.14 compatible shallow copy of Django template context.
    Avoids calling super().__copy__() which fails on Python 3.14 object behavior.
    """
    new_context = self.__class__.__new__(self.__class__)
    new_context.dicts = self.dicts[:]
    return new_context

BaseContext.__copy__ = safe_context_copy
