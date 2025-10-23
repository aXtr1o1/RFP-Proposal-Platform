import logging
import sys
from datetime import datetime

_LEVEL_PAD = 5  # align INFO/WARN/ERROR

class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        lvl = record.levelname[:5].ljust(_LEVEL_PAD)
        name = record.name.ljust(10)[:10]
        msg = record.getMessage()
        return f"{ts} | {lvl} | {name} | {msg}"

def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(PlainFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
