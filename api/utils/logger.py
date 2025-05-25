import logging
import sys

#configure logging
logger = logging.getLogger("MCPClient")
logger.setLevel(logging.DEBUG)

#file handler with debug level
file_handler=logging.FileHandler("mcp-client.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

#console handler with info level
console_handler=logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)