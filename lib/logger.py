import logging

# Define custom VERBOSE level and logging method
VERBOSE = 15
logging.addLevelName(VERBOSE, "VERBOSE")

def verbose(self, message, *args, **kws):
    if self.isEnabledFor(VERBOSE):
        self._log(VERBOSE, message, args, **kws)

logging.Logger.verbose = verbose

# Create and configure logger and handler
logger = logging.getLogger('RFYTGPTBot')
logger.setLevel(logging.DEBUG)
logger.propagate = False  # Prevent log records from being passed to the handlers of ancestor loggers

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s (%(module)s.%(funcName)s) - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Configure the root logger
logging.getLogger().setLevel(logging.WARNING)
