"""Synchronized camera selection and LaserScan XY display."""
import math
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox, QGridLayout, QToolButton, QMenu, QScrollArea


class VideoLabel(QLabel):
    def __init__(self):
        super().__init__("Open a ROS2 MCAP bag directory")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 120)
        self.setStyleSheet("background: #e9edf2; color: #344256;")
        self.original = None

    def show_rgb(self, rgb):
        if rgb is None:
            self.original = None
            self.clear()
            self.setText("No camera frame at this time")
            return
        h, w, _ = rgb.shape
        image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
        self.original = QPixmap.fromImage(image)
        self._rescale()

    def _rescale(self):
        if self.original is not None:
            self.setPixmap(self.original.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


class SpatialPanel(QWidget):
    """Camera and lidar tiles share one selection menu, layout and clock."""
    selection_changed = Signal(str)
    view_changed = Signal()

    def __init__(self):
        super().__init__()
        self.sources = {}
        self.cells = []
        self.cards = {}
        self.actions = {}
        self.last_indices = {}
        self.video = VideoLabel()
        self.scan_view = ScanView()
        self.scan_key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("2D views"))
        self.view_selector = QToolButton()
        self.view_selector.setText("Visible views ▾")
        self.view_selector.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu = QMenu(self)
        self.view_selector.setMenu(self.menu)
        controls.addWidget(self.view_selector)
        self.columns = QComboBox()
        self.columns.addItems(["1 column", "2 columns", "3 columns"])
        self.columns.setCurrentIndex(1)
        controls.addWidget(self.columns)
        controls.addStretch()
        controls.addWidget(QLabel("Frame-step camera"))
        self.selector = QComboBox()
        controls.addWidget(self.selector, 1)
        layout.addLayout(controls)
        self.tiles = QWidget()
        self.grid = QGridLayout(self.tiles)
        self.grid.addWidget(self.video, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(180)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.tiles)
        layout.addWidget(scroll, 1)
        self.empty = QLabel("Select camera or lidar views from Visible views.")
        self.empty.hide()
        layout.addWidget(self.empty)
        self.selector.currentTextChanged.connect(self.selection_changed.emit)
        self.columns.currentIndexChanged.connect(self._layout_cells)

    @property
    def selected_topic(self):
        return self.selector.currentText()

    def set_sources(self, sources, primary, scan=None, scan_topic="/scan"):
        self.sources = sources
        self.video.setParent(self)
        self.scan_view.setParent(self)
        while self.grid.count():
            self.grid.takeAt(0)
        for card in self.cards.values():
            if card is not self.scan_view:
                card.deleteLater()
        self.cards = {}
        self.cells = []
        self.actions = {}
        self.last_indices = {}
        self.menu.clear()
        self.menu.addAction("Show all", lambda: self._select_all(True))
        self.menu.addAction("Hide all", lambda: self._select_all(False))
        self.menu.addSeparator()
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItems(list(sources))
        primary_topic = next((t for t, source in sources.items() if source is primary), "")
        self.selector.setCurrentText(primary_topic)
        self.selector.blockSignals(False)
        for topic in sources:
            card = QWidget()
            card.setMinimumHeight(230)
            column = QVBoxLayout(card)
            column.setContentsMargins(0, 0, 0, 0)
            caption = QLabel(topic)
            caption.setTextFormat(Qt.TextFormat.PlainText)
            caption.setWordWrap(True)
            video = self.video if topic == primary_topic else VideoLabel()
            video.show_rgb(None)
            column.addWidget(caption)
            column.addWidget(video, 1)
            self.cards[topic] = card
            self.cells.append((topic, caption, video))
            self._add_action(topic, f"Camera · {topic}", topic == primary_topic)
        self.scan_view.set_source(scan, scan_topic)
        self.scan_key = scan_topic if scan is not None else None
        if scan is not None:
            self.cards[scan_topic] = self.scan_view
            self._add_action(scan_topic, f"Lidar · {scan_topic}", True)
        else:
            self.scan_view.hide()
        self._layout_cells()

    def _add_action(self, key, label, checked):
        action = self.menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(checked)
        action.toggled.connect(self._layout_cells)
        self.actions[key] = action

    def _select_all(self, checked):
        for action in self.actions.values():
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)
        self._layout_cells()

    def _layout_cells(self, *_):
        while self.grid.count():
            self.grid.takeAt(0)
        for row in range(self.grid.rowCount()):
            self.grid.setRowStretch(row, 0)
        for col in range(self.grid.columnCount()):
            self.grid.setColumnStretch(col, 0)
        visible = [key for key, action in self.actions.items() if action.isChecked()]
        columns = min(self.columns.currentIndex() + 1, max(1, len(visible)))
        for key, card in self.cards.items():
            card.setVisible(key in visible)
        for index, key in enumerate(visible):
            row, col = divmod(index, columns)
            self.grid.addWidget(self.cards[key], row, col)
            self.grid.setRowStretch(row, 1)
            self.grid.setColumnStretch(col, 1)
        self.empty.setVisible(not visible)
        self.view_changed.emit()

    def update_time(self, time_s):
        for topic, caption, video in self.cells:
            if not self.actions[topic].isChecked():
                continue
            source = self.sources[topic]
            index = source.index_at(time_s)
            if self.last_indices.get(topic) != index:
                try:
                    video.show_rgb(source.frame(index))
                except Exception:
                    video.show_rgb(None)
                    video.setText(f"Cannot decode {topic}")
                    raise
                self.last_indices[topic] = index
            if index >= 0:
                stamp = source.timestamps[index]
                caption.setText(f"{topic}\nFrame {stamp:.3f}s · age {time_s - stamp:.3f}s")
            else:
                caption.setText(f"{topic}\nNo frame at this time")
        if self.scan_key is not None and self.actions[self.scan_key].isChecked():
            self.scan_view.update_time(time_s)


