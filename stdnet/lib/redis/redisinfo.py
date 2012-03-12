'''\
Modulule containing utility classes for retrieving and displaying
Redis status and statistics.
'''
from datetime import datetime

from stdnet.utils.structures import OrderedDict
from stdnet.utils import iteritems, format_int
from stdnet import orm

init_data = {'set':{'count':0,'size':0},
             'zset':{'count':0,'size':0},
             'list':{'count':0,'size':0},
             'hash':{'count':0,'size':0},
             'ts':{'count':0,'size':0},
             'string':{'count':0,'size':0},
             'unknown':{'count':0,'size':0}}



__all__ = ['RedisDb',
           'RedisKey',
           'RedisDataFormatter',
           'redis_info']


class RediInfo(object):
    names = ('Server','Memory','Persistence',
             'Replication','Clients','Stats','CPU')
    converters = {'last_save_time': ('date', None),
                  'uptime_in_seconds': ('timedelta', 'uptime'),
                  'uptime_in_days': None}
    
    def __init__(self, client, info, formatter):
        self.client = client
        self.version = info['Server']['redis_version']
        self.info = info
        self._panels = OrderedDict()
        self.formatter = formatter
        self.databases = RedisDb.objects.all(self)
    
    @property
    def keyspace(self):
        return self.info['Keyspace']
    
    def panels(self):
        if not self._panels:
            for name in self.names:
                self.makepanel(name)
        return self._panels
    
    def _dbs(self,keydata):
        for k in keydata:
            if k[:2] == 'db':
                try:
                    n = int(k[2:])
                except:
                    continue
                else:
                    yield k,n,keydata[k]
    
    def dbs(self,keydata):
        return sorted(self._dbs(keydata), key = lambda x : x[1])
            
    def db(self,n):
        return self.info['Keyspace']['db{0}'.format(n)]
    
    def makepanel(self, name):
        if name not in self.info:
            return
        pa = self._panels[name] = []
        nicename = self.formatter.format_name
        nicebool = self.formatter.format_bool
        boolval = (0,1)
        for k,v in iteritems(self.info[name]):
            add = True
            if k in self.converters or isinstance(v,int):
                fdata = self.converters.get(k,('int',None))
                if fdata:
                    formatter = getattr(self.formatter,
                                        'format_{0}'.format(fdata[0]))
                    k = fdata[1] or k
                    v = formatter(v)
                else:
                    add = False
            elif v in boolval:
                v = nicebool(v)
            if add:
                pa.append({'name':nicename(k),
                           'value':v})
        return pa
    
    
class RedisDbManager(object):
    
    def all(self, info):
        rd = []
        kdata = info.keyspace
        for k,n,data in info.dbs(info.keyspace):
            rdb = RedisDb(client = info.client, db = n, keys = data['keys'],
                          expires = data['expires'])
            rd.append(rdb)
        return rd
    
    def get(self, db = None, info = None):
        if info and db is not None:
            data = info.keyspace.get('db{0}'.format(db))
            if data:
                return RedisDb(client = info.client, db = int(db),
                               keys = data['keys'], expires = data['expires'])
                            
    
class RedisDb(orm.ModelBase):
    
    def __init__(self, client = None, db = None, keys = None,
                 expires = None):
        self.id = db
        if client and db is None:
            self.id = client.db
        if self.id != client.db:
            client = client.clone(db = self.id)
        self.client = client
        self.keys = keys
        self.expires = expires
    
    def delete(self, flushdb = None):
        flushdb(self.client) if flushdb else self.client.flushdb()
        
    objects = RedisDbManager()
    
    @property
    def db(self):
        return self.id
    
    def __unicode__(self):
        return '{0}'.format(self.id)
    

class RedisKeyManager(object):
    
    def all(self, db):
        keys = []
        stats = init_data.copy()
        append = keys.append
        for info in self.keys(db, None, '*'):
            append(info)
            d = stats[info.type]
            d['count'] += 1
            d['size'] += info.length
        return keys,stats
    
    def keys(self, db, keys, *patterns):
        for info in db.client.script_call('keyinfo', keys, *patterns):
            info.database = db
            yield info
            
    def delete(self, instances):
        if instances:
            keys = tuple((instance.id for instance in instances))
            return instances[0].client.delete(*keys)
    
    
class RedisKey(orm.ModelBase):
    database = None
    def __init__(self, client = None, type = None, length = 0, ttl = None,
                 encoding = None, idle = None, **kwargs):
        self.client = client
        self.type = type
        self.length = length
        self.time_to_expiry = ttl
        self.encoding = encoding
        self.idle = idle
    
    objects = RedisKeyManager()
    
    @property
    def key(self):
        return self.id
    
    def __unicode__(self):
        return self.key


def niceadd(l,name,value):
    if value is not None:
        l.append({'name':name,'value':value})


class RedisDataFormatter(object):
    
    def format_bool(self, val):
        return 'yes' if val else 'no'
    
    def format_name(self, name):
        return name
    
    def format_int(self, val):            
        return format_int(val)
    
    def format_date(self, dte):
        try:
            d = datetime.fromtimestamp(dte)
            return d.isoformat().split('.')[0]
        except:
            return ''
    
    def format_timedelta(self, td):
        return td
            
            
def redis_info(client, formatter = None):
    info = client.info()
    formatter = formatter or RedisDataFormatter()
    return RediInfo(client, info, formatter)
    