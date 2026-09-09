import logging
from logging.handlers import RotatingFileHandler
import config


def configure_logging():
    config.LOG_FOLDER.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("weekly_report")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            config.LOG_FOLDER / "report_generator.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger
