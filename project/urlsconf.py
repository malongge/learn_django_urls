from project.views import index_view, path_view
import re
from .exceptions import ImproperlyConfigured
from django.utils.functional import cached_property


class RegexURLPattern(object):

    def __init__(self, regex, callback):
        self._regex = regex
        self.callback = callback

    @cached_property
    def regex(self):
        try:
            return re.compile(self._regex, re.UNICODE)
        except re.error as e:
            raise ImproperlyConfigured('"%s" is not a valid regular expression: %s' % (self._regex, e))

    def __repr__(self):
        return 'RegexURLPattern instance regex is: {}, callback name is: {}'.format(self._regex, self.callback.__name__)

    def __str__(self):
        return self.__repr__()


def url(regex: str, view):

    if not regex or not isinstance(regex, str):
        raise ImproperlyConfigured('{} is empty or invalid'.format(regex))
    # try:
    #     re.compile(regex)
    # except re.error as e:
    #     raise ImproperlyConfigured('"%s" is not a valid regular expression: %s' % (regex, e))

    if not callable(view):
        raise ImproperlyConfigured('URL pattern：{} view is not callable'.format(regex))

    return RegexURLPattern(regex, view)

url_patterns = [
    url('^/$', index_view),
    url('^/path([1,2])$', path_view)
]