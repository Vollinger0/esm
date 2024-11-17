import logging
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console

class EsmLogger:
    """
    provides facilities for logging
    """
    console = None # global rich console to use for logging to console
    fileLogLevel = logging.DEBUG
    streamLogLevel = logging.DEBUG
    
    @staticmethod 
    def setUpLogging(logFile: str|Path=None, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG):
        dateformat = "%Y-%m-%d %H:%M:%S"
        EsmLogger.console = Console(log_time_format=dateformat)
        
        handlers = list()

        # use rich stream handler for stdout, will reuse the global console object, since logging can't handle spinners and animations.
        # this will make for a very colorful terminal output... a bit too much for my taste, but better than plain white.
        streamHandler = RichHandler(show_path=False, console=EsmLogger.console)
        streamHandler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt=dateformat))
        streamHandler.setLevel(streamLogLevel)
        EsmLogger.streamLogLevel = streamLogLevel
        handlers.append(streamHandler)

        if logFile:
            # set a nice logging line and logging level for the logfile
            fileLoggingHandler = logging.FileHandler(logFile)
            fileLoggingHandler.setLevel(fileLogLevel)
            EsmLogger.fileLogLevel = fileLogLevel
            fileLoggingHandler.setFormatter(logging.Formatter(fmt="[%(asctime)s] %(process)d %(levelname)s %(message)s", datefmt=dateformat))
            handlers.append(fileLoggingHandler)

        logging.basicConfig(
            level=logging.DEBUG,
            handlers=handlers,
            force=True)
        
        if logFile:
            logging.debug(f"Logging initialized, logging to: '{Path(logFile).resolve()}'")
        else:
            logging.debug(f"Logging initialized, logging to console only")
