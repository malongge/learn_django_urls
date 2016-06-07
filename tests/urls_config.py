from project.urlsconf import url, include

url_patterns = [
    url(r'^$', lambda version, *args, **kwargs: '<h1>sub path test with root number: {}</h1>'.format(kwargs['root'])),
    url(r'^path([1,2])$', lambda version, *args, **kwargs:
        '<p>get sub /root{}/path{} test information</p>'.format(args[0], args[1])),
    url(r'^dpath(?P<dpath>[1,2])$', lambda version, *args, **kwargs:
        '<p>get sub /root{}/dpath{} test information</p>'.format(kwargs['root'], kwargs['dpath'])),
    url(r'^sdpath(?P<dpath>[1,2])/', include('tests.include_to_urls_conf'))
]