import sys
import copy
import hashlib
import weakref
from collections import namedtuple

from stdnet.utils import zip, to_bytestring, to_string
from stdnet.exceptions import *

from . import signals
from .globals import hashmodel, JSPLITTER
from .fields import Field, AutoField
from .session import Manager, setup_managers

__all__ = ['Metaclass']

def get_fields(bases, attrs):
    fields = {}
    for base in bases:
        if hasattr(base, '_meta'):
            fields.update(copy.deepcopy(base._meta.dfields))
    
    for name,field in list(attrs.items()):
        if isinstance(field,Field):
            fields[name] = attrs.pop(name)
    
    return fields


orderinginfo = namedtuple('orderinginfo','name field desc')


class Metaclass(object):
    '''An instance of :class:`Metaclass` stores all information
which maps an :class:`StdModel` into an object in the in a remote
:class:`stdnet.BackendDataServer`.
An instance is initiated by the orm when a :class:`StdModel` class is created.

To override default behaviour you can specify the ``Meta`` class as an inner
class of :class:`StdModel` in the following way::

    from datetime import datetime
    from stdnet import orm
    
    class MyModel(orm.StdModel):
        timestamp = orm.DateTimeField(default = datetime.now)
        ...
        
        class Meta:
            ordering = '-timestamp'
            modelkey = 'custom'
            

:parameter abstract: Check the :attr:`abstract` attribute.
:parameter ordering: Check the :attr:`ordering` attribute.
:parameter app_label: Check the :attr:`app_label` attribute.
:parameter modelkey: Check the :attr:`modelkey` attribute.

**Attributes and methods**:

This is the list of attributes and methods available. All attributes,
but the ones mantioned above, are initialized by the object relational
mapper.

.. attribute:: abstract

    If ``True``, it represents an abstract model and no database elements
    are created.

.. attribute:: app_label

    Unless specified it is the name of the directory or file
    (if at top level) containing the
    :class:`stdnet.orm.StdModel` definition.
    
.. attribute:: model

    a subclass of :class:`stdnet.orm.StdModel`. Set by the ``orm``.
    
.. attribute:: ordering

    Optional name of a :class:`stdnet.orm.Field` in the :attr:`model`.
    If provided, indeces will be sorted with respect the value of the
    field specidied.
    Check the :ref:`sorting <sorting>` documentation for more details.
    
    Default: ``None``.
    
.. attribute:: dfields

    dictionary of :class:`stdnet.orm.Field` instances.
    
.. attribute:: fields

    list of :class:`stdnet.orm.Field` instances.
    
.. attribute:: modelkey

    Override the modelkey which is by default given by ``app_label.name``
    
    Default ``None``.
        
.. attribute:: pk

    The primary key :class:`stdnet.orm.Field`
'''
    searchengine = None
    connection_string = None
    
    def __init__(self, model, fields,
                 abstract = False, app_label = '',
                 verbose_name = None,
                 ordering = None, modelkey = None,
                 **kwargs):
        self.abstract = abstract
        self.model = model
        self.app_label = app_label
        self.name = model.__name__.lower()
        self.fields = []
        self.scalarfields = []
        self.indices = []
        self.multifields = []
        self.dfields = {}
        self.timeout = 0
        self.related = {}
        self.verbose_name = verbose_name or self.name
        self.modelkey = modelkey or '{0}.{1}'.format(self.app_label,self.name)
        model._meta = self
        hashmodel(model)
        
        # Check if ID field exists
        try:
            pk = fields['id']
        except:
            # ID field not available, create one
            pk = AutoField(primary_key = True)
        pk.register_with_model('id',model)
        self.pk = pk
        if not self.pk.primary_key:
            raise FieldError("Primary key must be named id")
        
        for name,field in fields.items():
            if name == 'id':
                continue
            field.register_with_model(name,model)
            if field.primary_key:
                raise FieldError("Primary key already available %s." % name)
        
        self.ordering = None
        if ordering:
            self.ordering = self.get_sorting(ordering,ImproperlyConfigured)
        for scalar in self.scalarfields:
            if scalar.index:
                self.indices.append(scalar)
        
    def maker(self):
        model = self.model
        return model.__new__(model)
        
    def __repr__(self):
        if self.app_label:
            return '%s.%s' % (self.app_label,self.name)
        else:
            return self.name
    
    def __str__(self):
        return self.__repr__()
    
    def is_valid(self, instance):
        '''Perform validation for *instance* and stores serialized data,
indexes and errors into local cache.
Return ``True`` if the instance is ready to be saved to database.'''
        v = instance.temp()
        data = v['cleaned_data'] = {}
        errors = v['errors'] = {}
        toload = v['toload'] = []
        indices = v['indices'] = []
        id = instance.id
        dbdata = instance._dbdata
        idnew = not (id and id == dbdata.get('id'))
        
        #Loop over scalar fields first
        for field,value in instance.fieldvalue_pairs():
            name = field.attname
            if value is None:
                value = field.get_default()
                setattr(instance,name,value)
            try:
                svalue = field.serialize(value)
            except FieldValueError as e:
                errors[name] = str(e)
            else:
                if (svalue is None or svalue is '') and field.required:
                    errors[name] = "Field '{0}' is required for '{1}'."\
                                    .format(name,self)
                else:
                    if isinstance(svalue, dict):
                        #data[name] = svalue
                        data.update(svalue)
                    else:
                        if svalue is not None:
                            data[name] = svalue
                        # if the field is an index add it
                        if field.index:
                            if idnew:
                                indices.append((field,svalue,None))
                            else:
                                if field.name in dbdata:
                                    oldvalue = dbdata[field.name]
                                    if svalue != oldvalue:
                                        indices.append((field,svalue,oldvalue))
                                else:
                                    # The field was not loaded
                                    toload.append(field.name)
                                    indices.append((field,svalue,None))
                                
        return len(errors) == 0
    
    def flush(self):
        '''Fast method for clearing the whole table including related tables'''
        N = 0
        for rel in self.related.values():
            rmeta = rel._meta
            # This avoid circular reference
            if rmeta is not self:
                N += rmeta.flush()
        if self.cursor:
            N += self.cursor.flush(self)
        return N

    def get_sorting(self, sortby, errorClass):
        s = None
        desc = False
        if sortby.startswith('-'):
            desc = True
            sortby = sortby[1:]
        if sortby == 'id':
            f = self.pk
            return orderinginfo(f.name,f,desc)
        else:
            if sortby in self.dfields:
                f = self.dfields[sortby]
                return orderinginfo(f.name,f,desc)
            sortbys = sortby.split(JSPLITTER)
            s0 = sortbys[0]
            if len(sortbys) > 1 and s0 in self.dfields:
                f = self.dfields[s0]
                return orderinginfo(sortby,f,desc)
        raise errorClass('Cannot Order by attribute "{0}".\
 It is not a scalar field.'.format(sortby))
        
    def backend_fields(self, fields):
        '''Return a tuple containing a list
of fields names and a list of field attribute names.'''
        dfields = self.dfields
        processed = set()
        names = []
        atts = []
        for name in fields:
            if name == 'id':
                continue
            if name in processed:
                continue
            if name in dfields:
                processed.add(name)
                field = dfields[name]
                names.append(field.name)
                atts.append(field.attname)
            else:
                bname = name.split(JSPLITTER)[0]
                if bname in dfields:
                    field = dfields[bname]
                    if field.type == 'json object':
                        processed.add(name)
                        names.append(name)
                        atts.append(name)
        return names,atts


    def multifields_ids_todelete(self, instance):
        '''Return the list of ids of :class:`MultiField` belonging to *instance*
which needs to be deleted when *instance* is deleted.'''
        gen = (field.id(instance) for field in self.multifields\
                                         if field.todelete())
        return [fid for fid in gen if fid]
    
