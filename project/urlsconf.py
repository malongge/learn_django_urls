from project.views import index_view, path_view
import re
from .exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from project.exceptions import Http404


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

    def resolve(self, path):
        match = self.regex.search(path)

        if match:
            kwargs = match.groupdict()
            args = () if kwargs else match.groups()
            return self.callback, args, kwargs


class RegexURLPatternList(object):

    def __init__(self, regex, patterns):
        self._regex = regex
        self.patterns = patterns

    @cached_property
    def regex(self):
        try:
            return re.compile(self._regex, re.UNICODE)
        except re.error as e:
            raise ImproperlyConfigured('"%s" is not a valid regular expression: %s' % (self._regex, e))

    def __repr__(self):
        return 'RegexURLPattern instance regex is: {}, for sub pattern list'.format(self._regex)

    def __str__(self):
        return self.__repr__()

    def resolve(self, path):
        # import pdb
        # pdb.set_trace()
        match = self.regex.search(path)

        if match:
            new_path = path[match.end():]

            for pattern in self.patterns:
                sub_match = pattern.resolve(new_path)
                if sub_match:
                    sub_match_dict = dict(match.groupdict(), **sub_match[2])
                    sub_match_args = match.groups()
                    if not sub_match_dict:
                        sub_match_args += sub_match[1]

                    return sub_match[0], sub_match_args, sub_match_dict

        #     raise Http404
        # raise Http404

from importlib import import_module

def include(module_path):
    if not module_path:
        raise ImproperlyConfigured('include url pattern config should not empty')
    if isinstance(module_path, str):
        url_conf_module = import_module(module_path)
        patterns = getattr(url_conf_module, 'url_patterns')
        return patterns
    raise ImproperlyConfigured("include url pattern config should be "
                               "a string but it's type is {}".format(type(module_path)))

def url(regex: str, view):

    if not regex or not isinstance(regex, str):
        raise ImproperlyConfigured('{} is empty or invalid'.format(regex))
    # try:
    #     re.compile(regex)
    # except re.error as e:
    #     raise ImproperlyConfigured('"%s" is not a valid regular expression: %s' % (regex, e))
    if isinstance(view, (list, tuple)):
        return RegexURLPatternList(regex, view)

    if not callable(view):
        raise ImproperlyConfigured('URL pattern：{} view is not callable'.format(regex))

    return RegexURLPattern(regex, view)

url_patterns = [
    url('^$', index_view),
    url('^path([1,2])$', path_view)
]