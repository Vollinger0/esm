import logging
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console

class EsmLogger:
    """
    provides facilities for logging
    """
    console = None # global rich console to use for logging to console
    
    @staticmethod 
    def setUpLogging(logFile, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG):
        dateformat = "%Y-%m-%d %H:%M:%S"
        EsmLogger.console = Console(log_time_format=dateformat)
        
        # set a nice logging line and logging level for the logfile
        fileLoggingHandler = logging.FileHandler(logFile)
        fileLoggingHandler.setLevel(fileLogLevel)
        fileLoggingHandler.setFormatter(logging.Formatter(fmt="[%(asctime)s] %(process)d %(levelname)s %(message)s", datefmt=dateformat))
        
        # use rich stream handler for stdout, will reuse the global console object, since logging can't handle spinners and animations.
        # this will make for a very colorful terminal output... a bit too much for my taste, but better than plain white.
        streamHandler = RichHandler(show_path=False, console=EsmLogger.console)
        streamHandler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt=dateformat))
        streamHandler.setLevel(streamLogLevel)

        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[
                streamHandler,
                fileLoggingHandler
            ],
            force=True)
        logging.debug(f"Logging initialized, logging to: '{Path(logFile).resolve()}'")
