import os
from datetime import date

from stdnet import test, odm, InvalidTransaction
from stdnet.utils import encoders, zip
from stdnet.utils.populate import populate

skipUnless = test.unittest.skipUnless
do_tests = os.environ.get('stdnet_backend_status') == 'stdnet'

dates = list(set(populate('date',100,start=date(2009,6,1),end=date(2010,6,6))))
values = populate('float',len(dates),start=0,end=1000)


class StructMixin(object):
    structure = None
    name = None
    
    def createOne(self, session):
        '''Create a structure and add few elements. Must return the structure
itself.'''
        raise NotImplementedError()
    
    def asserGroups(self, l):
        sm = l.session.model(l._meta)
        self.assertEqual(len(sm),1)
        self.assertTrue(l.session)
        self.assertTrue(l.state().persistent)
        self.assertFalse(l in sm.new)
        self.assertTrue(l in sm.dirty)
        self.assertTrue(l in sm.modified)
        self.assertFalse(l in sm.loaded)
        
    def testMeta(self):
        session = self.session()
        # start the transaction
        session.begin()
        l = self.createOne(session)
        self.assertTrue(l.id)
        self.assertEqual(l.instance, None)
        self.assertEqual(l.session, session)
        self.assertEqual(l._meta.name, self.name)
        self.assertEqual(l._meta.model._model_type, 'structure')
        #Structure have always the persistent flag set to True
        self.assertTrue(l.state().persistent)
        self.assertTrue(l in session)
        self.assertEqual(l.size(), 0)
        self.asserGroups(l)
        return l
    
    def testCommit(self):
        l = self.testMeta()
        l.session.commit()
        self.assertTrue(l.state().persistent)
        self.assertTrue(l.size())
        self.assertTrue(l in l.session)
        self.asserGroups(l)
        
    def testTransaction(self):
        session = self.session()
        with session.begin():
            l = self.createOne(session)
            # Trying to save within a section will throw an InvalidTransaction
            self.assertRaises(InvalidTransaction, l.save)
            # Same for delete
            self.assertRaises(InvalidTransaction, l.delete)
            self.assertTrue(l.state().persistent)
            self.asserGroups(l)
        self.assertTrue(l.size())
        self.assertTrue(l.state().persistent)
        
    def testDelete(self):
        session = self.session()
        with session.begin():
            s = self.createOne(session)
        self.asserGroups(s)
        self.assertTrue(s.size())
        s.delete()
        self.assertEqual(s.size(),0)
        self.assertNotEqual(s.session,None)
        self.assertFalse(s in session)
        
    def testEmpty(self):
        session = self.session()
        with session.begin():
            l = session.add(self.structure())
        self.asserGroups(l)
        self.assertEqual(l.size(),0)
        self.assertEqual(l.session,session)
        self.asserGroups(l)
        self.assertFalse(l.state().deleted)


class TestSet(StructMixin,test.TestCase):
    structure = odm.Set
    name = 'set'
    
    def createOne(self, session):
        s = session.add(odm.Set())
        s.update((1,2,3,4,5,5))
        return s
            
    def testSimpleUpdate(self):
        # Typical usage. Add a set to a session
        session = self.session()
        s = session.add(odm.Set())
        # if not id provided, an id is created
        self.assertTrue(s.id)
        self.assertEqual(s.session, session)
        self.assertEqual(s.instance, None)
        self.assertEqual(s.size(),0)
        # this add and commit to the backend server
        s.add(8)
        self.assertEqual(s.size(),1)
        self.assertTrue(s.state().persistent)
        s.update((1,2,3,4,5,5))
        self.assertEqual(s.size(),6)
        
    def testUpdateDelete(self):
        session = self.session()
        with session.begin():
            s = session.add(odm.Set())
            s.update((1,2,3,4,5,5))
            s.discard(2)
            s.discard(67)
            s.remove(4)
            s.remove(46)
            s.difference_update((1,56,89))
        self.assertEqual(s.size(),2)
        with session.begin():
            s.difference_update((3,5,6,7))
        self.assertEqual(s.size(),0)
        

