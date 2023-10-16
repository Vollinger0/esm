from datetime import timedelta
import logging
from timeit import default_timer as timer

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

def getTimer():
    return timer()

def getElapsedTime(start):
    return timedelta(seconds=timer()-start)