"""Dynamic parameter button controls grouped by base parameter type."""

from __future__ import annotations

import re
from collections import defaultdict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Examples: A1, A2, B1CW, B1CCW, C12, D2CW
_PATH_SUFFIX_RE = re.compile(r"^[A-Z]\d+(?:CW|CCW)?$", re.IGNORECASE)


def normalize_base_parameter(raw_base: str) -> str:
    """Normalize a base parameter to canonical UI form."""

    normalized = raw_base.strip().replace(" ", "")
    normalized = re.sub(r"SOS", "VOS", normalized, flags=re.IGNORECASE)
    return normalized.upper()


def extract_base_parameter(column_name: str) -> str:
    """Extract base parameter name from a full column name.

    Grouping is intentionally based on *base type* and not path.
    Examples
    --------
    - MeasPathVOS_A1 -> MEASPATHVOS
    - MeasPathVOS_B1CW -> MEASPATHVOS
    - MeasPathSOS_B1CCW -> MEASPATHVOS
    """

    name = column_name.strip()
    if not name:
        return ""

    parts = name.split("_")
    if len(parts) > 1 and _PATH_SUFFIX_RE.match(parts[-1]):
        return normalize_base_parameter("_".join(parts[:-1]))

    # Fallback for compact names that may not include underscore separators.
    # Example: MeasPathVOSA1 or MeasPathSNRB1CW.
    compact_match = re.match(r"^(.*?)([A-Z]\d+(?:CW|CCW)?)$", name, re.IGNORECASE)
    if compact_match:
        return normalize_base_parameter(compact_match.group(1))

    return normalize_base_parameter(name)


def group_columns_by_base_parameter(columns: list[str]) -> dict[str, list[str]]:
    """Map base parameter -> full column names for all detected path variants."""

    grouped: dict[str, list[str]] = defaultdict(list)
    for column in columns:
        base = extract_base_parameter(column)
        if base:
            grouped[base].append(column)

    # Preserve deterministic order.
    return {base: sorted(values) for base, values in sorted(grouped.items())}


class ParameterButtonsWidget(QWidget):
    """Horizontal scrollable button strip for base-parameter selection."""

    parameter_group_selected = pyqtSignal(str, list)  # base_parameter, matched_columns

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grouped_columns: dict[str, list[str]] = {}

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self._container = QWidget(self)
        self._button_layout = QHBoxLayout(self._container)
        self._button_layout.setContentsMargins(4, 4, 4, 4)
        self._button_layout.setSpacing(8)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._container)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._scroll)

    def clear_buttons(self) -> None:
        while self._button_layout.count():
            item = self._button_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._button_group.removeButton(widget)
                widget.deleteLater()
        self._grouped_columns.clear()

    def set_columns(self, columns: list[str]) -> None:
        """Rebuild buttons from available columns grouped by base parameter."""

        self.clear_buttons()
        self._grouped_columns = group_columns_by_base_parameter(columns)

        for base_param, matched_columns in self._grouped_columns.items():
            button = QPushButton(base_param, self)
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda checked, bp=base_param, cols=matched_columns: self._on_button_clicked(checked, bp, cols)
            )
            self._button_group.addButton(button)
            self._button_layout.addWidget(button)

        self._button_layout.addStretch(1)

    def _on_button_clicked(self, checked: bool, base_parameter: str, matched_columns: list[str]) -> None:
        if not checked:
            return
        self.parameter_group_selected.emit(base_parameter, matched_columns)

    def select_base_parameter(self, base_parameter: str) -> None:
        for button in self._button_group.buttons():
            if button.text() == base_parameter:
                button.setChecked(True)
                self._on_button_clicked(True, base_parameter, self._grouped_columns.get(base_parameter, []))
                return
