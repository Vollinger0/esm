
from functools import cached_property
import logging
import unittest
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
        # no need to instantiate anything, there should already bee a Foo instance in the registry
        self.assertEqual(self.foo.getBar(), 3)

    def test_ServiceCanBeOverriden(self):
        foo = Foo()
        foo.setBar(5)
        ServiceRegistry.register(foo)
        retrievedFoo1 = ServiceRegistry.get(Foo)
        self.assertEqual(retrievedFoo1.getBar(), 5)

        foo2 = Foo(9)
        ServiceRegistry.register(foo2)
        retrievedFoo2 = ServiceRegistry.get(Foo)
        self.assertEqual(retrievedFoo2.getBar(), 9)
