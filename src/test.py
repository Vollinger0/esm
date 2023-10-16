from glob import glob
import logging
from pathlib import Path

from esm.EsmMain import EsmMain
from esm.FsTools import FsTools

esm = EsmMain(caller=__file__,
              configFileName="esm-config.yaml"
              )
log = logging.getLogger(__name__)

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"debugging is: {esm.config.general.debugMode}")

def resolve_paths(paths, parent_directory="."):
    resolved_paths = []

    # Convert parent_directory to an absolute path
    parent_directory = Path(parent_directory).absolute()

    for path in paths:
        # Check if the path is an absolute path
        if Path(path).absolute():
            # Expand glob patterns and append to the resolved_paths list
            resolved_paths.extend(glob(path))
        else:
            # Resolve relative paths, expand glob patterns, and append to the resolved_paths list
            absolute_path = Path(parent_directory).absolute().joinpath(path)
            resolved_paths.extend(glob(absolute_path))

    return resolved_paths


userentries = [
    "d:/egs/empyrion/test.txt",
    "d:/egs/empyrion/*.txt",
    "foo/bar/baz.txt",
    "foo/bar/*.txt"
    ]

parent = Path(".").absolute()

entries = []

for entry in userentries:
    log.debug(f"entry: {entry}")

    if Path(entry).absolute():
        if FsTools.isGlobPattern(entry):
            entries.extend(glob(entry))
        else:
            entries.append(entry)
    else:
        if FsTools.isGlobPattern(entry):
            entries.extend(glob(entry))
        else:
            entries.append(Path(parent).joinpath(entry))
            
log.debug(f"entries {entries}")

test = resolve_paths(userentries)
log.debug(f"test: {test}")


