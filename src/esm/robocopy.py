import subprocess
import logging

log = logging.getLogger(__name__)

def execute(src, dst, options='', logFile="robocopy.log", encoding="ansi"):
    # extend the options, so robocopy logs to an own file
    alloptions = []
    alloptions.extend(options)
    alloptions.append(f"/unilog+:{logFile}")
    command = f'robocopy "{src}" "{dst}" {" ".join(alloptions)}'
    log.debug(f"Executing command: {command}")
    # result = subprocess.run(command, capture_output=True, text=True)
    result = subprocess.run(command, capture_output=True, text=True, encoding=encoding)
    log.debug(f"Robocopy finished: {result}")
    return result
