import datetime
import sys
import re

from django.utils import six,  timezone
from http.client import responses
from email.header import Header

_charset_from_content_type_re = re.compile(r';\s*charset=(?P<charset>[^\s;]+)', re.I)


class HttpResponseBase(six.Iterator):
    """
    An HTTP response base class with dictionary-accessed headers.

    This class doesn't handle content. It should not be used directly.
    Use the HttpResponse and StreamingHttpResponse subclasses instead.
    """

    status_code = 200

    def __init__(self, content_type=None, status=None, reason=None, charset=None):
        # _headers is a mapping of the lower-case name to the original case of
        # the header (required for working with legacy systems) and the header
        # value. Both the name of the header and its value are ASCII strings.
        self._headers = {}
        self._closable_objects = []
        # This parameter is set by the handler. It's necessary to preserve the
        # historical behavior of request_finished.
        self._handler_class = None
        self.cookies = {}
        self.closed = False
        if status is not None:
            self.status_code = status
        self._reason_phrase = reason
        self._charset = charset
        if content_type is None:
            content_type = '%s; charset=%s' % ('text/html',
                                               self.charset)
        self['Content-Type'] = content_type

    @property
    def reason_phrase(self):
        if self._reason_phrase is not None:
            return self._reason_phrase
        # Leave self._reason_phrase unset in order to use the default
        # reason phrase for status code.
        return responses.get(self.status_code, 'Unknown Status Code')

    @reason_phrase.setter
    def reason_phrase(self, value):
        self._reason_phrase = value

    @property
    def charset(self):
        if self._charset is not None:
            return self._charset
        content_type = self.get('Content-Type', '')
        matched = _charset_from_content_type_re.search(content_type)
        if matched:
            # Extract the charset and strip its double quotes
            return matched.group('charset').replace('"', '')
        return 'utf-8'

    @charset.setter
    def charset(self, value):
        self._charset = value

    def serialize_headers(self):
        """HTTP headers as a bytestring."""
        def to_bytes(val, encoding):
            return val if isinstance(val, bytes) else val.encode(encoding)

        headers = [
            (b': '.join([to_bytes(key, 'ascii'), to_bytes(value, 'latin-1')]))
            for key, value in self._headers.values()
        ]
        return b'\r\n'.join(headers)

    if six.PY3:
        __bytes__ = serialize_headers
    else:
        __str__ = serialize_headers

    def _convert_to_charset(self, value, charset, mime_encode=False):
        """Converts headers key/value to ascii/latin-1 native strings.

        `charset` must be 'ascii' or 'latin-1'. If `mime_encode` is True and
        `value` can't be represented in the given charset, MIME-encoding
        is applied.
        """
        if not isinstance(value, (bytes, six.text_type)):
            value = str(value)
        if ((isinstance(value, bytes) and (b'\n' in value or b'\r' in value)) or
                isinstance(value, six.text_type) and ('\n' in value or '\r' in value)):
            raise ValueError("Header values can't contain newlines (got %r)" % value)
        try:
            if six.PY3:
                if isinstance(value, str):
                    # Ensure string is valid in given charset
                    value.encode(charset)
                else:
                    # Convert bytestring using given charset
                    value = value.decode(charset)
            else:
                if isinstance(value, str):
                    # Ensure string is valid in given charset
                    value.decode(charset)
                else:
                    # Convert unicode string to given charset
                    value = value.encode(charset)
        except UnicodeError as e:
            if mime_encode:
                # Wrapping in str() is a workaround for #12422 under Python 2.
                value = str(Header(value, 'utf-8', maxlinelen=sys.maxsize).encode())
            else:
                e.reason += ', HTTP response headers must be in %s format' % charset
                raise
        return value

    def __setitem__(self, header, value):
        header = self._convert_to_charset(header, 'ascii')
        value = self._convert_to_charset(value, 'latin-1', mime_encode=True)
        self._headers[header.lower()] = (header, value)

    def __delitem__(self, header):
        try:
            del self._headers[header.lower()]
        except KeyError:
            pass

    def __getitem__(self, header):
        return self._headers[header.lower()][1]

    def has_header(self, header):
        """Case-insensitive check for a header."""
        return header.lower() in self._headers

    __contains__ = has_header

    def items(self):
        return self._headers.values()

    def get(self, header, alternate=None):
        return self._headers.get(header.lower(), (None, alternate))[1]

    def set_cookie(self, key, value='', max_age=None, expires=None, path='/',
                   domain=None, secure=False, httponly=False):
        """
        Sets a cookie.

        ``expires`` can be:
        - a string in the correct format,
        - a naive ``datetime.datetime`` object in UTC,
        - an aware ``datetime.datetime`` object in any time zone.
        If it is a ``datetime.datetime`` object then ``max_age`` will be calculated.

        """
        value = str(value)
        self.cookies[key] = value
        if expires is not None:
            if isinstance(expires, datetime.datetime):
                if timezone.is_aware(expires):
                    expires = timezone.make_naive(expires, timezone.utc)
                delta = expires - expires.utcnow()
                # Add one second so the date matches exactly (a fraction of
                # time gets lost between converting to a timedelta and
                # then the date string).
                delta = delta + datetime.timedelta(seconds=1)
                # Just set max_age - the max_age logic will set expires.
                expires = None
                max_age = max(0, delta.days * 86400 + delta.seconds)
            else:
                self.cookies[key]['expires'] = expires
        if max_age is not None:
            self.cookies[key]['max-age'] = max_age
            # IE requires expires, so set it if hasn't been already.
            if not expires:
                # self.cookies[key]['expires'] = cookie_date(time.time() + max_age)
                pass

        if path is not None:
            self.cookies[key]['path'] = path
        if domain is not None:
            self.cookies[key]['domain'] = domain
        if secure:
            self.cookies[key]['secure'] = True
        if httponly:
            self.cookies[key]['httponly'] = True

    def setdefault(self, key, value):
        """Sets a header unless it has already been set."""
        if key not in self:
            self[key] = value

    def set_signed_cookie(self, key, value, salt='', **kwargs):
        # value = signing.get_cookie_signer(salt=key + salt).sign(value)
        return self.set_cookie(key, value, **kwargs)

    def delete_cookie(self, key, path='/', domain=None):
        self.set_cookie(key, max_age=0, path=path, domain=domain,
                        expires='Thu, 01-Jan-1970 00:00:00 GMT')

    # Common methods used by subclasses

    def make_bytes(self, value):
        """Turn a value into a bytestring encoded in the output charset."""
        # Per PEP 3333, this response body must be bytes. To avoid returning
        # an instance of a subclass, this function returns `bytes(value)`.
        # This doesn't make a copy when `value` already contains bytes.

        # Handle string types -- we can't rely on force_bytes here because:
        # - under Python 3 it attempts str conversion first
        # - when self._charset != 'utf-8' it re-encodes the content
        if isinstance(value, bytes):
            return bytes(value)
        if isinstance(value, six.text_type):
            return bytes(value.encode(self.charset))

        # Handle non-string types (#16494)
        return bytes(value, self.charset)

    # These methods partially implement the file-like object interface.
    # See http://docs.python.org/lib/bltin-file-objects.html

    # The WSGI server must call this method upon completion of the request.
    # See http://blog.dscpl.com.au/2012/10/obligations-for-calling-close-on.html
    def close(self):
        for closable in self._closable_objects:
            try:
                closable.close()
            except Exception:
                pass
        self.closed = True
        # signals.request_finished.send(sender=self._handler_class)

    def write(self, content):
        raise IOError("This %s instance is not writable" % self.__class__.__name__)

    def flush(self):
        pass

    def tell(self):
        raise IOError("This %s instance cannot tell its position" % self.__class__.__name__)

    # These methods partially implement a stream-like object interface.
    # See https://docs.python.org/library/io.html#io.IOBase

    def writable(self):
        return False

    def writelines(self, lines):
        raise IOError("This %s instance is not writable" % self.__class__.__name__)


