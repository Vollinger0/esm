class SaveGameFoundException(Exception):
    pass

class NoSaveGameFoundException(Exception):
    pass

class SaveGameMirrorFoundException(Exception):
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

class SafetyException(Exception):
    pass

class WrongParameterError(Exception):
    pass


class ExitCodes:
    """
    used as console return codes for sys.exit() throughout the application, if needed.
    """
    INSTANCE_RUNNING = 1
    INSTANCE_RUNNING_GAVE_UP = 2
    SCRIPT_INTERRUPTED = 10
