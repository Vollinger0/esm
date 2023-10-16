import logging
from pathlib import Path

from EsmLogger import EsmLogger

EsmLogger.setUpLogging("x")
log = logging.getLogger(__name__)

directory = Path(".")
log.info(directory.glob("*"))
for entry in directory.glob("*"):
    if entry.is_dir():
        log.debug(f"entry: {entry}")