class HttpResponse(HttpResponseBase):
    """
    An HTTP response class with a string as content.

    This content that can be read, appended to or replaced.
    """

    streaming = False

    def __init__(self, content='', *args, **kwargs):
        super(HttpResponse, self).__init__(*args, **kwargs)
        # Content is a bytestring. See the `content` property methods.
        self.content = content

    def serialize(self):
        """Full HTTP message, including headers, as a bytestring."""
        return self.serialize_headers() + b'\r\n\r\n' + self.content

    if six.PY3:
        __bytes__ = serialize
    else:
        __str__ = serialize

    @property
    def content(self):
        return b''.join(self._container)

    @content.setter
    def content(self, value):
        # Consume iterators upon assignment to allow repeated iteration.
        if hasattr(value, '__iter__') and not isinstance(value, (bytes, six.string_types)):
            if hasattr(value, 'close'):
                self._closable_objects.append(value)
            value = b''.join(self.make_bytes(chunk) for chunk in value)
        else:
            value = self.make_bytes(value)
        # Create a list of properly encoded bytestrings to support write().
        self._container = [value]

    def __iter__(self):
        return iter(self._container)

    def write(self, content):
        self._container.append(self.make_bytes(content))

    def tell(self):
        return len(self.content)

    def getvalue(self):
        return self.content

    def writable(self):
        return True

    def writelines(self, lines):
        for line in lines:
            self.write(line)


class HttpResponseNotFound(HttpResponse):
    status_code = 404

#
# def application(environ, start_response):
#     start_response('200 OK', [('content-type', 'text/html')])
#     return [b'Hello World! ']


# def application(environ, start_response):
#     path = environ['PATH_INFO']
#     if path == '/':
#         data = [b'root path']
#     elif path == '/path1':
#         data = [b'get path1 information']
#     elif path == '/path2':
#         data = [b'get path2 information']
#     else:
#         data = [b'404 error']
#
#     if data == [b'404 error']:
#         status = '404 PATH NOT FOUND ERROR'
#     else:
#         status = '200 OK'
#
#     start_response(status, [('content-type', 'text/html')])
#
#     return data

def index(environ, *args, **kwargs):
    print('<h1>root path</h1>')

def show_path(environ, *args, **kwargs):
    print('<p>get path1 information</p>')

url_patterns = [
    ('^/$', index),
    ('^/path[1,2]$', show_path)
]

def application(environ, start_response):
    response = path_to_response(environ)
    status = '%s %s' % (response.status_code, response.reason_phrase)
    response_headers = [(str(k), str(v)) for k, v in response.items()]
    for c in response.cookies.values():
        response_headers.append((str('Set-Cookie'), str(c.output(header=''))))
    start_response(status, response_headers)
    return response


def path_to_response(environ):
    path = environ['PATH_INFO']
    path_not_found = False
    data = ''
    if path == '/':
        data = '<h1>root path</h1>'
    elif path == '/path1':
        data = '<p>get path1 information</p>'
    elif path == '/path2':
        data = '<p>get path2 information</p>'
    else:
        path_not_found = True
    if path_not_found:
        response = HttpResponseNotFound('<p style="color:red;">path not found error</p>')
    else:
        response = HttpResponse(data)
    return response