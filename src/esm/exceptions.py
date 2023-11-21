class EsmException(Exception):
    pass

class SaveGameFoundException(EsmException):
    pass

class NoSaveGameFoundException(EsmException):
    pass

class SaveGameMirrorFoundException(EsmException):
    pass

class NoSaveGameMirrorFoundException(EsmException):
    pass

class AdminRequiredException(EsmException):
    pass

class RequirementsNotFulfilledError(EsmException):
    pass

class UserAbortedException(EsmException):
    pass

class ServiceNotFoundError(EsmException):
    pass

class ServerNeedsToBeStopped(EsmException):
    pass

class SafetyException(EsmException):
    pass

class WrongParameterError(EsmException):
    pass


class ExitCodes:
    """
    used as console return codes for sys.exit() throughout the application, if needed.
    """
    INSTANCE_RUNNING = 1
    """when an instance of this script is already running """
    INSTANCE_RUNNING_GAVE_UP = 2
    """when an instance of this script is already running, and we waited long enough for it to end"""
    SCRIPT_INTERRUPTED = 10
    """when the script was interrupted by the user, probably by ctrl+c (sigint)"""
    MISSING_CONFIG = 20
    """no config file found"""