class ScanView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(230)
        self.source = None
        self.last_index = None
        self.initial_range = False
        self.current_time = 0.0
        layout = QVBoxLayout(self)
        self.flip_y = QCheckBox("Flip scan orientation (Y → −Y)")
        self.flip_y.setToolTip("View from the opposite Z direction by mirroring Y. Raw scan data is unchanged.")
        self.flip_y.toggled.connect(self._flip_changed)
        layout.addWidget(self.flip_y)
        self.info = QLabel("No LaserScan topic in this bag")
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.plot = pg.PlotWidget(background="white")
        self.plot.setAspectLocked(True)
        self.plot.setLabel("bottom", "Y / left [m]")
        self.plot.invertX(True)
        self.plot.setLabel("left", "X / forward ↑ [m]")
        for name in ("bottom", "left"):
            self.plot.getAxis(name).setPen(pg.mkPen("#9aa7b5"))
            self.plot.getAxis(name).setTextPen(pg.mkPen("#344256"))
            self.plot.getAxis(name).enableAutoSIPrefix(False)
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.points = self.plot.plot(pen=None, symbol="o", symbolSize=3,
                                     symbolPen=None, symbolBrush="#2067b2")
        self.plot.plot([0], [0], pen=None, symbol="+", symbolSize=12, symbolPen="#c03639")
        self.plot.setXRange(-12, 12, padding=0)
        self.plot.setYRange(-12, 12, padding=0)
        layout.addWidget(self.plot, 1, Qt.AlignmentFlag.AlignHCenter)
        self.flip_y.setChecked(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep the spatial view roughly square rather than stretching its X
        # range across the full widescreen window when aspect locking is on.
        self.plot.setFixedWidth(max(200, min(self.width() - 20, self.height() - 85)))

    def set_source(self, source, topic):
        self.source = source
        self.topic = topic
        self.last_index = None
        self.initial_range = False
        self.points.setData([], [])
        self.info.setText("No scan at this time" if source else "No LaserScan topic in this bag")

    def _flip_changed(self, flipped):
        self.plot.setLabel("bottom", "−Y / mirrored [m]" if flipped else "Y / left [m]")
        self.last_index = None
        self.update_time(self.current_time)

    def update_time(self, time_s):
        self.current_time = time_s
        if self.source is None:
            return
        index = self.source.index_at(time_s)
        if index != self.last_index:
            frame = self.source.frame(index)
            self.points.setData([] if frame is None else (-frame.y if self.flip_y.isChecked() else frame.y),
                                [] if frame is None else frame.x)
            self.last_index = index
            if frame is not None and not self.initial_range:
                extent = frame.range_max if math.isfinite(frame.range_max) and frame.range_max > 0 else 12
                self.plot.setXRange(-extent, extent, padding=0)
                self.plot.setYRange(-extent, extent, padding=0)
                self.initial_range = True
        if index < 0:
            self.info.setText(f"{self.topic} · No scan at this time")
        else:
            frame = self.source.frame(index)
            stamp = self.source.timestamps[index]
            self.info.setText(f"{self.topic} · {frame.frame_id} · {len(frame.x)}/{frame.total_rays} valid rays"
                              f" · Scan {stamp:.3f}s · age {time_s - stamp:.3f}s")
