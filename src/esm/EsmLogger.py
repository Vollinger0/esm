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
    handlers = list()
    
    @staticmethod 
    def setUpLogging(logFile: str|Path=None, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG):
        dateformat = "%Y-%m-%d %H:%M:%S"
        EsmLogger.console = Console(log_time_format=dateformat)
        
        EsmLogger.handlers = list()

        # use rich stream handler for stdout, will reuse the global console object, since logging can't handle spinners and animations.
        # this will make for a very colorful terminal output... a bit too much for my taste, but better than plain white.
        streamHandler = RichHandler(show_path=False, console=EsmLogger.console)
        streamHandler.setFormatter(logging.Formatter(fmt="%(thread)d %(message)s", datefmt=dateformat))
        #streamHandler.setFormatter(logging.Formatter(fmt="[%(asctime)s] %(process)d %(thread)d %(name)s %(levelname)s %(message)s", datefmt=dateformat))
        streamHandler.setLevel(streamLogLevel)
        EsmLogger.streamLogLevel = streamLogLevel
        EsmLogger.handlers.append(streamHandler)

        if logFile:
            # set a nice logging line and logging level for the logfile
            fileLoggingHandler = logging.FileHandler(logFile)
            fileLoggingHandler.setLevel(fileLogLevel)
            EsmLogger.fileLogLevel = fileLogLevel
            fileLoggingHandler.setFormatter(logging.Formatter(fmt="[%(asctime)s] %(process)d %(thread)d %(levelname)s %(message)s", datefmt=dateformat))
            EsmLogger.handlers.append(fileLoggingHandler)

        logging.basicConfig(
            level=logging.DEBUG,
            handlers=EsmLogger.handlers,
            force=True)
        
        if logFile:
            logging.debug(f"Logging initialized, logging to: '{Path(logFile).resolve()}'")
        else:
            logging.debug(f"Logging initialized, logging to console only")

    @staticmethod
    def configureUvicornLogging(logLevel=None):
        """
        Configure Uvicorn's logging to use the same handlers as EsmLogger
        Make sure to have set ip EsmLogger via first!
        """
        handlers = EsmLogger.handlers

        if logLevel is None:
            logLevel = EsmLogger.streamLogLevel

        # Configure Uvicorn loggers
        uvicorn_loggers = [
            'uvicorn',
            'uvicorn.access',
            'uvicorn.error'
        ]
        
        for logger_name in uvicorn_loggers:
            logger = logging.getLogger(logger_name)
            
            # Remove existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            
            # Add the handlers from EsmLogger
            for handler in handlers:
                logger.addHandler(handler)
            
            # Set the log level
            logger.setLevel(logLevel)
        
        logging.debug("Uvicorn logging configured to use EsmLogger handlers")
