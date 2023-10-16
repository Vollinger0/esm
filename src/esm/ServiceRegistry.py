from typing import TypeVar
from esm import ServiceNotFoundError

class ServiceRegistryMeta(type):
    _instances = {}

    def __call__(self, *args, **kwargs):
        if self not in self._instances:
            self._instances[self] = super(ServiceRegistryMeta, self).__call__(*args, **kwargs)
        return self._instances[self]

class ServiceRegistry(metaclass=ServiceRegistryMeta):
    _registry = {}

    T = TypeVar('T')

    @staticmethod
    def registerDecorated(serviceClass):
        ServiceRegistry._registry[serviceClass.__name__] = serviceClass()

    @staticmethod
    def register(instance=None):
        iClass = instance.__class__
        if instance is None:
            ServiceRegistry._registry[iClass.__name__] = iClass()
        else:
            ServiceRegistry._registry[iClass.__name__] = instance
        return ServiceRegistry._registry[iClass.__name__]
    
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

