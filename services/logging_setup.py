
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(server_name, log_directory):
    """
    Configure logging for the Broker or Exchange Server.

    Each server writes to its own rotating log file.
    Repeated configuration must not duplicate handlers.
    """

    if server_name not in ("broker", "exchange"):
        raise ValueError("Unknown server name.")

    log_directory = Path(log_directory)

    log_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    log_path = log_directory / f"{server_name}.log"

    logger = logging.getLogger(server_name)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Normalize paths to handle Windows path differences.
    target_path = os.path.normcase(
        os.path.abspath(log_path)
    )

    # Reuse an existing handler for the same file.
    # Remove obsolete rotating file handlers.
    for handler in list(logger.handlers):

        if isinstance(handler, RotatingFileHandler):

            existing_path = os.path.normcase(
                os.path.abspath(handler.baseFilename)
            )

            if existing_path == target_path:
                return logger

            logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    )

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger
