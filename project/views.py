from project.response import HttpResponse

def index_view(environ, *args, **kwargs):
    return HttpResponse('<h1>root path</h1>')


def path_view(environ, *args, **kwargs):
    return HttpResponse('<p>get path{} information</p>'.format(args[0]))


