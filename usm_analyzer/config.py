"""Central configuration for the USM analyzer application."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

APP_NAME: Final[str] = "USM Analyzer"
APP_ORG: Final[str] = "Industrial Diagnostics"


@dataclass(frozen=True)
class LoggingConfig:
    """Logging behavior for console and rotating file handlers."""

    logger_name: str = "usm_analyzer"
    level: str = "INFO"
    log_dir: Path = Path.home() / ".usm_analyzer" / "logs"
    file_name: str = "usm_analyzer.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 5
    format: str = (
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "%(filename)s:%(lineno)d | %(message)s"
    )


@dataclass(frozen=True)
class DataLoaderConfig:
    """Configuration values for CSV loading and cleaning."""

    supported_encodings: tuple[str, ...] = ("utf-8", "latin1", "cp1252")
    csv_separators: tuple[str, ...] = (",", ";", "\t", "|")
    time_column_candidates: tuple[str, ...] = (
        "timestamp",
        "time",
        "datetime",
        "date_time",
        "logtime",
        "sampletime",
        "recorded_at",
    )
    datetime_parse_threshold: float = 0.70
    numeric_parse_threshold: float = 0.80
    min_non_na_ratio: float = 0.05
    low_memory: bool = False


@dataclass(frozen=True)
class AppConfig:
    """Aggregated application configuration."""

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    data_loader: DataLoaderConfig = field(default_factory=DataLoaderConfig)


DEFAULT_CONFIG: Final[AppConfig] = AppConfig()