class TestZset(StructMixin,test.TestCase):
    structure = odm.Zset
    name = 'zset'
    result =  [(0.0022,'pluto'),
               (0.06,'mercury'),
               (0.11,'mars'),
               (0.82,'venus'),
               (1,'earth'),
               (14.6,'uranus'),
               (17.2,'neptune'),
               (95.2,'saturn'),
               (317.8,'juppiter')]
    
    def createOne(self, session):
        l = session.add(odm.Zset())
        l.add(1,'earth')
        l.add(0.06,'mercury')
        l.add(317.8,'juppiter')
        l.update(((95.2,'saturn'),\
                  (0.82,'venus'),\
                  (14.6,'uranus'),\
                  (0.11,'mars'),
                  (17.2,'neptune'),
                  (0.0022,'pluto')))
        self.assertEqual(len(l.cache.toadd),9)
        return l
        
    def planets(self):
        session = self.session()
        session.begin()
        l = self.createOne(session)
        self.assertEqual(l.size(),0)
        session.commit()
        self.assertTrue(l.state().persistent)
        self.assertEqual(l.size(),9)
        return l
            
    def testMeta2(self):
        l = self.testMeta()
        self.assertFalse(l.cache.cache)
        self.assertTrue(l.cache.toadd)
        self.assertFalse(l.cache.toremove)

    def testZsetState(self):
        '''test a very simple zset with integer'''
        session = self.session()
        z = session.add(odm.Zset())
        self.assertTrue(z.state().persistent)
        self.assertTrue(z in session)
        self.assertEqual(z.session, session)
        session.delete(z)
        self.assertFalse(z in session)
        self.assertTrue(z.session)
        
    def testiRange(self):
        l = self.planets()
        # Get the whole range
        r = list(l.irange())
        self.assertEqual(r,self.result)
        
    def testIter(self):
        '''test a very simple zset with integer'''
        l = self.planets()
        r = list(l)
        v = [t[1] for t in self.result]
        self.assertEqual(r,v)
                
    def testItems(self):
        '''test a very simple zset with integer'''
        l = self.planets()
        r = list(l.items())
        self.assertEqual(r,self.result)
        
    def testGet(self):
        l = self.planets()
        self.assertEqual(l[1],'earth')
        self.assertEqual(l.get(0.11),'mars')


class TestList(StructMixin, test.TestCase):
    structure = odm.List
    name = 'list'
    
    def createOne(self, session):
        l = session.add(odm.List())
        l.push_back(3)
        l.push_back(5.6)
        return l
    
    def testMeta2(self):
        l = self.testMeta()
        l.push_back('save')
        l.push_back({'test': 1})
        l.session.commit()
        self.asserGroups(l)
        self.assertEqual(l.size(),4)
        self.assertEqual(list(l),[3,5.6,'save',"{'test': 1}"])
        
    def testJsonList(self):
        with self.session().begin() as t:
            l = t.add(odm.List(value_pickler = encoders.Json()))
            l.push_back(3)
            l.push_back(5.6)
            l.push_back('save')
            l.push_back({'test': 1})
            l.push_back({'test': 2})
        self.assertEqual(l.size(),5)
        self.assertEqual(list(l),[3,5.6,'save',{'test': 1},{'test': 2}])
    

class TestHash(StructMixin, test.TestCase):
    structure = odm.HashTable
    name = 'hashtable'
    
    def createOne(self, session):
        h = session.add(odm.HashTable())
        h['bla'] = 'foo'
        h['pluto'] = 3
        return h
        
    def testNoTransaction(self):
        session = self.session()
        d = session.add(odm.HashTable())
        d['bla'] = 5676
        self.assertEqual(d.size(),1)
        self.assertEqual(d['bla'],5676)
        
    def testPop(self):
        session = self.session()
        with session.begin():
            d = session.add(odm.HashTable())
            d['foo'] = 'ciao'
        self.assertEqual(d.size(),1)
        self.assertEqual(d['foo'],'ciao')
        self.assertRaises(KeyError, lambda : d.pop('bla'))
        self.assertEqual(d.pop('bla',56),56)
        self.assertRaises(TypeError, lambda : d.pop('bla',1,2))
        self.assertEqual(d.pop('foo'),'ciao')
        self.assertEqual(len(d),0)
        
    def testGet(self):
        session = self.session()
        with session.begin():
            h = session.add(odm.HashTable())
            h['bla'] = 'foo'
            h['bee'] = 3
        
        self.assertEqual(h['bla'],'foo')
        self.assertEqual(h.get('bee'),3)
        self.assertEqual(h.get('ggg'),None)
        self.assertEqual(h.get('ggg',1),1)
        self.assertRaises(KeyError, lambda : h['gggggg'])
        
