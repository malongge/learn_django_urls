深入理解 django 的 urls 的实现 （二）
===================================

通过函数来处理 path 并返回处理后的数据
------------------------------------

  首先我将 url path 与它的处理函数对应起来， path 匹配的方式都采用正则表达式来做， 然后我将这些 URL 资源定位
相关的数据也告诉处理函数。

在这之前，我需要了解一点正则表达式知识， 比如在路径里面需要将变量扩起来是为了进行分组，这样不但匹配了路径还可以提取匹配模式的内容，
另外路径中使用?P<alias name>这样的模式除了分组之外，还给每个组取了个别名，这样就可以像字典一样找到对应的匹配内容了

下面对应着，不分组，分组，分组取别名的情况

```
    
    >>> import re
    
    >>> pat = re.compile('^/path[1,2]$')
    >>> pat.search('/path1').groups()
    ()
    
    >>> pat = re.compile('^/path([1,2])$')
    >>> pat.search('/path1').groups()
    ('1',)
    
    >>>pat = re.compile('^/path(?P<num>[1,2])$')
    >>> pat.search('/path1').groupdict()
    {'num': '1'}

```

现在将路径独立出来进行配置, 并修改 path_to_response 函数

```

    url_patterns = [
        ('^/$', index_view),
        ('^/path([1,2])$', path_view)
    ]
    
    def path_to_response(environ):

    path = environ['PATH_INFO']

    for pattern, view in url_patterns:
        compiled_regex = re.compile(pattern, re.UNICODE)
        match = compiled_regex.search(path)
        if match:
            kwargs = match.groupdict()
            args = () if kwargs else match.groups()
            return view(environ, *args, **kwargs)

    return HttpResponseNotFound('<p style="color:red;">path not found error</p>')

```

现在我继续测试一下， 如果每次都要自己测试一遍的话，比较麻烦， 因此可以加上单元测试，让程序做这个事情

增加单元测试处理
-----------------

这里使用 pytest , 使用 pip 安装即可
 
创建一个pytest的配置文件 pytest.ini, 配置它去搜索的目录为 tests，以及有两个失败的单元测试之后，就
停止测试

```
    [pytest]
    python_paths = .
    addopts = --maxfail=2 -rf
    testpaths = tests

```

为了更好的单元测试，我创建一个 urlsconf.py 然后将配置路径移过去，这样就可以通过 monkey patch的
形式就可以替换我的配置路径了， 同时重构下目录和文件名，让项目代码独立放到 project, 并且更加符合pep
8源文件命名（无下划线全小写)的风格.接着把 view 的代码和Response也分别独立放一个文件 views.py 和
response.py

首先在 tests 的 __init__.py 文件中，将项目加到 PYTHONPATH 中，以便 pytest 可以找到

```

    import sys, os
    myPath = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, myPath + '/../')

```

创建一个测试文件 test_my_wsgi.py, 加上我的单元测试

```
    from project import mywsgi


    def test_path_to_response(monkeypatch):
    
        url_patterns = [
            ('^/$', lambda version, *args, **kwargs: '<h1>root path test</h1>'),
            ('^/path([1,2])$', lambda version, *args, **kwargs: '<p>get path{} test information</p>'.format(args[0]))
        ]
    
        monkeypatch.setattr(mywsgi, "url_patterns", url_patterns)
    
        assert mywsgi.path_to_response({'PATH_INFO': '/'}) == '<h1>root path test</h1>'
        assert mywsgi.path_to_response({'PATH_INFO': '/'}) != '<h1>root path tes</h1>'
        assert mywsgi.path_to_response({'PATH_INFO': '/path1'}) == '<p>get path1 test information</p>'
        assert mywsgi.path_to_response({'PATH_INFO': '/path3'}) == '<p style="color:red;">path not found error</p>'

```

当我使用 py.test 命令执行测试的时候， 测试未通过

