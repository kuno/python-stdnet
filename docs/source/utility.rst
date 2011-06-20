.. _utility-index:

============================
Internals and Utilities
============================

.. module:: stdnet.orm

Model Utilities
============================

Instance form UUID
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: stdnet.orm.from_uuid


Model Iterator
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: stdnet.orm.model_iterator


Register Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: stdnet.orm.register_application_models


.. autofunction:: stdnet.orm.register_applications


Flush Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: stdnet.orm.flush_models


.. module:: stdnet.utils


Miscellaneous
============================

Populate
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: stdnet.utils.populate



Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: stdnet.PipeLine
   :members:
   :member-order: bysource


Exceptions
============================

.. autoclass:: stdnet.StdNetException
   :members:
   :member-order: bysource
   
.. autoclass:: stdnet.ImproperlyConfigured
   :members:
   :member-order: bysource
   
.. autoclass:: stdnet.ModelNotRegistered
   :members:
   :member-order: bysource
   
   
.. autoclass:: stdnet.QuerySetError
   :members:
   :member-order: bysource
   
.. autoclass:: stdnet.FieldError
   :members:
   :member-order: bysource
   
.. autoclass:: stdnet.FieldValueError
   :members:
   :member-order: bysource
   