class FakeMeta(object):
    pass
        
    
class FakeModelType(type):
    '''StdModel python metaclass'''
    def __new__(cls, name, bases, attrs):
        parents = [b for b in bases if isinstance(b, FakeModelType)]
        is_base_class = attrs.pop('is_base_class',False)
        new_class = super(FakeModelType, cls).__new__(cls, name, bases, attrs)
        if not parents or is_base_class:
            return new_class
        new_class._meta = FakeMeta()
        hashmodel(new_class)
        return new_class  


class StdNetType(type):
    '''StdModel python metaclass'''
    def __new__(cls, name, bases, attrs):
        super_new = super(StdNetType, cls).__new__
        parents = [b for b in bases if isinstance(b, StdNetType)]
        if not parents or attrs.pop('is_base_class',False):
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
        new_class = super_new(cls, name, bases, attrs)
        setup_managers(new_class)
        app_label = kwargs.pop('app_label')
        
        if app_label is None:
            model_module = sys.modules[new_class.__module__]
            try:
                app_label = model_module.__name__.split('.')[-2]
            except:
                app_label = ''
        
        meta = Metaclass(new_class,fields,app_label=app_label,**kwargs)
        signals.class_prepared.send(sender=new_class)
        return new_class
    
    def __str__(cls):
        return str(cls._meta)
    

def meta_options(abstract = False,
                 app_label = None,
                 ordering = None,
                 modelkey = None,
                 **kwargs):
    return {'abstract': abstract,
            'app_label':app_label,
            'ordering':ordering,
            'modelkey':modelkey}
    