>   
    E        assert <project.response.HttpResponseNotFound object at 0x035A70D0> == '<p style="color:red;">path not found error</p>'
    E        +  where <project.response.HttpResponseNotFound object at 0x035A70D0> = <function path_to_response at 0x030F1618>({'PATH_INF
    O': '/path3'})
    E        +    where <function path_to_response at 0x030F1618> = mywsgi.path_to_response


增加程序的健壮性同时重构 404 问题
--------------------------------

那么这说明， 在路径找不到的时候，它的处理与 正常的 path 的 view 不一致， 这里我应该修改它，使其与
其他正常 view 一样才行， 按照 django 的设计思想是找不到这样的路径将抛出异常，然后捕获这个异常进行处理， 还有这里的 url 正则表达式不用
每次请求都进行编译，只要配置好，编译一次就够了， 另外除了路径找不到的问题，还会有其他的问题，比如程序出现异常， 所以采用捕获异常的方式
可以根据不同的异常，来得到不同的响应。只有正常的情况下才返回 view. 那么修改单元测试为:

```
    ... ...
    with pytest.raises(Http404):
        mywsgi.path_to_response({'PATH_INFO': '/path3'})

```

修改 application 函数为:

```

    try:
        response = path_to_response(environ)
    except Http404:
        response = HttpResponseNotFound('<p style="color:red;">path not found error</p>')
    except Exception:
        response = HttpResponseServerError('error occur in server')

```

为 application 增加一个单元测试:

```

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

```

注意我这里增加了一个 exceptions.py 模块和一个 HttpResponseServerError 响应, 单元测试了下一切正常。

重构 url 匹配
--------------

接下来要重构一下， url 匹配这一块代码， 提高匹配性能， 路径判断， 更加优雅的拓展 url 的配置.
除了上述想要的目标， 还应该检查 url 配置正确性。

首先在配置的时候，加一层壳，用于检查 url 的配置正确性, 如果配置不正确， 增加一个抛出异常
exceptions.py

```

    class ImproperlyConfigured(Exception):
        """Django is somehow improperly configured"""
        pass

```

在这个 url 函数中， 对正则表达式判断和编译，以及 view 是否为函数进行判断
urlsconf.py

```

    def url(regex: str, view):

        if not regex or not isinstance(regex, str):
            raise ImproperlyConfigured('{} is empty or invalid'.format(regex))
        try:
            re.compile(regex)
        except re.error as e:
            raise ImproperlyConfigured('"%s" is not a valid regular expression: %s' % (regex, e))
    
        if not callable(view):
            raise ImproperlyConfigured('URL pattern：{} view is not callable'.format(regex))
    
        return RegexURLPattern(regex, view)
    
```

修改 path_to_response 函数， 来满足这个 url 函数

```

    def path_to_response(environ):

        path = environ['PATH_INFO']
    
        for pattern_object in url_patterns:
            # compiled_regex = re.compile(pattern, re.UNICODE)
            match = pattern_object.regex.search(path)
            if match:
                kwargs = match.groupdict()
                args = () if kwargs else match.groups()
                return pattern_object.callback(environ, *args, **kwargs)
    
        raise Http404
    
```

下面是添加的 RegexURLPattern 类， 使用描述符将编译的 regex 属性缓存到属性列表中:

```

    class RegexURLPattern(object):

        def __init__(self, regex, callback):
            self._regex = regex
            self.callback = callback
    
        @cached_property
        def regex(self):
            return re.compile(self._regex, re.UNICODE)
    
        def __repr__(self):
            return 'RegexURLPattern instance regex is: {}, callback name is: {}'.format(self._regex, self.callback.__name__)
    
        def __str__(self):
            return self.__repr__()
        
```

然后我加上一个单元测试函数来测试它:

```

    from project.urlsconf import url

    def test_url_function(monkeypatch):
    
        def temp_func(version, *args, **kwargs):
            return '<h1>root path test</h1>'
    
        with pytest.raises(ImproperlyConfigured):
            url(None, temp_func)
    
        with pytest.raises(ImproperlyConfigured):
            url(r'^d({1,-1}$', temp_func)
    
        with pytest.raises(ImproperlyConfigured):
            url([1, 2, 3], temp_func)
    
        with pytest.raises(ImproperlyConfigured):
            url('^/path([1,2])$', None)

```

测试没有问题， 查看代码的时候发现， regex 还是进行了两次编译， 判断时编译了一次， 还有第一次使用时编译了一次,
因此将编译检测其实可以放一块， 判断推后就行了, 去掉前面单元测试中不合法的正则表达式的检查，然后增加一个 RegexURLPattern
类的单元测试， 同时移除 url 函数中正则表达式不合法的检测。

```

    from project.urlsconf import RegexURLPattern


    def test_regex_url_pattern_class():
    
        with pytest.raises(ImproperlyConfigured):
            RegexURLPattern(r'^d({1,-1}$', _temp_func).regex


```

注， django 目前来说，还支持字符串形式的 view，这种方式通过分解字符串来加载函数， 但是 django 明确在将来将会淘汰这种方法， 因此
大致的 url 的一个实现过程由个初步的了解了。

结束语
----------

通过 一个正则表达式对应一个处理函数的方式， 来将具体路径映射到具体的处理函数中去，在路径匹配的时候，不但要知道这个路径具体怎么处理，
还要提取路径中的信息，作为处理函数的条件或者数据，因此需要在正则表达式中进行分组处理， 接下来为了使这种映射关系配置的灵活性，将其
作为独立配置以列表的形式独立了出来， 在匹配的时候是通过扫描列表的方式来匹配的， 这就意味着将使用频繁的路径放在列表的前面有利于提高
访问性能； 这种配置模式是要经过检查处理的，python 它不像 java 那样的静态语言，因此动态语言的灵活性有的时候也会带来一些困扰， 虽然
在接下来的 python 3 版本中，加了注解，但以防万一很多时候参数的检查还是得自己来写，这里加了一个配置检测的异常 ImproperlyConfigured
它应该是对应所有配置发生错误应该抛出的异常； 为了达到最好的性能， django 只在第一次匹配路径时进行正则表达式的编译处理，因此第一次
请求可能响应时间会相对慢一些。






