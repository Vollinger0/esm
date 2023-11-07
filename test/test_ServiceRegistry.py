
from functools import cached_property
import logging
import unittest
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class Foo:

    def __init__(self, value=3) -> None:
        self.bar = value

    def getBar(self):
        return self.bar
    
    def setBar(self, value):
        self.bar = value

class test_ServiceRegistry(unittest.TestCase):

    @cached_property
    def foo(self) -> Foo:
        return ServiceRegistry.get(Foo)

    def test_ServiceAnnotationWorks(self):
        #foo = ServiceRegistry.get(Foo)
        self.assertEqual(self.foo.getBar(), 3)

    def test_ServiceCanBeOverriden(self):
        foo = Foo()
        foo.setBar(5)
        ServiceRegistry.register(foo)
        self.assertEqual(self.foo.getBar(), 5)
