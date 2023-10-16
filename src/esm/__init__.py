import logging

log = logging.getLogger(__name__)

def isDebugMode(config):
    return config.general.debugMode

def askUser(question, answerForTrue):
    """
    asks the user for input, returns true if the answer was 'answerForTrue'
    """
    log.debug(f"asking for user input: {question}")
    answer = input(question).lower()
    log.debug(f"user answered with {answer}")
    return answer==answerForTrue


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