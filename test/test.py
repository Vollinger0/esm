import logging
from pathlib import Path
import time
from esm.EsmMain import EsmMain
from esm.Tools import Timer

esm = EsmMain(caller="test")
log = logging.getLogger(__name__)
