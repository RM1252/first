"""Asynchronous CSV loading and cleaning for USM log files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from usm_analyzer.config import DataLoaderConfig
from usm_analyzer.utils.logger import get_logger


@dataclass(slots=True)
class LoadedFile:
    """Loaded and normalized CSV result."""

    file_path: str
    file_name: str
    dataframe: pd.DataFrame
    time_column: str | None
    encoding_used: str
    separator_used: str


class CSVLoadWorker(QObject):
    """QObject worker that loads and cleans multiple CSV files."""

    file_loaded = pyqtSignal(object)  # LoadedFile
    progress = pyqtSignal(int, int, str)  # current, total, path
    error = pyqtSignal(str, str)  # path, message
    finished = pyqtSignal(list)  # list[LoadedFile]

    def __init__(self, file_paths: list[str], config: DataLoaderConfig) -> None:
        super().__init__()
        self._file_paths = [str(Path(p)) for p in file_paths]
        self._config = config
        self._cancel_requested = False
        self._logger = get_logger("data_loader")

    def stop(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        total = len(self._file_paths)
        results: list[LoadedFile] = []

        self._logger.info("Starting CSV load for %d file(s)", total)
        for index, file_path in enumerate(self._file_paths, start=1):
            if self._cancel_requested:
                self._logger.warning("CSV loading cancelled by user")
                break

            self.progress.emit(index, total, file_path)
            try:
                loaded = self._load_single_file(file_path)
                results.append(loaded)
                self.file_loaded.emit(loaded)
                self._logger.info(
                    "Loaded %s (%d rows, %d columns)",
                    loaded.file_name,
                    len(loaded.dataframe),
                    len(loaded.dataframe.columns),
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self._logger.exception("Failed to load file: %s", file_path)
                self.error.emit(file_path, message)

        self.finished.emit(results)

    def _load_single_file(self, file_path: str) -> LoadedFile:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        dataframe, encoding, separator = self._read_csv_with_fallback(file_path)
        cleaned_df, time_column = self._clean_dataframe(dataframe)

        if cleaned_df.empty:
            raise ValueError("No valid data remained after cleaning")

        return LoadedFile(
            file_path=file_path,
            file_name=Path(file_path).name,
            dataframe=cleaned_df,
            time_column=time_column,
            encoding_used=encoding,
            separator_used=separator,
        )

    def _read_csv_with_fallback(self, file_path: str) -> tuple[pd.DataFrame, str, str]:
        errors: list[str] = []

        for encoding in self._config.supported_encodings:
            for sep in self._config.csv_separators:
                try:
                    df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        sep=sep,
                        low_memory=self._config.low_memory,
                    )
                    if len(df.columns) <= 1:
                        continue
                    return df, encoding, sep
                except UnicodeDecodeError as exc:
                    errors.append(f"{encoding}/{sep}: {exc}")
                except pd.errors.ParserError as exc:
                    errors.append(f"{encoding}/{sep}: {exc}")

        raise ValueError(
            "Unable to parse CSV with supported encodings and separators. "
            f"Attempts: {'; '.join(errors[:5])}"
        )

    def _clean_dataframe(self, df: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
        cleaned = df.copy()
        cleaned.columns = [str(c).strip() for c in cleaned.columns]

        time_col = self._detect_time_column(cleaned)
        if time_col:
            cleaned[time_col] = pd.to_datetime(cleaned[time_col], errors="coerce", utc=False)
            pre_drop = len(cleaned)
            cleaned = cleaned.dropna(subset=[time_col])
            if pre_drop != len(cleaned):
                self._logger.debug("Dropped %d rows with invalid timestamps", pre_drop - len(cleaned))
            cleaned = cleaned.sort_values(by=time_col).reset_index(drop=True)

        cleaned = self._convert_numeric_columns(cleaned, protected_column=time_col)

        min_non_na = max(1, int(len(cleaned) * self._config.min_non_na_ratio))
        cleaned = cleaned.dropna(axis=1, thresh=min_non_na)

        numeric_cols = [c for c in cleaned.columns if c != time_col and pd.api.types.is_numeric_dtype(cleaned[c])]
        if numeric_cols:
            pre_drop = len(cleaned)
            cleaned = cleaned.dropna(subset=numeric_cols, how="all")
            if pre_drop != len(cleaned):
                self._logger.debug(
                    "Dropped %d rows where all numeric values are invalid",
                    pre_drop - len(cleaned),
                )

        return cleaned.reset_index(drop=True), time_col

    def _detect_time_column(self, df: pd.DataFrame) -> str | None:
        lowered = {c.lower(): c for c in df.columns}

        for candidate in self._config.time_column_candidates:
            if candidate in lowered:
                return lowered[candidate]

        best_col: str | None = None
        best_ratio = 0.0

        sample_size = min(len(df), 500)
        if sample_size == 0:
            return None

        sample = df.head(sample_size)
        for col in df.columns:
            series = sample[col]
            if not pd.api.types.is_object_dtype(series) and not pd.api.types.is_string_dtype(series):
                continue

            parsed = pd.to_datetime(series, errors="coerce", utc=False)
            ratio = parsed.notna().mean()
            if ratio > best_ratio:
                best_ratio = ratio
                best_col = col

        if best_ratio >= self._config.datetime_parse_threshold:
            return best_col
        return None

    def _convert_numeric_columns(self, df: pd.DataFrame, protected_column: str | None) -> pd.DataFrame:
        for column in df.columns:
            if column == protected_column:
                continue

            series = df[column]
            if pd.api.types.is_numeric_dtype(series):
                continue

            as_str = series.astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            converted = pd.to_numeric(as_str, errors="coerce")

            non_na_count = as_str.notna().sum()
            if non_na_count == 0:
                continue

            success_ratio = converted.notna().sum() / non_na_count
            if success_ratio >= self._config.numeric_parse_threshold:
                df[column] = converted

        return df


class CSVLoadThread(QThread):
    """QThread wrapper that owns a :class:`CSVLoadWorker` instance."""

    file_loaded = pyqtSignal(object)
    progress = pyqtSignal(int, int, str)
    error = pyqtSignal(str, str)
    completed = pyqtSignal(list)

    def __init__(self, file_paths: list[str], config: DataLoaderConfig) -> None:
        super().__init__()
        self._worker = CSVLoadWorker(file_paths=file_paths, config=config)
        self._worker.moveToThread(self)

        self.started.connect(self._worker.run)
        self._worker.file_loaded.connect(self.file_loaded)
        self._worker.progress.connect(self.progress)
        self._worker.error.connect(self.error)
        self._worker.finished.connect(self._on_worker_finished)

    def cancel(self) -> None:
        self._worker.stop()

    def _on_worker_finished(self, results: list[LoadedFile]) -> None:
        self.completed.emit(results)
        self.quit()
        self.wait(1000)


def load_csv_files_sync(file_paths: list[str], config: DataLoaderConfig) -> list[LoadedFile]:
    """Synchronous helper for tests/CLI workflows."""

    worker = CSVLoadWorker(file_paths=file_paths, config=config)
    loaded_results: list[LoadedFile] = []
    worker.file_loaded.connect(loaded_results.append)
    worker.run()
    return loaded_results


def summarize_loaded_files(files: list[LoadedFile]) -> list[dict[str, Any]]:
    """Return lightweight metadata for loaded file list."""

    return [
        {
            "file_path": item.file_path,
            "file_name": item.file_name,
            "rows": len(item.dataframe),
            "columns": list(item.dataframe.columns),
            "time_column": item.time_column,
            "encoding": item.encoding_used,
            "separator": item.separator_used,
        }
        for item in files
    ]
