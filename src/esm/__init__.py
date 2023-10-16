class NoSaveGameFoundException(Exception):
    pass

class SaveGameMirrorExistsException(Exception):
    pass

class NoSaveGameMirrorFoundException(Exception):
    pass

class AdminRequiredException(Exception):
    pass

class RequirementsNotFulfilledError(Exception):
    pass

class UserAbortedException(Exception):
    pass

class ServiceNotFoundError(Exception):
    pass

class ServerNeedsToBeStopped(Exception):
    pass

class SecurityException(Exception):
    pass