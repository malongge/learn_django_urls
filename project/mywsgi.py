import re

from project.urlsconf import url_patterns
from project.response import HttpResponseNotFound, HttpResponseServerError
from project.exceptions import Http404


def application(environ, start_response):

    try:
        response = path_to_response(environ)
    except Http404:
        response = HttpResponseNotFound('<p style="color:red;">path not found error</p>')
    except Exception:
        response = HttpResponseServerError('error occur in server')

    status = '%s %s' % (response.status_code, response.reason_phrase)
    response_headers = [(str(k), str(v)) for k, v in response.items()]
    for c in response.cookies.values():
        response_headers.append((str('Set-Cookie'), str(c.output(header=''))))
    start_response(status, response_headers)
    return response

# first_pattern = re.compile(r'/')

def path_to_response(environ):

    path = environ['PATH_INFO']
    # match = path[1:]

    new_path = path[1:]
    # callback = None
    # args = None
    # kwargs = None
    for pattern_object in url_patterns:
        # compiled_regex = re.compile(pattern, re.UNICODE)
        # match = pattern_object.regex.search(path)
        # if match:
        #     kwargs = match.groupdict()
        #     args = () if kwargs else match.groups()
        #     return pattern_object.callback(environ, *args, **kwargs)
        obj = pattern_object.resolve(new_path)
        if obj:
            callback, args, kwargs = obj
            return callback(environ, *args, **kwargs)

    raise Http404




