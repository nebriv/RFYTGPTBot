import logging

# Create a logger named 'myapp'
logger = logging.getLogger('RFYTGPTBot')
logger.setLevel(logging.INFO)  # Set level for your application
logger.propagate = False
# Create a console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)  # Or whichever level you want

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s (%(module)s.%(funcName)s) - %(levelname)s - %(message)s')

# Add formatter to ch
ch.setFormatter(formatter)

logger.addHandler(ch)

# This line sets the logging level for all third-party libraries to WARNING
logging.getLogger().setLevel(logging.WARNING)