深入理解 django 的 urls 的实现 （三）
===================================

url 按模块配置说明
------------------------------------

  前面说到 url 是可配置的， 那么怎么能够让 url 配置更加灵活了， 我知道 url 是可以通过包含其他 urls.py 模块来配置的
那么怎么来实现这个了， 这个问题的解决方法里面就出现在 url 函数中， 这个 view 参数，它不仅仅只是一个 view， 它可以是
查找的模块，而从这个模块中同样可以找到 url 的配置项，这充分利用 python 动态语言的这个特性， 那么接下来只要对模块和单个 view 
进行不同处理就可以了. 由于每个 url 匹配的查找是分段进行的，因此要对这个匹配过程进行切割， 以 url 中的 `/` 进行切割最为合适， 
从左到右依次匹配切割项.但是了也不排除不使用 `\` 进行切割的方式:

以 django 中 include 方法为例:

root_urls.py

```

    urlpatterns = [
        url(r'^/root$', include('project.part_urls')),
    ]
    
```

part_urls.py

```

    urlpatterns = [
        url(r'^/part_1$', view_func1),
        url(r'^/part_2$', view_func2),
    ]
    
```

显然这样做的话， `/` 就冗余了,  为了保证配置的一致性， 在root url 中， 也需要把斜杆去掉， 即任何路径的匹配，首先就把第一个斜杆作为
切割的一部分给匹配掉， 这样在任何模块中进行 url 配置时， 它们的配置方式都是完全一致的， 如果作为 url 最后切割的一部分，当然也可以不用
管这个斜杆， 这种约定的方式使得配置非常统一， 唯一不足的地方就是在匹配的时候，多切割了一层（而它仅仅只是为了去掉冗余的斜杆）

root_urls.py

```

    urlpatterns = [
        url(r'^root/$', include('project.part_urls')),
    ]
    
```

part_urls.py

```

    urlpatterns = [
            url(r'^part_1/$', view_func1),
            url(r'^part_2$', view_func2),
    ]

```


url 按模块配置实现
------------------------------------

知道了大致的实现思路， 那我也来简单实现一下， 第一步，切割掉 `/` , 然后分段切割， 如果是调用方法就返回处理， 如果是包含的模块的配置
则递归处理，直至匹配成功到调用方法， 如果没有匹配到最后的切割部分没有找到对应的匹配，怎抛出 404 异常。

接下来我要重构一下 path_to_response 函数， 让它首先切割掉 url 路径中的 `/`, 然后在重构下 url 函数，使其支持返回匹配列表，接着再
增加两个统一的入口方法， 将 url 中直接匹配和切割匹配作为两个独立的对象看待，但是了，它们这个方法都是返回匹配结果的，同时它们接受同样的
一个路径方法。由于方法的入口一样，因此不管切割的多么复杂，最后也会逐一匹配，直到最终找到匹配项。原来的匹配过程在 path_to_response 对象
中，现在应该放到两个对象上去做了。

首先我用 include 函数进行切割， 它需要返回一个 url 匹配列表， 这里采用规则优于配置的做法，规定 url 配置模块中 包含这个属性 
url_patterns， 并且返回匹配列表:

```
    
    def include(module_path):
        if not module_path:
            raise ImproperlyConfigured('include url pattern config should not empty')
        if isinstance(module_path, str):
            url_conf_module = import_module(module_path)
            patterns = getattr(url_conf_module, 'url_patterns')
            return patterns
        raise ImproperlyConfigured("include url pattern config should be "
                                   "a string but it's type is {}".format(type(module_path)))

```

写个正常的测试用例来测试这个函数， 由于重点在于 url 的可扩展， 关于 include 的健壮性暂时不做考虑

```

    def test_include_func():
        assert include('tests.urls_config') == url_patterns


```

使用命令 `py.test -q -s tests/test_my_wsgi.py::test_include_func` 来单独执行这个单元测试:

```

    def test_include_func():
        assert include('tests.urls_config') == url_patterns

```

这里在 tests 目录下创建两个单元测试用到的依赖的模块 urls_config.py， include_to_urls_conf.py

```

    # urls_config.py
    from project.urlsconf import url, include
    
    url_patterns = [
        url(r'^$', lambda version, *args, **kwargs: '<h1>sub path test with root number: {}</h1>'.format(kwargs['root'])),
        url(r'^path([1,2])$', lambda version, *args, **kwargs:
            '<p>get sub /root{}/path{} test information</p>'.format(args[0], args[1])),
        url(r'^dpath(?P<dpath>[1,2])$', lambda version, *args, **kwargs:
            '<p>get sub /root{}/dpath{} test information</p>'.format(kwargs['root'], kwargs['dpath'])),
        url(r'^sdpath(?P<dpath>[1,2])/', include('tests.include_to_urls_conf'))
    ]

