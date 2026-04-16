"""Main application window for USM analyzer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usm_analyzer.config import DEFAULT_CONFIG
from usm_analyzer.core.data_loader import CSVLoadThread, LoadedFile
from usm_analyzer.plotting.plot_engine import PlotEngine, PlotRequest
from usm_analyzer.ui.left_panel import FileNode, LeftPanel
from usm_analyzer.ui.plot_window import PlotWindow
from usm_analyzer.utils.logger import get_logger


class MainWindow(QMainWindow):
    """Top-level UI container that orchestrates loading and selection workflow."""

    def __init__(self) -> None:
        super().__init__()

        self._logger = get_logger("main_window")
        self._active_loader: CSVLoadThread | None = None
        self._loaded_files: dict[str, LoadedFile] = {}
        self._plot_engine = PlotEngine()
        self._plot_windows: list[PlotWindow] = []

        self.setWindowTitle("USM Analyzer")
        self.resize(1360, 860)

        self._setup_layout()
        self._connect_signals()

    def _setup_layout(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Horizontal, root)
        self.left_panel = LeftPanel(splitter)
        self.preview_table = QTableWidget(splitter)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.preview_table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 1000])

        root_layout.addWidget(splitter)
        self.setCentralWidget(root)

        self.statusBar().showMessage("Ready")

    def _connect_signals(self) -> None:
        self.left_panel.load_files_requested.connect(self._on_load_files_requested)
        self.left_panel.plot_requested.connect(self._on_plot_requested)

    def _on_load_files_requested(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Ultrasonic Meter CSV Logs",
            str(Path.home()),
            "CSV files (*.csv);;All files (*.*)",
        )
        if not file_paths:
            return

        if self._active_loader and self._active_loader.isRunning():
            QMessageBox.warning(self, "Loader Busy", "CSV loading is already in progress.")
            return

        self.statusBar().showMessage("Loading files...")
        self.left_panel.load_button.setEnabled(False)

        loader = CSVLoadThread(file_paths=file_paths, config=DEFAULT_CONFIG.data_loader)
        loader.progress.connect(self._on_loader_progress)
        loader.file_loaded.connect(self._on_file_loaded)
        loader.error.connect(self._on_loader_error)
        loader.completed.connect(self._on_loader_completed)
        loader.finished.connect(lambda: self.left_panel.load_button.setEnabled(True))

        self._active_loader = loader
        loader.start()

    def _on_loader_progress(self, current: int, total: int, file_path: str) -> None:
        self.statusBar().showMessage(f"Loading {current}/{total}: {Path(file_path).name}")

    def _on_file_loaded(self, loaded_file: LoadedFile) -> None:
        self._loaded_files[loaded_file.file_name] = loaded_file

    def _on_loader_error(self, file_path: str, message: str) -> None:
        self._logger.error("Failed loading '%s': %s", file_path, message)
        QMessageBox.critical(
            self,
            "File Load Error",
            f"Failed to load:\n{file_path}\n\nError:\n{message}",
        )

    def _on_loader_completed(self, results: list[LoadedFile]) -> None:
        if not results:
            self.statusBar().showMessage("No files loaded")
            self.left_panel.status_label.setText("No valid files loaded")
            return

        nodes = [FileNode(file_name=item.file_name, columns=list(item.dataframe.columns)) for item in results]
        row_counts = {item.file_name: len(item.dataframe) for item in results}
        self.left_panel.set_loaded_files(nodes, row_counts=row_counts)

        self.statusBar().showMessage(f"Loaded {len(results)} file(s)")
        self._preview_first_file(results[0])

    def _preview_first_file(self, loaded_file: LoadedFile, max_rows: int = 200) -> None:
        df = loaded_file.dataframe.head(max_rows)
        self._set_table_data(df)

    def _set_table_data(self, df: pd.DataFrame) -> None:
        self.preview_table.clear()
        self.preview_table.setRowCount(len(df))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])

        for row_idx in range(len(df)):
            for col_idx, column_name in enumerate(df.columns):
                value = df.iloc[row_idx, col_idx]
                item = QTableWidgetItem("" if pd.isna(value) else str(value))
                self.preview_table.setItem(row_idx, col_idx, item)

        self.preview_table.resizeColumnsToContents()

    def _on_plot_requested(self, selected_files: list[str], selected_parameters: list[str]) -> None:
        if not selected_files:
            QMessageBox.information(self, "No File Selected", "Select at least one file.")
            return

        if not selected_parameters:
            QMessageBox.information(self, "No Parameter Selected", "Select at least one parameter.")
            return

        available = [self._loaded_files[f] for f in selected_files if f in self._loaded_files]
        if not available:
            QMessageBox.warning(self, "Selection Error", "Selected files are no longer available.")
            return

        plot_requests: list[PlotRequest] = []
        for file_data in available:
            matching = [c for c in selected_parameters if c in file_data.dataframe.columns]
            if matching:
                plot_requests.append(
                    PlotRequest(
                        file_name=file_data.file_name,
                        dataframe=file_data.dataframe,
                        time_column=file_data.time_column,
                        selected_parameters=matching,
                    )
                )

        if not plot_requests:
            QMessageBox.warning(
                self,
                "No Matching Columns",
                "Selected parameters are not present in the chosen file(s).",
            )
            return

        figure = self._plot_engine.create_figure(plot_requests)
        plot_window = PlotWindow(figure, title=f"USM Plot ({len(plot_requests)} file(s))")
        plot_window.show()
        self._plot_windows.append(plot_window)

        # Keep tabular preview in sync with selected data from first requested file.
        first = plot_requests[0]
        preview_df = first.dataframe[first.selected_parameters].head(300)
        self._set_table_data(preview_df)
        self.statusBar().showMessage(
            f"Opened plot window for {len(plot_requests)} file(s), {len(selected_parameters)} parameter selection(s)"
        )
