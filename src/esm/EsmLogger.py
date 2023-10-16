import logging

class EsmLogger:

    @staticmethod 
    def setUpLogging(logFile, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG):
        # set a nice logging line and logging level, including proper logging to a logfile
        fileLoggingHandler = logging.FileHandler(logFile)
        # debug level for the logfile
        fileLoggingHandler.setLevel(fileLogLevel)
        streamHandler = logging.StreamHandler()
        # info level for the console
        # streamHandler.setLevel(logging.INFO)
        streamHandler.setLevel(streamLogLevel)
        logging.basicConfig(
            format="[%(asctime)s] %(levelname)s %(message)s", 
            datefmt='%Y-%m-%d %H:%M:%S',
            level=logging.DEBUG,
            handlers=[
                streamHandler,
                fileLoggingHandler
            ])