```

```

    # include_to_urls_conf.py
    from project.urlsconf import url

    url_patterns = [
        url(r'^$', lambda version, *args, **kwargs: '<h1>sub path test with root number: {}</h1>'.format(kwargs['root'])),
        url(r'^subdpath(?P<subdpath>[1,2])$',
            lambda version, *args, **kwargs: '<p>sub dpath number: {}</p>'.format(kwargs['subdpath']))
    ]

```

现在按照前面的描述的那样，将最前面的斜杆去掉， 然后 path_to_response 不在进行具体的匹配的操作， 而是放到其他匹配对象中

```

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
            
```

这里单元测试肯定通不过了， 首先修改原来的 RegexURLPattern 类， 加入 resolve 方法， 将 path_to_response 匹配的方法原封不动的
拷贝到这个 resolve 方法中， 并让其返回一个元组，里面放的值依次时 view方法， 分组参数， 分组字典参数， 对应 callback, args, kwargs

```

    def resolve(self, path):
        match = self.regex.search(path)

        if match:
            kwargs = match.groupdict()
            args = () if kwargs else match.groups()
            return self.callback, args, kwargs

```

此时由于去掉了最前面的斜杆， 应该将单元测试中 monkey patch 所对应的 url_patterns 修正过来

```

    def test_path_to_response(monkeypatch):
    
        url_patterns = [
            url('^$', lambda version, *args, **kwargs: '<h1>root path test</h1>'),
            url('^path([1,2])$', lambda version, *args, **kwargs: '<p>get path{} test information</p>'.format(args[0]))
        ]
        ... ...

```

再次运行所有的单元测试，应该确保所有的单元测试都通过

接下来增加一个 `RegexURLPatternList` 这个类和 `RegexURLPattern` 唯一的区别就是它初始化时接受的不是 view 函数， 而是一个 匹配列表了
它的 resolve 方法也不相同:

```

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

```

这个 resolve 方法要复杂很多， 因为在获取匹配参数的时候， 需要将分割的路径所有的参数都获取到， 最后汇总， 这里的做法就是利用前面
统一 resolve 接口所带来的好处， 不管 url 是如何配置的， 最终它们 resolve 的方法返回和接受的参数都是一致的， 同时这里需要做一些
约定，这也是为什么很多时候， url 配置的时候， 为啥没有获取到匹配参数的原因， 这个约定是这样的， **任何切割的地方出现了字典型分组，那么
非字典型分组就直接被忽略了， 如果没有出现字典型分组，则所有的分组按照先后顺序得到一个最终的分组**

写个单元测试，逐一测试一下

```

    def test_regex_url_pattern_list_class():
        assert {'root': '1'} == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/')[2]
        assert {'root': '1'} == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/path1')[2]
        assert ('1',) == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/path1')[1]
        assert ('1', '1') == RegexURLPatternList(r'^root([1,2])/', url_patterns).resolve('root1/path1')[1]
        assert {'root': '1', 'dpath': '1'} == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/dpath1')[2]
        assert {'root': '1', 'dpath': '1', 'subdpath': '1'} \
               == RegexURLPatternList(r'^root(?P<root>[1,2])/', url_patterns).resolve('root1/sdpath1/subdpath1')[2]

```

测试通过后，我在加上一个分割 url 的 path_to_response 函数的测试用例:

```

    def test_path_to_response_with_include_url_patterns(monkeypatch):
    
        url_patterns = [
            url('^root(?P<root>[1,2])/', include('tests.urls_config'))
        ]
        monkeypatch.setattr(mywsgi, "url_patterns", url_patterns)
        assert mywsgi.path_to_response({'PATH_INFO': '/root1/sdpath1/subdpath1'}) == '<p>sub dpath number: 1</p>'
    
        with pytest.raises(Http404):
            mywsgi.path_to_response({'PATH_INFO': '/root1/sdpath/subdpath1'})

```


小结
------

至此这个切割的 url 形式大致完成了，现在可以进行 url 配置扩展了， 总的来说 url 分组就是利用了规则优于配置的形式来实现的，同时
在获取切割的匹配参数的时候做了一些约定， 并且针对于不同的 url 配置，对应了不同的匹配类， 指定一个统一的接口使得 url 配置所得到的结果
都是一致的，那么 url 配置查找这一块还有什么内容了， 知道 django 中是有翻转 url 查找的， 还有就分区域的， 那这些又该如何实现了。





