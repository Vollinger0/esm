
from pathlib import Path
import logging

log = logging.getLogger(__name__)

class EcfReader:
    """
        reads an ecf file
    """
    def __init__(self, filePath: Path):
        self.filePath = filePath
