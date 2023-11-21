import logging
import os
import shutil
import subprocess
import traceback
from datetime import timedelta
from pathlib import Path
from timeit import default_timer as timer
from typing import List

from esm.ConfigModels import MainConfig

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

def askUser(question, answerForTrue, override=None):
    """
    asks the user for input, returns true if the answer was 'answerForTrue'
    """
    if override:
        log.warning(f"using override for user input: {override}")
        answer = override
    else:
        log.debug(f"asking for user input: {question}")
        answer = input(question).lower()
        log.debug(f"user answered with '{answer}'")
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
        self.elapsedTime = getElapsedTime(self.start)

def mergeDicts(a: dict, b: dict, path=[], logOverwrites=False, allowOverwrites=True):
    """
    deep merges dict b into dict a, will mutate dict a in the process. same keys will be overwritten by default.
    """
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                mergeDicts(a[key], b[key], path + [str(key)])
            elif a[key] != b[key]:
                if logOverwrites:
                    print(f"overwritten a[key] with b[key]: key: {key}, old value: {a[key]}, new value: {b[key]}")
                if not allowOverwrites:
                    raise Exception('Conflict at ' + '.'.join(path + [str(key)]))
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a    

def extractSystemAndPlayfieldNames(names: List[str]):
    """
    returns two lists, one with the playfields extracted from the names
    the other ones with the system names, of the name in the list was prefixed with a "S:" or "s:"
    """
    playfields = []
    solarsystems = []
    for name in names:
        if name.lower().startswith("s:"):
            solarsystems.append(name[2:])
        else:
            playfields.append(name)
    return solarsystems, playfields

def byteArrayToString(byteArray: bytearray, encoding="UTF-8"):
    if byteArray == None or len(byteArray) < 1:
        return ""
    try:
        decoded_string = byteArray.decode(encoding)
        return decoded_string
    except UnicodeDecodeError:
        return None
