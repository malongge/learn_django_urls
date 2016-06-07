from project.urlsconf import url

url_patterns = [
    url(r'^$', lambda version, *args, **kwargs: '<h1>sub path test with root number: {}</h1>'.format(kwargs['root'])),
    url(r'^subdpath(?P<subdpath>[1,2])$',
        lambda version, *args, **kwargs: '<p>sub dpath number: {}</p>'.format(kwargs['subdpath']))
]