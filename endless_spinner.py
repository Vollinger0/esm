import logging
from pathlib import Path
import time
from esm.EsmLogger import EsmLogger

log = logging.getLogger(__name__)

print("Starting sleep phase, press CTRL+C to end.")
EsmLogger.setUpLogging(f"{Path(__file__).name}.log")

with EsmLogger.console.status("Running...") as status:
    try:
        while True:
            time.sleep(.5)
            log.debug("some text to garble up the spinner")
            time.sleep(.5)
            log.info("some text to garble up the spinner")
            time.sleep(.5)
            log.warning("some text to garble up the spinner some text to garble up the spinner some text to garble up the spinner some text to garble up the spinner some text to garble up the spinner ")
            time.sleep(.5)
            log.error("some text to garble up the spinner")
            pass
    except KeyboardInterrupt:
        status.stop()
        EsmLogger.console.log("Done")
        pass
print("The end.")
