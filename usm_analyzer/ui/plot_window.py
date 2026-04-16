"""Standalone plot window with interactive matplotlib tools."""

from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QToolBar
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


class PlotWindow(QMainWindow):
    """Independent window hosting a matplotlib figure and controls."""

    def __init__(self, figure: Figure, title: str = "USM Plot") -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1100, 720)

        self.canvas = FigureCanvasQTAgg(figure)
        self.setCentralWidget(self.canvas)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        # Dedicated reset action in addition to toolbar Home button for UX clarity.
        reset_toolbar = QToolBar("Plot Actions", self)
        reset_toolbar.setMovable(False)
        reset_action = reset_toolbar.addAction("Reset")
        reset_action.triggered.connect(self.reset_view)
        self.addToolBar(reset_toolbar)

    def reset_view(self) -> None:
        """Reset current view limits to default extents."""

        self.toolbar.home()
        self.canvas.draw_idle()