@skipUnless(do_tests, 'Requires stdnet-redis')
class TestTS(StructMixin, test.TestCase):
    structure = odm.TS
    name = 'ts'
    
    def createOne(self, session):
        ts = session.add(odm.TS())
        ts.update(zip(dates,values))
        return ts
        
    def testMeta2(self):
        ts = self.testMeta()
        self.assertFalse(ts.cache.cache)
        self.assertTrue(ts.cache.toadd)
        self.assertFalse(ts.cache.toremove)
        
    def testEmpty2(self):
        session = self.session()
        ts = session.add(odm.TS())
        self.assertTrue(ts.id)
        self.assertEqual(ts.size(),0)
        self.assertEqual(ts.front(),None)
        self.assertEqual(ts.back(),None)
        self.assertEqual(ts.size(),0)
        
    def testData(self):
        session = self.session()
        session.begin()
        ts = self.createOne(session)
        self.assertTrue(ts.cache.toadd)
        session.commit()
        self.assertEqual(ts.size(),len(dates))
        front = ts.front()
        back = ts.back()
        self.assertTrue(back[0]>front[0])
        range = list(ts.range(date(2009,10,1),date(2010,5,1)))
        self.assertTrue(range)
        for time,val in range:
            self.assertTrue(time>=front[0])
            self.assertTrue(time<=back[0])
            
    def testGet(self):
        session = self.session()
        with session.begin():
            ts = session.add(odm.TS())
            ts.update(zip(dates,values))
        dt1 = dates[0]
        val1 = ts[dt1]
        self.assertTrue(val1)
        self.assertEqual(ts.get(dt1),val1)
        self.assertEqual(ts.get(date(1990,1,1)),None)
        self.assertEqual(ts.get(date(1990,1,1),1),1)
        self.assertRaises(KeyError, lambda : ts[date(1990,1,1)])
    

class TestString(StructMixin, test.TestCase):
    structure = odm.String
    name = 'string'
    
    def createOne(self, session):
        a = session.add(self.structure())
        a.push_back('this is a test')
        return a
    
    def testIncr(self):
        session = self.session()
        a = session.add(self.structure())
        self.assertEqual(a.incr(),1)
        self.assertEqual(a.incr(),2)
        self.assertEqual(a.incr(3),5)
        self.assertEqual(a.incr(-7),-2)
        
    
    
class TestNumberArray(StructMixin, test.TestCase):
    structure = odm.NumberArray
    name = 'numberarray'
    
    def createOne(self, session):
        a = session.add(self.structure())
        a.push_back(56).push_back(-78.6)
        return a
    
    def testSizeResize(self):
        session = self.session()
        a = session.add(self.structure())
        a.push_back(56).push_back(-78.6)
        self.assertEqual(a.size(),2)
        self.assertEqual(len(a),2)
        self.assertEqual(a.resize(10),10)
        data = list(a)
        self.assertEqual(len(data),10)
        self.assertAlmostEqual(data[0],56.0)
        self.assertAlmostEqual(data[1],-78.6)
        for v in data[2:]:
            self.assertNotEqual(v,v)
        
    def testSetGet(self):
        session = self.session()
        a = session.add(self.structure())
        a.push_back(56).push_back(-104.5)
        self.assertEqual(a.size(),2)
        self.assertAlmostEqual(a[1],-104.5)