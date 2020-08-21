"""Logging utilities for consistent logging within purepyvmware"""

import logging
import os

from logging import handlers
from pathlib import Path

HOME = str(Path.home())
LOG_FILE = os.path.join(HOME, 'purepyvmware.log')
FORMATTER = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG_HANDLER = handlers.RotatingFileHandler(LOG_FILE, maxBytes=2097152, backupCount=3)
LOG_HANDLER.setLevel(logging.INFO)
LOG_HANDLER.setFormatter(FORMATTER)

logging.basicConfig(level=logging.INFO, handlers=[LOG_HANDLER])
