import os
import sys
from itertools import chain
from uuid import uuid4

from .py2py3 import *

if ispy3k:  # pragma: no cover
    import pickle
    unichr = chr
else:   # pragma: no cover
    import cPickle as pickle
    unichr = unichr 
    
from .jsontools import *
from .populate import populate
from .dates import *


def gen_unique_id(short = True):
    id = str(uuid4())
    if short:
        id = id[:8]
    return id

    
def grouper(n, iterable, padvalue=None):
    "grouper(3, 'abcdefg', 'x') --> ('a','b','c'), ('d','e','f'), ('g','x','x')"
    return zip_longest(*[iter(iterable)]*n, fillvalue=padvalue)

def _format_int(val):
    positive = val >= 0
    sval = ''.join(reversed(','.join((''.join(g) for g in\
                               grouper(3,reversed(str(abs(val))),'')))))
    return sval if positive else '-'+sval
    
def format_int(val):
    try: # for python 2.7 and up
        return '{:,}'.format(val)
    except ValueError:  # pragma nocover
        _format_int(val)

def flat_mapping(mapping):
    if isinstance(mapping,dict):
        mapping = iteritems(mapping)
    items = []
    extend = items.extend
    for pair in mapping:
        extend(pair)
    return items


def _flat2d_gen(iterable):
    for v in iterable:
        yield v[0]
        yield v[1]
        
        
def flat2d(iterable):
    if hasattr(iterable,'__len__'):
        return chain(*iterable)
    else:
        return _flat2d_gen(iterable)

    
def _flatzsetdict(kwargs):
    for k,v in iteritems(kwargs):
        yield v
        yield k


def flatzset(iterable = None, kwargs = None):
    if iterable:
        c = flat2d(iterable)
        if kwargs:
            c = chain(c,_flatzsetdict(kwargs))
    elif kwargs:
        c = _flatzsetdict(kwargs)
    return tuple(c)


def uplevel(path,lev=1):
    if lev:
        return uplevel(os.path.split(path)[0],lev-1)
    else:
        return path


class PPath(object):
    '''Utility class for adding directories to the python path'''    
    def __init__(self, local_path):
        local_path = os.path.abspath(local_path)
        if os.path.isfile(local_path):
            self.local_path = os.path.split(local_path)[0]
        elif os.path.isdir(local_path):
            self.local_path = local_path
        else:
            raise ValueError('{0} not a valid directory'.format(local_path))
        
    def __repr__(self):
        return self.local_path
    __str__ = __repr__
    
    def join(self, path):
        return os.path.join(self.local_path,path)
        
    def add(self, module = None, up = 0, down = None, front = False):
        '''Add a directory to the python path.
        
:parameter module: Optional module name to try to import once we have found
    the directory
:parameter up: number of level to go up the directory three from
    :attr:`local_path`.
:parameter down: Optional tuple of directory names to travel down once we have
    gone *up* levels.
:parameter front: Boolean indicating if we want to insert the new path at the
    front of ``sys.path`` using ``sys.path.insert(0,path)``.'''
        if module:
            try:
                __import__(module)
                return module
            except ImportError:
                pass
            
        dir = uplevel(self.local_path,up)
        if down:
            dir = os.path.join(dir, *down)
        added = False
        if os.path.isdir(dir):
            if dir not in sys.path:
                if front:
                    sys.path.insert(0,dir)
                else:
                    sys.path.append(dir)
                added = True
            else:
                raise ValueError('Directory {0} not available'.format(dir))
        if module:
            try:
                __import__(module)
                return module
            except ImportError:
                pass
        return added


memory_symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
memory_size = dict(((s,1 << (i+1)*10) for i,s in enumerate(memory_symbols)))

def convert_bytes(b):
    '''Convert a number of bytes into a human readable memory usage'''
    if b is None:
        return '#NA'
    for s in reversed(memory_symbols):
        if b >= memory_size[s]:
            value = float(b) / memory_size[s]
            return '%.1f%sB' % (value, s)
    return "%sB" % b
