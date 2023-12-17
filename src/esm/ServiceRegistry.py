import logging
from typing import TypeVar
from esm.exceptions import ServiceNotFoundError

log = logging.getLogger(__name__)

class ServiceRegistryMeta(type):
    _instances = {}

    def __call__(self, *args, **kwargs):
        if self not in self._instances:
            self._instances[self] = super(ServiceRegistryMeta, self).__call__(*args, **kwargs)
        return self._instances[self]

class ServiceRegistry(metaclass=ServiceRegistryMeta):
    """
    Service registry for classic dependency injection. There may be better libraries out there for this, but i needed something simple and fast.
    """
    _registry = {}

    T = TypeVar('T')

    @staticmethod
    def registerDecorated(serviceClass):
        ServiceRegistry._registry[serviceClass.__name__] = serviceClass()

    @staticmethod
    def register(instance):
        """
        if you want to register the instance you just created. Probably for testing
        """
        iClassName = instance.__class__.__name__
        if ServiceRegistry._registry.__contains__(iClassName):
            previous = ServiceRegistry._registry[iClassName]
            log.debug(f"warning, overwriting registered class {iClassName} ({previous}) with instance {instance}")
        ServiceRegistry._registry[iClassName] = instance
        return instance
    
    @staticmethod
    def get(serviceClass: T) -> T:
        service = ServiceRegistry._registry.get(serviceClass.__name__)
        if service:
            return service
        else:
            raise ServiceNotFoundError(f"no service by class {serviceClass.__name__} found.")
    
def Service(orgClass):
    """
    decorator to mark a class as service, will get registered in the registry automatically
    """
    ServiceRegistry.registerDecorated(orgClass)  # Register the service class
    return orgClass  # Return the original class, unmodified
