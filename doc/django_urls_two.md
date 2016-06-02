深入理解 django 的 urls 的实现 （二）
===================================

通过方法来处理 path 并返回处理后的数据
------------------------------------

  首先我将 url path 与它的处理方法对应起来， path 匹配的方式都采用正则表达式来做， 然后我将这些 URL 资源定位
相关的数据也告诉处理方法。

url_patterns



```

    import socket
    import socketserver
    
    from wsgiref import simple_server
    from django.utils.encoding import uri_to_iri
    from django.core.management.color import color_style
    from django.core.handlers.wsgi import ISO_8859_1, UTF_8
    from django.utils import six
    
    
    def is_broken_pipe_error():
        exc_type, exc_value = sys.exc_info()[:2]
        return issubclass(exc_type, socket.error) and exc_value.args[0] == 32
    
    
    class ServerHandler(simple_server.ServerHandler, object):
        def handle_error(self):
            # Ignore broken pipe errors, otherwise pass on
            if not is_broken_pipe_error():
                super(ServerHandler, self).handle_error()
    
    
    class WSGIServer(simple_server.WSGIServer, object):
        """BaseHTTPServer that implements the Python WSGI protocol"""
    
        request_queue_size = 10
    
        def __init__(self, *args, **kwargs):
            if kwargs.pop('ipv6', False):
                self.address_family = socket.AF_INET6
            super(WSGIServer, self).__init__(*args, **kwargs)
    
        def server_bind(self):
            """Override server_bind to store the server name."""
            super(WSGIServer, self).server_bind()
            self.setup_environ()
    
        def handle_error(self, request, client_address):
            if is_broken_pipe_error():
                sys.stderr.write("- Broken pipe from %s\n" % (client_address,))
            else:
                super(WSGIServer, self).handle_error(request, client_address)
                
                
    class WSGIRequestHandler(simple_server.WSGIRequestHandler, object):
    
        def __init__(self, *args, **kwargs):
            self.style = color_style()
            super(WSGIRequestHandler, self).__init__(*args, **kwargs)
    
        def address_string(self):
            # Short-circuit parent method to not call socket.getfqdn
            return self.client_address[0]
    
        def log_message(self, format, *args):
    
            msg = "[%s]" % self.log_date_time_string()
            try:
                msg += "%s\n" % (format % args)
            except UnicodeDecodeError:
                # e.g. accessing the server via SSL on Python 2
                msg += "\n"
    
            # Utilize terminal colors, if available
            if args[1][0] == '2':
                # Put 2XX first, since it should be the common case
                msg = self.style.HTTP_SUCCESS(msg)
            elif args[1][0] == '1':
                msg = self.style.HTTP_INFO(msg)
            elif args[1] == '304':
                msg = self.style.HTTP_NOT_MODIFIED(msg)
            elif args[1][0] == '3':
                msg = self.style.HTTP_REDIRECT(msg)
            elif args[1] == '404':
                msg = self.style.HTTP_NOT_FOUND(msg)
            elif args[1][0] == '4':
                # 0x16 = Handshake, 0x03 = SSL 3.0 or TLS 1.x
                if args[0].startswith(str('\x16\x03')):
                    msg = ("You're accessing the development server over HTTPS, "
                        "but it only supports HTTP.\n")
                msg = self.style.HTTP_BAD_REQUEST(msg)
            else:
                # Any 5XX, or any other response
                msg = self.style.HTTP_SERVER_ERROR(msg)
    
            sys.stderr.write(msg)
    
        def get_environ(self):
            # Strip all headers with underscores in the name before constructing
            # the WSGI environ. This prevents header-spoofing based on ambiguity
            # between underscores and dashes both normalized to underscores in WSGI
            # env vars. Nginx and Apache 2.4+ both do this as well.
            for k, v in self.headers.items():
                if '_' in k:
                    del self.headers[k]
    
            env = super(WSGIRequestHandler, self).get_environ()
    
            path = self.path
            if '?' in path:
                path = path.partition('?')[0]
    
            path = uri_to_iri(path).encode(UTF_8)
            # Under Python 3, non-ASCII values in the WSGI environ are arbitrarily
            # decoded with ISO-8859-1. We replicate this behavior here.
            # Refs comment in `get_bytes_from_wsgi()`.
            env['PATH_INFO'] = path.decode(ISO_8859_1) if six.PY3 else path
    
            return env
    
        def handle(self):
            """Copy of WSGIRequestHandler, but with different ServerHandler"""
    
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(414)
                return
    
            if not self.parse_request():  # An error code has been sent, just exit
                return
    
            handler = ServerHandler(
                self.rfile, self.wfile, self.get_stderr(), self.get_environ()
            )
            handler.request_handler = self      # backpointer for logging
            handler.run(self.server.get_app())
    
    
    def run(addr, port, application, ipv6=False, threading=False):
        server_address = (addr, port)
        http_cls = type(str('WSGIServer'), (socketserver.ThreadingMixIn, WSGIServer), {})
        httpd = http_cls(server_address, WSGIRequestHandler)
        httpd.set_app(application)
        httpd.serve_forever()
```

