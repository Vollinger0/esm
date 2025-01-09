import logging
import os
import re
import shutil
import socket
import subprocess
import traceback
from ruamel.yaml import YAML
from datetime import timedelta
from pathlib import Path
from timeit import default_timer as timer
from typing import List

from esm.ConfigModels import MainConfig
from esm.DataTypes import ZipFile
from esm.exceptions import AdminRequiredException

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

def getOwnIp(config: MainConfig):
    """
    return the external ip of the server from the context or find it out calling findMyOwnIp()
    """
    if not config.context.get("myOwnIp"):
        config.context["myOwnIp"] = findMyOwnIp()
    return config.context.get("myOwnIp")

def findMyOwnIp():
    """
    return the external ip of the server from the internet
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        myIp = s.getsockname()[0]
    except Exception:
        myIp = '127.0.0.1'
    finally:
        s.close()
    return myIp

def findZipFileByName(zipFileList: List[ZipFile], containedIn: str = None, startsWith: str = None) -> ZipFile:
    """
    returns the according zipfile of the list if the name is in containedIn or starts with startsWith
    """
    for zipFile in zipFileList:
        if containedIn and zipFile.name in containedIn:
            return zipFile
        if startsWith and zipFile.name.startswith(startsWith):
            return zipFile
    return None

def validateScenario(sourcePath: Path):
    """
        checks if the scenario is valid throws an exception if not
    """
    if not sourcePath.is_dir():
        raise AdminRequiredException(f"'{sourcePath}' is not a directory. Please check the configuration.")
    validateYamlFiles(sourcePath)

def validateYamlFiles(sourcePath: Path):
    """
        checks all the scenario's yaml files
    """
    yaml = YAML(typ='safe')
    # allow duplicate keys since they are all over the place
    yaml.allow_duplicate_keys = True
    yaml.allow_unicode = True

    validYamlFiles = 0
    invalidYamlFiles = 0
    brokenYamlFiles = 0
    ignoredYamlFiles = 0

    log.info(f"Validating scenario yaml files")
    with Timer() as timer:
        # walk through the whole directory, validate all yaml files
        for root, dirs, files in sourcePath.walk():
            for file in files:  
                if file.endswith(".yml") or file.endswith(".yaml"):
                    if file.startswith("+"): 
                        ignoredYamlFiles += 1
                        continue
                    path = Path(root).joinpath(file)
                    try:
                        loadYamlFile(yaml, Path(path))
                        validYamlFiles += 1
                    except Exception as e1:
                        invalidYamlFiles += 1
                        log.warning(f"Failed to load file '{path}': {e1} - trying again with preprocessing to remove yaml-illegal shenanigans")
                        try:
                            loadYamlFile(yaml, Path(path), preprocess=True)
                        except Exception as e2:
                            log.warning(f"Failed to load file again '{path}': {e2} - trying again with 'iso-8859-1' encoding")
                            try:
                                loadYamlFile(yaml, Path(path), preprocess=True, encoding="iso-8859-1")
                            except Exception as e3:
                                log.error(f"Failed to load file '{path}': {e3} - file must be broken. If it is not, this tool needs to learn what else to accept. Please open an issue on github.")
                                brokenYamlFiles += 1

    log.info(f"Validation took {timer.elapsedTime}. Ignored files: {ignoredYamlFiles}, valid: {validYamlFiles}, invalid but readable: {invalidYamlFiles}, broken: {brokenYamlFiles}.")
    if brokenYamlFiles > 0:
        raise AdminRequiredException(f"Scenario contains broken files. Please fix them and try again.")
    else:                          
        log.info(f"The scenarios yaml files should be valid.")

def loadYamlFile(yaml: YAML, filePath: Path, preprocess: bool = False, encoding: str = "utf-8"):
    """
        parse the yaml file, return false if it is invalid.
    """
    with open(filePath, "r", encoding=encoding) as f:
        content = f.read()
        if preprocess:
            content = filterEgsYamlShenanigans(content)
        yaml.load(content)

def filterEgsYamlShenanigans(content):
    """
        filters out shenanigans from the egs yaml files
    """
    # a ton of files have this illegal property value: - Name: =
    # no yaml parser can ignore this easily, so we have to remove this in this preprocessing
    filteredContent = re.sub(r"- Name:\s*=", "- Name: \"=\"", content, flags=re.MULTILINE)
    return filteredContent

