import copy

from stdnet.exceptions import *
from stdnet.utils import zip, UnicodeMixin
from stdnet import dispatch

from .base import StdNetType, FakeModelType
from .globals import get_model_from_hash 
from .signals import *


__all__ = ['FakeModel',
           'StdModel',
           'StdNetType',
           'from_uuid',
           'model_to_dict']


class ModelMixin(UnicodeMixin):
    DoesNotExist = ObjectNotFound
    DoesNotValidate = ObjectNotValidated
    
    def __eq__(self, other):
        if other.__class__ == self.__class__:
            return self.id == other.id
        else:
            return False
        
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        try:
            return hash(self.uuid)
        except self.DoesNotExist as e:
            raise TypeError(str(e))
        
    @property
    def uuid(self):
        '''Universally unique identifier for a model instance.'''
        if not self.id:
            raise self.DoesNotExist('Object not saved. Cannot obtain universally unique id')
        return '{0}.{1}'.format(self._meta.hash,self.id)
        
    
FakeModelBase = FakeModelType('FakeModelBase',(ModelMixin,),{})
StdNetBase = StdNetType('StdNetBase',(ModelMixin,),{})


class FakeModel(FakeModelBase):
    id = None
    is_base_class = True
        


class StdModel(StdNetBase):
    '''A model is the single, definitive source of data
about your data. It contains the essential fields and behaviors
of the data you're storing. Each model class
maps to a single :class:`stdnet.HashTable` structure via
the :attr:`StdModel._meta` attribute.

.. attribute:: _meta

    Instance of :class:`stdnet.orm.base.Metaclass`

.. attribute:: id

    Model instance id. The instance primary key.
        
.. attribute:: uuid

    Universally unique identifier for a model instance.
    
'''
    is_base_class = True
    
    def __init__(self, **kwargs):
        for field in self._meta.scalarfields:
            name = field.name
            value = kwargs.pop(name,None)
            if value is None:
                value = field.get_default()
            setattr(self,name,value)
        setattr(self,'id',kwargs.pop('id',None))
        if kwargs:
            raise ValueError("'%s' is an invalid keyword argument for %s" % (kwargs.keys()[0],self._meta))
        self.afterload()
        
    def afterload(self):
        self._cachepipes = {}
    
    def save(self, transaction = None):
        '''Save the instance in the remote :class:`stdnet.HashTable`
The model must be registered with a :class:`stdnet.backends.BackendDataServer`
otherwise a :class:`stdnet.exceptions.ModelNotRegistered` exception will raise.

:parameter transaction: Optional transaction instance. It can be useful when saving
                        several object together (it guaranties atomicity and it is much faster).
                        Check the :ref:`transaction <model-transactions>`
                        documentation for more information.
                        
                        Default: ``None``.
                        
The method return ``self``.
'''
        if not transaction:
            pre_save.send(sender=self.__class__, instance = self)
        meta = self._meta
        if not meta.cursor:
            raise ModelNotRegistered("Model '{0}' is not registered with a\
 backend database. Cannot save instance.".format(meta))
        r = meta.cursor.save_object(self, transaction)
        if not transaction:
            post_save.send(sender=self.__class__,
                           instance = r)
        return r
    
    def is_valid(self):
        '''Return ``True`` if the model validates. It check all fields agains their respective
validation algorithm.'''
        return self._meta.is_valid(self)

    def _valattr(self, name):
        if hasattr(self,self._meta.VALATTR):
            return getattr(self,self._meta.VALATTR)[name]
            
    @property
    def cleaned_data(self):
        return self._valattr('data')
        
    @property
    def errors(self):
        return self._valattr('errors')
        
    @property
    def indices(self):
        return self._valattr('indices')
    
    def delete(self, transaction = None, dlist = None):
        '''Delete an instance from database. If the instance is not available (it does not have an id) and
``StdNetException`` exception will raise. Return the number of model instances deleted.

:parameter transaction: Optional transaction instance as in :meth:`stdnet.orm.StdModel.save`.
:parameter dlist: Optional list. If available it will be filled with the ids of all models deleted.

It returns the number of objects deleted. This method can delete more than one object when
related the model for ``self`` is a related field in other models.'''
        meta = self._meta
        if not self.id:
            raise StdNetException('Cannot delete object. It was never saved.')
        T = 0
        # Gather related objects to delete
        pre_delete.send(sender=self.__class__, instance = self)
        objs = self.related_objects()
        for obj in objs:
            T += obj.delete(transaction,dlist)
        res = T + meta.cursor.delete_object(self, transaction, dlist)
        post_delete.send(sender=self.__class__, instance = self)
        return res
    
    def related_objects(self):
        '''Collect or related objects'''
        objs = []
        for rel in self._meta.related:
            rmanager = getattr(self,rel)
            objs.extend(rmanager.all())
        return objs
    
    def todict(self):
        odict = {}
        for field in self._meta.scalarfields:
            value = getattr(self,field.attname,None)
            value = field.serialize(value)
            if value:
                odict[field.name] = value
        return odict
    
    # UTILITY METHODS
    
    def instance_keys(self):
        '''Utility method for returning keys associated with this instance only. The instance id
is however available in other keys (indices and other backend containers).'''
        return self._meta.cursor.instance_keys(self)
    
    @classmethod
    def flush(cls, count = None):
        '''Flush the model table and all related tables including all indexes.
Calling flush will erase everything about the model instances in the remote server.
If count is a dictionary, the method
will enumerate the number of object to delete. without deleting them.'''
        return cls._meta.flush(count)
    
    @classmethod
    def transaction(cls):
        '''Return a transaction instance.'''
        return cls._meta.cursor.transaction()
    
    # PICKLING SUPPORT
    
    def __getstate__(self):
        return (self.id, self.todict())
    
    def __setstate__(self, state):
        id,data = state
        meta = self._meta
        field = meta.pk
        setattr(self,'id',field.to_python(id))
        for field in meta.scalarfields:
            name = field.attname
            if name in data:
                value = data[name]
            else:
                value = None
            setattr(self,name,field.to_python(value))
        self.afterload()
    

def from_uuid(uuid):
    '''Retrieve an instance of a :class:`stdnet.orm.StdModel`
from an universal unique identifier *uuid*. If the *uuid* does not match any
instance an exception will raise.'''
    elems = uuid.split('.')
    if len(elems) == 2:
        model = get_model_from_hash(elems[0])
        if not model:
            raise StdModel.DoesNotExist('model id "{0}" not available'.format(elems[0]))
        return model.objects.get(id = elems[1])
    raise StdModel.DoesNotExist('uuid "{0}" not recognized'.format(uuid))
    
    
def model_to_dict(instance, fields = None, exclude = None):
    if isinstance(instance,StdModel):
        return instance.todict()
    else:
        d = {}
        for field in instance._meta.fields:
            default = field.get_default()
            if default:
                d[field.name] = default
        return d
                
