import logging

class EsmLogger:

    @staticmethod 
    def setUpLogging(logFile):
        # set a nice logging line and logging level, including proper logging to a logfile
        fileLoggingHandler = logging.FileHandler(logFile)
        # debug level for the logfile
        fileLoggingHandler.setLevel(logging.DEBUG)
        streamHandler = logging.StreamHandler()
        # info level for the console
        # streamHandler.setLevel(logging.INFO)
        streamHandler.setLevel(logging.DEBUG)
        logging.basicConfig(
            format="[%(asctime)s] %(levelname)s %(message)s", 
            datefmt='%Y-%m-%d %H:%M:%S',
            level=logging.DEBUG,
            handlers=[
                streamHandler,
                fileLoggingHandler
            ])