这里对这个 wsgi 服务器稍做解释， 首先通过元类编程，将 WSGIServer 扩展成为一个多线程处理的服务器， 
然后指定请求处理类 WSGIRequestHandler， 这个请求处理类会委托 application 来处理请求， application 必须是满足 wsgi 协议的， 即
它必须接受两个位置参数，习惯的叫它们 environ 和 start_response, 这里的命名是可以随便取，只是按照惯例这么取名的，根据 wsgi 协议， 
服务器或网关必须用到这两个位置参数， environ 是一个字典对象， 它包含一些特定的 wsgi 协议所需的变量，也可以包含一些服务器的相关变量。
而 start_response 参数是一个可调用者， 它接受两个必要的位置参数和一个可选参数， 习惯性命名为 status, response_headers 和 exc_info
, status参数是一个形式如 `200 OK` 这样的状态字符串。而 response_headers 参数是一个包含有 `(header_name,header_value)
参数列表的元组`，用来描述HTTP的响应头. exc_info 不考虑， 另外 wsgi 还规定了 application 必须返回一个可迭代的值。
如对 application 有疑问， 可以查询 PEP333 来详细了解 wsgi 协议的内容。
  

定义满足 wsgi 的 application 方法
--------------------------------

按照上面所说， 那么接下来我就要实现这么一个 application ， 以方便我测试服务器以及进行后期的升级改造

首先新建一个 python 文件， 叫它 my_wsgi.py , 在文件中添加一个 application 方法：

```

    def application(environ, start_response):
        start_response('200 OK', [('content-type', 'text/html')])
        return [b'Hello World! ']
        
```

然后我在 run_server.py 中测试一下，加入如下代码:

```

    if __name__ == '__main__':
        import sys
        sys.path.insert(0, r'D:\learn_django_urls')
        from learn_django_urls.my_wsgi import application
        run('127.0.0.1', 8003, application)
        
```

我将当前项目加入到路径加入到 PYTHONPATH 中， 然后我在 8003 端口启动服务，测试一下

```
    curl -G  http://127.0.0.1:8003
```

返回了 Hello World!

想象一下现在我的 application 是固定的， 我想要根据请求的 path 不同，然后返回的内容不同， 这就是 django 的 url 实现的开始:
根据 wsgi 协议， 知道 path 是存放在 environ 的 PATH_INFO 当中， 它是要给字符串类型, 修改 application 方法如下:

```

    def application(environ, start_response):
        path = environ['PATH_INFO']
        if path == '/':
            data = [b'root path']
        elif path == '/path1':
            data = [b'get path1 information']
        elif path == '/path2':
            data = [b'get path2 information']
        else:
            data = [b'404 error']
    
        if data == [b'404 error']:
            status = '404 PATH NOT FOUND ERROR'
        else:
            status = '200 OK'
    
        start_response(status, [('content-type', 'text/html')])
    
        return data
  
```

测试结果如下:

```

    curl -G http://127.0.0.1:8003
        root path
    curl -G http://127.0.0.1:8003/path1
        get path1 information
    curl -G http://127.0.0.1:8003/path2
        get path2 information
    curl -G http://127.0.0.1:8003/invalid_path
        404 error

```


增加 HttpResponse
--------------------------------


显然我的这个 application 太不合情理了， 虽然返回一个 iterator 数据， 但它不够灵活， 应该让返回的数据决定它的状态和要返回的 http
头部信息才对， 而且编码处理也应该由响应自己完成才对， 总之我要一个响应对应一个响应对象，并且这个对象是可迭代的，而且可以指定内容，
状态码，编码，头部，cookie信息等，那么我主要考察的是 url 的实现， 因此我也可以去拿 django HttpResponse 稍作修改就好， 
我把跟 settings 有关的内容固定下来, 在 my_wsgi 文件中添加如下代码:

```

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

```


django 的 HttpResponse 做为 http 的响应体基类， 其他针对于不同的状态码定义了不同的响应类它们都是 HttpResponse 的子类，这样
做的好处就是见名知意， 像 django 中的异常也是这么来做的， 这符合 python 哲学，HttpResponseNotFound 针对于找不到这样请求路径时
使用。 那么接下来就可以修改 application 的代码的返回为响应体了。

```

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
    
```

在原来的基础上， 我将返回数据变得更像网页类服务器所返回的数据，在上面加了一些 `html` 标记， 然后稍微的重构了下， 这样 application
的负担就减轻了， 那我就可以专注于请求路径上面了.

结束语
-------

那现在一切都以准备就绪了， 那接下来要关注的就是针对于不同的路径来生成内容了， 在访问服务器的时候， 除了不一样的路径， 还有
url 参数, 查询字符串等，它们也是 http 定位资源的一部分， 因此也要将它们考虑进来， 另外就算是路径，一个网站的路径成千上万，
不可能都if， else来实现吧， 那好用字典吧，将路径与返回的数据一一对应起来不就行了嘛， 这样做应该没有问题的， 但很多时候它会
变得不方便， 比如一个路径 /path/id , 这个id 从 1 到 100 都是合法的，那是不是要写个方法，将它逐一添加到这个路径字典中了，
如果 1 到 100 的路径是其他一样的数据了， 显然这样做冗余太大了， 并且针对于不同的路径可能要编写不同的方法来将这些路径添加到
这个字典中来， 因此就有了正则表达式来判断路径对应返回的数据的念头了， 这也正式 django 框架采用的方法，它足够灵活，以及足够的性能。







