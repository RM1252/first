"""Left control panel for file and parameter selection."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from usm_analyzer.ui.parameter_buttons import ParameterButtonsWidget, extract_base_parameter


@dataclass(slots=True)
class FileNode:
    file_name: str
    columns: list[str]


class LeftPanel(QWidget):
    """Primary diagnostics control panel."""

    load_files_requested = pyqtSignal()
    plot_requested = pyqtSignal(list, list)  # selected_files, selected_parameters

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._file_data: dict[str, FileNode] = {}

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self._build_loader_group(root_layout)
        self._build_file_tree_group(root_layout)
        self._build_parameter_button_group(root_layout)
        self._build_parameter_tree_group(root_layout)

        self.plot_button = QPushButton("Plot Selected", self)
        self.plot_button.clicked.connect(self._emit_plot_request)
        root_layout.addWidget(self.plot_button)
        root_layout.addStretch(1)

    def _build_loader_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("File Loader", self)
        layout = QHBoxLayout(group)

        self.load_button = QPushButton("Load CSV", group)
        self.load_button.clicked.connect(self.load_files_requested.emit)

        self.status_label = QLabel("No files loaded", group)
        self.status_label.setWordWrap(True)

        layout.addWidget(self.load_button)
        layout.addWidget(self.status_label, 1)

        parent_layout.addWidget(group)

    def _build_file_tree_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("File Selection", self)
        layout = QVBoxLayout(group)

        self.file_tree = QTreeWidget(group)
        self.file_tree.setHeaderLabels(["File", "Rows"])
        self.file_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        layout.addWidget(self.file_tree)
        parent_layout.addWidget(group)

    def _build_parameter_button_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Parameter Buttons", self)
        layout = QVBoxLayout(group)

        self.parameter_buttons = ParameterButtonsWidget(group)
        self.parameter_buttons.parameter_group_selected.connect(self._apply_parameter_group_selection)

        layout.addWidget(self.parameter_buttons)
        parent_layout.addWidget(group)

    def _build_parameter_tree_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Parameter Tree", self)
        layout = QVBoxLayout(group)

        self.parameter_tree = QTreeWidget(group)
        self.parameter_tree.setHeaderLabels(["Parameter"])
        self.parameter_tree.itemChanged.connect(self._on_parameter_item_changed)

        layout.addWidget(self.parameter_tree)
        parent_layout.addWidget(group, 1)

    def set_loaded_files(self, file_nodes: list[FileNode], row_counts: dict[str, int] | None = None) -> None:
        """Refresh file tree and parameter controls from loaded files."""

        row_counts = row_counts or {}
        self._file_data = {node.file_name: node for node in file_nodes}

        self.file_tree.clear()
        for node in file_nodes:
            item = QTreeWidgetItem([node.file_name, str(row_counts.get(node.file_name, "-"))])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
            self.file_tree.addTopLevelItem(item)

        all_columns = sorted({column for node in file_nodes for column in node.columns})
        self.parameter_buttons.set_columns(all_columns)
        self._populate_parameter_tree(all_columns)

        self.status_label.setText(f"Loaded {len(file_nodes)} file(s)")

    def _populate_parameter_tree(self, columns: list[str]) -> None:
        self.parameter_tree.blockSignals(True)
        self.parameter_tree.clear()

        grouped: dict[str, list[str]] = {}
        for column in columns:
            grouped.setdefault(extract_base_parameter(column), []).append(column)

        for base_parameter in sorted(grouped):
            parent = QTreeWidgetItem([base_parameter])
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsTristate | Qt.ItemFlag.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.CheckState.Unchecked)

            for column in sorted(grouped[base_parameter]):
                child = QTreeWidgetItem([column])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                parent.addChild(child)

            self.parameter_tree.addTopLevelItem(parent)

        self.parameter_tree.expandAll()
        self.parameter_tree.blockSignals(False)

    def _apply_parameter_group_selection(self, _base_parameter: str, matched_columns: list[str]) -> None:
        """Clear old selections and select all columns under the clicked base parameter."""

        self.parameter_tree.blockSignals(True)
        for i in range(self.parameter_tree.topLevelItemCount()):
            parent = self.parameter_tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                state = Qt.CheckState.Checked if child.text(0) in matched_columns else Qt.CheckState.Unchecked
                child.setCheckState(0, state)
        self.parameter_tree.blockSignals(False)

    def _on_parameter_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if item.childCount() > 0:
            return

        # Synchronize parent check state for better UX.
        parent = item.parent()
        if parent is None:
            return

        checked = 0
        for i in range(parent.childCount()):
            if parent.child(i).checkState(0) == Qt.CheckState.Checked:
                checked += 1

        if checked == 0:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        elif checked == parent.childCount():
            parent.setCheckState(0, Qt.CheckState.Checked)
        else:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _selected_files(self) -> list[str]:
        files: list[str] = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                files.append(item.text(0))
        return files

    def _selected_parameters(self) -> list[str]:
        selected: list[str] = []
        for i in range(self.parameter_tree.topLevelItemCount()):
            parent = self.parameter_tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    selected.append(child.text(0))
        return selected

    def _emit_plot_request(self) -> None:
        self.plot_requested.emit(self._selected_files(), self._selected_parameters())
