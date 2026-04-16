"""Logging utilities for the USM analyzer."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from usm_analyzer.config import LoggingConfig


def _build_console_handler(fmt: str) -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    return handler


def _build_file_handler(config: LoggingConfig) -> logging.Handler:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    file_path: Path = config.log_dir / config.file_name
    handler = RotatingFileHandler(
        filename=file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(config.format))
    return handler


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Create or reconfigure the application logger.

    Calling this function multiple times is safe: existing handlers are removed
    before applying new configuration to prevent duplicate logs.
    """

    logger = logging.getLogger(config.logger_name)
    level = getattr(logging, config.level.upper(), logging.INFO)

    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    logger.addHandler(_build_console_handler(config.format))
    logger.addHandler(_build_file_handler(config))
    return logger


def get_logger(name: str | None = None, root_name: str = "usm_analyzer") -> logging.Logger:
    """Return a namespaced logger.

    Parameters
    ----------
    name:
        Optional child logger name. If omitted, returns the root application logger.
    root_name:
        Root logger name configured by :func:`setup_logging`.
    """

    if not name:
        return logging.getLogger(root_name)
    return logging.getLogger(f"{root_name}.{name}")
