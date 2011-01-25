import sys
import copy

from stdnet.utils import zip
from stdnet.orm import signals
from stdnet.exceptions import *

from .globals import hashmodel
from .query import UnregisteredManager
from .fields import Field, AutoField


def get_fields(bases, attrs):
    fields = {}
    for base in bases:
        if hasattr(base, '_meta'):
            fields.update(copy.deepcopy(base._meta.dfields))
    
    for name,field in attrs.items():
        if isinstance(field,Field):
            fields[name] = attrs.pop(name)
    
    return fields


class Metaclass(object):
    '''Utility class used for storing all information
which maps a :class:`stdnet.orm.StdModel` model
into a :class:`stdnet.HashTable` structure in a :class:`stdnet.BackendDataServer`.
An instance is initiated when :class:`stdnet.orm.StdModel` class is created:

.. attribute:: model

    a subclass of :class:`stdnet.orm.StdModel`.
    
.. attribute:: fields

    dictionary of :class:`stdnet.orm.Field` instances.
    
.. attribute:: abstract

    if ``True``, it represents an abstract model and no database elements are created.

.. attribute:: keyprefix

    prefix for the database table. By default it is given by ``settings.DEFAULT_KEYPREFIX``,
    where ``settings`` is obtained by::
    
        from dynts.conf import settings
    
.. attribute:: pk

    primary key ::class:`stdnet.orm.Field`

'''
    def __init__(self, model, fields,
                 abstract = False, keyprefix = None,
                 app_label = '', verbose_name = None, **kwargs):
        self.abstract  = abstract
        self.keyprefix = keyprefix
        self.model     = model
        self.app_label = app_label
        self.name = model.__name__.lower()
        self.fields       = []
        self.scalarfields = []
        self.multifields  = []
        self.dfields      = {}
        self.timeout      = 0
        self.related      = {}
        self.verbose_name = verbose_name or self.name
        self.maker        = lambda : model.__new__(model)
        model._meta       = self
        hashmodel(model)

        if id in fields:
            pk = fields['id']
        else:
            pk = AutoField(primary_key = True)
        pk.register_with_model('id',model)
        self.pk = pk
        if not self.pk.primary_key:
            raise FieldError("Primary key must be named id")
        
        for name,field in fields.iteritems():
            if name == 'id':
                continue
            field.register_with_model(name,model)
            if field.primary_key:
                raise FieldError("Primary key already available %s." % name)
            
        self.cursor = None
        self.keys  = None
        
    def __repr__(self):
        if self.app_label:
            return '{0}.{1}'.format(self.app_label,self.name)
        else:
            return self.name
    __str__ = __repr__
        
    def basekey(self, arg = ''):
        '''Calculate the key to access model hash-table, and model filters in the database.
        For example::
        
            >>> a = Author(name = 'Dante Alighieri').save()
            >>> a.meta.basekey()
            'stdnet:author'
            '''
        return '{0}{1}{2}'.format(self.keyprefix,self,arg)
    
    def autoid(self):
        '''Return the key for the autoincrement id.'''
        return self.basekey(':ids')
    
    def key_idset(self):
        return self.basekey(':idset')
    
    def key_hash(self, id):
        '''Return the key for the hash containing the instance with id ``id``.'''
        return self.basekey(':hash:{0}'.format(id))
    
    def key_index(self, field_name, value):
        '''Return the key for the index of field of
``field_name`` with ``value``.'''
        return self.basekey(':index:{0}:{1}'.format(field_name,value))
    
    def table(self, id):
        '''Return an instance of :class:`stdnet.HashTable` holding
the model table'''
        if not self.cursor:
            raise ModelNotRegistered('%s not registered. Call orm.register(model_class) to solve the problem.' % self)
        return self.cursor.hash(self.key_hash(id),self.timeout)
    
    def make(self, id, data):
        '''Create a model instance from server data'''
        obj = self.maker()
        setattr(obj,'id',id)
        if data:
            for field,value in zip(self.scalarfields,data):
                setattr(obj,field.attname,field.to_python(value))
        obj.afterload()
        return obj
    
    def flush(self, count = None):
        '''Fast method for clearing the whole table including related tables'''
        for rel in self.related.values():
            to = rel.to
            if to._meta.cursor:
                to.flush(count)
        if count is None:
            cursor = self.cursor
            keys = cursor.keys('{0}*'.format(self.basekey()))
            if keys:
                cursor.delete(*keys)
        else:
            count[str(self)] = self.table().count()


class StdNetType(type):
    '''StdModel python metaclass'''
    def __new__(cls, name, bases, attrs):
        super_new = super(StdNetType, cls).__new__
        parents = [b for b in bases if isinstance(b, StdNetType)]
        if not parents:
            return super_new(cls, name, bases, attrs)
        
        # remove the Meta class if present
        meta      = attrs.pop('Meta', None)
        if meta:
            kwargs   = meta_options(**meta.__dict__)
        else:
            kwargs   = meta_options()
        
        #if kwargs['abstract']:
        #    return super_new(cls, name, bases, attrs)
        
        # remove and build field list
        fields    = get_fields(bases, attrs)        
        # create the new class
        objects   = attrs.pop('objects',None)
        new_class = super_new(cls, name, bases, attrs)
        new_class.objects = objects
        app_label = kwargs.pop('app_label')
        
        if app_label is None:
            model_module = sys.modules[new_class.__module__]
            try:
                app_label = model_module.__name__.split('.')[-2]
            except:
                app_label = ''
        
        meta = Metaclass(new_class,fields,app_label=app_label,**kwargs)
        if objects is None:
            new_class.objects = UnregisteredManager(new_class)
        signals.class_prepared.send(sender=new_class)
        return new_class
    

def meta_options(abstract = False,
                 keyprefix = None,
                 app_label = None,
                 **kwargs):
    return {'abstract': abstract,
            'keyprefix': keyprefix,
            'app_label':app_label}
    

