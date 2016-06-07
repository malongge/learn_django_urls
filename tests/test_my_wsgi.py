from project import mywsgi
import pytest
from project.exceptions import Http404, ImproperlyConfigured
from project.response import HttpResponseServerError, HttpResponseNotFound
from project.urlsconf import url

def test_application(monkeypatch):

    def view1(environ):
        raise ValueError('test')

    def view2(environ):
        raise Http404

    def start_response(param1, param2):
        pass

    monkeypatch.setattr(mywsgi, 'path_to_response', view1)
    assert isinstance(mywsgi.application(None, start_response), HttpResponseServerError)

    monkeypatch.setattr(mywsgi, 'path_to_response', view2)
    assert isinstance(mywsgi.application(None, start_response), HttpResponseNotFound)


def test_path_to_response(monkeypatch):

    url_patterns = [
        url('^$', lambda version, *args, **kwargs: '<h1>root path test</h1>'),
        url('^path([1,2])$', lambda version, *args, **kwargs: '<p>get path{} test information</p>'.format(args[0]))
    ]

    monkeypatch.setattr(mywsgi, "url_patterns", url_patterns)

    assert mywsgi.path_to_response({'PATH_INFO': '/'}) == '<h1>root path test</h1>'
    assert mywsgi.path_to_response({'PATH_INFO': '/'}) != '<h1>root path tes</h1>'
    assert mywsgi.path_to_response({'PATH_INFO': '/path1'}) == '<p>get path1 test information</p>'

    with pytest.raises(Http404):
        mywsgi.path_to_response({'PATH_INFO': '/path3'})


from project.urlsconf import url


def _temp_func(version, *args, **kwargs):
        return '<h1>root path test</h1>'


def test_url_function():

    with pytest.raises(ImproperlyConfigured):
        url(None, _temp_func)

    with pytest.raises(ImproperlyConfigured):
        url([1, 2, 3], _temp_func)

    with pytest.raises(ImproperlyConfigured):
        url('^/path([1,2])$', None)


from project.urlsconf import RegexURLPattern, include, RegexURLPatternList
from tests.urls_config import url_patterns


def test_regex_url_pattern_class():

    with pytest.raises(ImproperlyConfigured):
        RegexURLPattern(r'^d({1,-1}$', _temp_func).regex


def test_regex_url_pattern_list_class():
    assert {'root': '1'} == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/')[2]
    assert {'root': '1'} == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/path1')[2]
    assert ('1',) == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/path1')[1]
    assert ('1', '1') == RegexURLPatternList(r'^root([1,2])/', url_patterns).resolve('root1/path1')[1]
    assert {'root': '1', 'dpath': '1'} == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/dpath1')[2]
    assert {'root': '1', 'dpath': '1', 'subdpath': '1'} \
           == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/sdpath1/subdpath1')[2]


def test_include_func():
    assert include('tests.urls_config') == url_patterns


def test_path_to_response_with_include_url_patterns(monkeypatch):

    url_patterns = [
        url('^root(?P<root>[1,2])/', include('tests.urls_config'))
    ]
    monkeypatch.setattr(mywsgi, "url_patterns", url_patterns)
    assert mywsgi.path_to_response({'PATH_INFO': '/root1/sdpath1/subdpath1'}) == '<p>sub dpath number: 1</p>'

    with pytest.raises(Http404):
        mywsgi.path_to_response({'PATH_INFO': '/root1/sdpath/subdpath1'})



