"""User-selected channel overlays on one or two synchronized time planes."""
from html import escape

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QPushButton, QScrollArea,
    QHeaderView,
)

from .config import SeriesSpec
from .plots import SeriesPlot


def normalize_values(values):
    """Full-log min/max normalization; invalid samples remain gaps."""
    result = np.full(values.shape, np.nan, dtype=float)
    finite = np.isfinite(values)
    if finite.any():
        lo, hi = np.min(values[finite]), np.max(values[finite])
        result[finite] = (values[finite] - lo) / (hi - lo) if hi > lo else 0.0
    return result


class OverlayPane(QWidget):
    def __init__(self, number):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.title = QLabel(f"Plot {number}")
        header.addWidget(self.title)
        header.addStretch()
        self.scale = QComboBox()
        self.scale.addItems(["Original values", "Normalize each series 0–1"])
        self.scale.setToolTip("Normalize using each channel's min/max across the full log; constant values become 0.")
        header.addWidget(self.scale)
        layout.addLayout(header)
        legend_area = QScrollArea()
        legend_area.setWidgetResizable(True)
        legend_area.setFrameShape(QScrollArea.Shape.NoFrame)
        legend_area.setMinimumHeight(38)
        legend_area.setMaximumHeight(64)
        self.legend = QLabel("Select channels in the left list.")
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        self.legend.setWordWrap(True)
        self.legend.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        legend_area.setWidget(self.legend)
        layout.addWidget(legend_area)
        self.plot = SeriesPlot(SeriesSpec("Values", "", "", (), (), ""))
        self.plot.setLabel("left", "Value")
        layout.addWidget(self.plot, 1)
        self.curves = {}


class CustomCompare(QWidget):
    """Check columns 1/2 independently; samples retain their own timestamps."""
    def __init__(self):
        super().__init__()
        self.series = []
        self.items = {}
        self.channel_styles = {}
        self.duration = 0.0
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Time-series overlay"))
        self.plane_count = QComboBox()
        self.plane_count.addItems(["1 plot", "2 plots"])
        toolbar.addWidget(self.plane_count)
        clear = QPushButton("Clear selections")
        clear.clicked.connect(self.clear_selection)
        toolbar.addWidget(clear)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        split = QSplitter(Qt.Orientation.Horizontal)
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter channels…")
        side.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Channel / unit", "1", "2"])
        self.tree.setRootIsDecorated(True)
        self.tree.setMinimumWidth(220)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            self.tree.header().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.tree.setColumnWidth(column, 36)
        side.addWidget(self.tree)
        split.addWidget(sidebar)
        self.plot_splitter = QSplitter(Qt.Orientation.Vertical)
        self.panes = [OverlayPane(1), OverlayPane(2)]
        self.plots = [pane.plot for pane in self.panes]
        for pane in self.panes:
            self.plot_splitter.addWidget(pane)
            pane.scale.currentIndexChanged.connect(self.refresh)
        split.addWidget(self.plot_splitter)
        split.setStretchFactor(1, 1)
        split.setSizes([310, 800])
        layout.addWidget(split, 1)
        self.tree.itemChanged.connect(self._item_changed)
        self.search.textChanged.connect(self._filter)
        self.plane_count.currentIndexChanged.connect(self._set_plane_count)
        self._set_plane_count(0)

    def set_data(self, series, duration):
        self.series = series
        self.duration = duration
        self.items = {}
        self.channel_styles = {}
        with QSignalBlocker(self.tree):
            self.tree.clear()
            index = 0
            for si, data in enumerate(series):
                group = QTreeWidgetItem(self.tree, [f"{data.spec.group} / {data.spec.name}"])
                group.setToolTip(0, data.spec.topic)
                for ci, label in enumerate(data.spec.labels):
                    key = (si, ci)
                    item = QTreeWidgetItem(group, [f"{label} [{data.spec.units}]"])
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(1, Qt.CheckState.Unchecked)
                    item.setCheckState(2, Qt.CheckState.Unchecked)
                    item.setToolTip(0, f"{data.spec.name} / {label} [{data.spec.units}]\n{data.spec.topic}")
                    color = QColor.fromHsv((index * 137) % 360, 185, 155)
                    style = (Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine,
                             Qt.PenStyle.DotLine)[(index // 8) % 3]
                    self.channel_styles[key] = (color, style)
                    item.setForeground(0, QBrush(color))
                    self.items[key] = item
                    index += 1
                group.setExpanded(True)
        for plot in self.plots:
            plot.cursor.setBounds((0, duration))
            plot.setXRange(0, max(duration, 0.001), padding=0.01)
        self._filter(self.search.text())
        self.refresh()

    def _set_plane_count(self, index):
        self.panes[1].setVisible(index == 1)
        self.tree.setColumnHidden(2, index == 0)
        if index == 1:
            self.plot_splitter.setSizes([300, 300])

    def clear_selection(self):
        with QSignalBlocker(self.tree):
            for item in self.items.values():
                item.setCheckState(1, Qt.CheckState.Unchecked)
                item.setCheckState(2, Qt.CheckState.Unchecked)
        self.refresh()

    def _item_changed(self, item, column):
        if column in (1, 2):
            self.refresh()

    def _filter(self, text):
        text = text.casefold().strip()
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            visible = False
            for ci in range(group.childCount()):
                child = group.child(ci)
                match = text in f"{group.text(0)} {child.text(0)}".casefold()
                child.setHidden(not match)
                visible |= match
            group.setHidden(not visible)

    def refresh(self, *_):
        for plane_index, pane in enumerate(self.panes):
            for curve in pane.curves.values():
                pane.plot.removeItem(curve)
            pane.curves.clear()
            legend = []
            units = set()
            normalized = pane.scale.currentIndex() == 1
            for key, item in self.items.items():
                if item.checkState(plane_index + 1) != Qt.CheckState.Checked:
                    continue
                si, ci = key
                data = self.series[si]
                color, style = self.channel_styles[key]
                values = data.values[:, ci]
                if normalized:
                    values = normalize_values(values)
                label = f"{data.spec.name} · {data.spec.labels[ci]} [{data.spec.units}]"
                curve = pane.plot.plot(data.time, values, name=label, connect="finite",
                                       pen=pg.mkPen(color, width=1.4, style=style))
                curve.setClipToView(True)
                curve.setDownsampling(auto=True, method="peak")
                pane.curves[key] = curve
                units.add(data.spec.units)
                legend.append(f'<span style="color:{color.name()}">━ {escape(label)}</span>')
            if normalized:
                axis = "Normalized [0–1]"
            elif len(units) == 1:
                axis = f"Value [{next(iter(units))}]"
            elif units:
                axis = "Mixed units · see legend"
            else:
                axis = "Value"
            pane.plot.setLabel("left", axis)
            pane.plot.enableAutoRange(axis="y")
            pane.title.setText(f"Plot {plane_index + 1} · {len(pane.curves)} channels")
            pane.legend.setText(" &nbsp; · &nbsp; ".join(legend) or "Select channels in the left list.")
