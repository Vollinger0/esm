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
    """when an instance of this script is already running """
    INSTANCE_RUNNING_GAVE_UP = 2
    """when an instance of this script is already running, and we waited long enough for it to end"""
    SCRIPT_INTERRUPTED = 10
    """when the script was interrupted by the user, probably by ctrl+c (sigint)"""
    MISSING_CONFIG = 20
    """no config file found"""
