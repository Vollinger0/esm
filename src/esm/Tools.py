import logging
import os
import shutil
import subprocess
import traceback
from datetime import timedelta
from pathlib import Path
from timeit import default_timer as timer

log = logging.getLogger(__name__)

def monkeyPatchAllFSFunctionsForDebugMode():
    """
    "monkey patch" all fs-changing function calls so that they just log the line. Useful for debugging purposes only.
    """
    def wrap_function(returnInstance=None, *args, **kwargs):
        # Get the current call stack frame
        stack = traceback.extract_stack()
        caller_frame = stack[-2]
        if "lambda" in caller_frame._line:
            caller_frame = stack[-3]
        log.debug(f"**DEBUGMODE**: {caller_frame._line} args: {args} kwargs: {kwargs}")
        if returnInstance:
            return returnInstance
    subprocess.run = lambda *args, **kwargs: wrap_function(returnInstance=subprocess.CompletedProcess(args={}, returncode=0), args=args, kwargs=kwargs)
    shutil.rmtree = wrap_function
    shutil.copy = wrap_function
    shutil.copyfile = wrap_function
    shutil.move = wrap_function
    Path.rmdir = wrap_function
    Path.unlink = wrap_function
    Path.mkdir = wrap_function
    Path.stat = lambda *args, **kwargs: wrap_function(returnInstance=os.stat(Path("test")))

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

class Timer:
    """
    context manager to measure the time that passed for the execution of the statements within.
    Usage:
        with Timer() as timer:
            # do_something_long
        print(timer.elapsedTime)
    """
    def __enter__(self):
        self.start = getTimer()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Code to execute at the end of the block
        # if exc_type is None:
        #     log.debug("Exiting the timer context normally")
        # else:
        #     log.debug(f"Exiting the timer context with an exception: {exc_type}, {exc_value}")
        self.elapsedTime = getElapsedTime(self.start)
