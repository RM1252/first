"""Plot construction and downsampling utilities for USM analyzer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from matplotlib.figure import Figure


@dataclass(slots=True)
class PlotRequest:
    """Input payload required to generate a plot."""

    file_name: str
    dataframe: pd.DataFrame
    time_column: str | None
    selected_parameters: list[str]


@dataclass(slots=True)
class PlotOptions:
    """Plot rendering options."""

    max_points_per_series: int = 5000
    figure_size: tuple[float, float] = (12.0, 6.0)
    dpi: int = 100


class PlotEngine:
    """Engine for generating performant matplotlib figures."""

    def __init__(self, options: PlotOptions | None = None) -> None:
        self.options = options or PlotOptions()

    def create_figure(self, requests: list[PlotRequest]) -> Figure:
        """Create a single figure that can compare multiple files/parameters."""

        fig = Figure(figsize=self.options.figure_size, dpi=self.options.dpi, tight_layout=True)
        axis = fig.add_subplot(1, 1, 1)

        plotted_count = 0
        for request in requests:
            plot_cols = [c for c in request.selected_parameters if c in request.dataframe.columns]
            if not plot_cols:
                continue

            x_column = request.time_column if request.time_column and request.time_column in request.dataframe.columns else None
            plot_df = self._prepare_plot_frame(request.dataframe, x_column, plot_cols)

            if x_column:
                x_values = plot_df[x_column]
                for column in plot_cols:
                    y_values = plot_df[column]
                    label = f"{request.file_name} | {column}"
                    axis.plot(x_values, y_values, linewidth=1.0, label=label)
                    plotted_count += 1
            else:
                x_values = np.arange(len(plot_df))
                for column in plot_cols:
                    y_values = plot_df[column]
                    label = f"{request.file_name} | {column}"
                    axis.plot(x_values, y_values, linewidth=1.0, label=label)
                    plotted_count += 1

        axis.set_title("USM Parameter Comparison")
        axis.set_ylabel("Value")
        axis.set_xlabel("Time" if any(r.time_column for r in requests) else "Sample Index")
        axis.grid(True, linestyle="--", alpha=0.35)

        if plotted_count > 0:
            axis.legend(loc="upper right", fontsize=8)
        return fig

    def _prepare_plot_frame(self, df: pd.DataFrame, x_column: str | None, y_columns: list[str]) -> pd.DataFrame:
        required_columns = [x_column] + y_columns if x_column else y_columns
        frame = df[required_columns].copy()
        frame = frame.dropna(subset=y_columns, how="all")

        if x_column:
            frame = frame.dropna(subset=[x_column])
            frame = frame.sort_values(by=x_column)

        if len(frame) > self.options.max_points_per_series:
            sample_index = self._downsample_indices(len(frame), self.options.max_points_per_series)
            frame = frame.iloc[sample_index]

        return frame.reset_index(drop=True)

    @staticmethod
    def _downsample_indices(length: int, max_points: int) -> np.ndarray:
        """Return evenly-spaced row indices while preserving first and last points."""

        if length <= max_points:
            return np.arange(length)

        indices = np.linspace(0, length - 1, num=max_points, dtype=int)
        indices[0] = 0
        indices[-1] = length - 1
        return np.unique(indices)
