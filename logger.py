import logging

# Create a logger named 'myapp'
logger = logging.getLogger('myapp')
logger.setLevel(logging.DEBUG)  # Set level for your application

# Create a console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)  # Or whichever level you want

# Create formatter
formatter = logging.Formatter('%(name)s (%(module)s.%(funcName)s) - %(levelname)s - %(message)s')

# Add formatter to ch
ch.setFormatter(formatter)

# Add ch to logger
logger.addHandler(ch)

# This line sets the logging level for all third-party libraries to WARNING
logging.getLogger().setLevel(logging.WARNING)