"""Qt widgets and synchronization; loading runs outside the GUI thread."""
import math

from PySide6.QtCore import Qt, QThread, Signal, QSignalBlocker, QTimer
from PySide6.QtGui import QImage, QPixmap, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog, QMessageBox, QSplitter,
    QTabWidget, QScrollArea, QCheckBox, QToolButton, QMenu,
)

from .data import BagDataSource
from .playback import PlaybackController, format_time
from .theme import apply_light_theme
from .plots import SeriesPlot
from .comparison import CustomCompare


class LoadThread(QThread):
    loaded = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, config, path, parent=None):
        super().__init__(parent)
        self.config, self.path = config, path
        self.result = None

    def run(self):
        source = BagDataSource(self.config)
        try:
            source.load(self.path, self.progress.emit, self.isInterruptionRequested)
            self.result = source
            self.loaded.emit(source)
        except InterruptedError:
            source.close()
        except Exception as exc:
            source.close()
            self.failed.emit(f"{type(exc).__name__}: {exc}")


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


class MainWindow(QMainWindow):
    def __init__(self, config, bag_path=None):
        super().__init__()
        apply_light_theme()
        self.config = config
        self.source = None
        self.loader = None
        self.closing = False
        self.last_frame = None
        self.slider_scale = 1000.0
        self.setWindowTitle("ROS2 MCAP Viewer")
        self.resize(1200, 950)
        self.controller = PlaybackController(self)
        body = QWidget()
        layout = QVBoxLayout(body)
        self.setCentralWidget(body)
        top = QHBoxLayout()
        self.open_button = QPushButton("Open bag…")
        self.open_button.clicked.connect(self.choose_bag)
        self.cancel_button = QPushButton("Cancel loading")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_loading)
        self.path_label = QLabel("No bag loaded")
        self.path_label.setTextFormat(Qt.TextFormat.PlainText)
        top.addWidget(self.open_button)
        top.addWidget(self.cancel_button)
        top.addWidget(self.path_label, 1)
        layout.addLayout(top)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.video = VideoLabel()
        splitter.addWidget(self.video)
        graph_area = QWidget()
        graph_layout = QVBoxLayout(graph_area)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_toolbar = QHBoxLayout()
        graph_toolbar.addWidget(QLabel("Graphs · shared time axis"))
        graph_toolbar.addStretch()
        self.video_toggle = QCheckBox("Show camera")
        self.video_toggle.setChecked(True)
        self.video_toggle.toggled.connect(self.video.setVisible)
        graph_toolbar.addWidget(self.video_toggle)
        self.graph_selector = QToolButton()
        self.graph_selector.setText("Visible graphs ▾")
        self.graph_selector.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.graph_menu = QMenu(self)
        self.graph_selector.setMenu(self.graph_menu)
        graph_toolbar.addWidget(self.graph_selector)
        graph_layout.addLayout(graph_toolbar)
        self.graph_tabs = QTabWidget()
        graph_layout.addWidget(self.graph_tabs)
        splitter.addWidget(graph_area)
        self._syncing_ranges = False
        self._build_graphs(config.series)
        self.graph_tabs.currentChanged.connect(self._arrange_graphs)
        splitter.setSizes([280, 580])
        layout.addWidget(splitter, 1)
        self.controls = QWidget()
        controls = QHBoxLayout(self.controls)
        self.previous_button = QPushButton("⏮ Previous")
        self.play_button = QPushButton("▶ Play")
        self.next_button = QPushButton("Next ⏭")
        self.previous_button.clicked.connect(lambda: self.controller.step_frame(-1))
        self.next_button.clicked.connect(lambda: self.controller.step_frame(1))
        self.play_button.clicked.connect(self.controller.toggle)
        self.speed = QComboBox()
        for rate in (0.25, 0.5, 1.0, 2.0):
            self.speed.addItem(f"{rate:g}x", rate)
        self.speed.setCurrentIndex(2)
        self.speed.currentIndexChanged.connect(lambda _: self.controller.set_rate(self.speed.currentData()))
        self.time_label = QLabel("00:00.000 / 00:00.000")
        for widget in (self.previous_button, self.play_button, self.next_button, self.speed):
            controls.addWidget(widget)
        controls.addStretch()
        controls.addWidget(self.time_label)
        layout.addWidget(self.controls)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(lambda value: self.seek(value / self.slider_scale))
        layout.addWidget(self.slider)
        self._enable_transport(False)
        self.controller.position_changed.connect(self.update_position)
        self.controller.playing_changed.connect(
            lambda playing: self.play_button.setText("⏸ Pause" if playing else "▶ Play"))
        self.shortcuts = []
        for key, callback in (
            ("Space", self.controller.toggle),
            ("Left", lambda: self.controller.step_frame(-1)),
            ("Right", lambda: self.controller.step_frame(1)),
            ("Shift+Left", lambda: self.seek(self.controller.current_time - 1)),
            ("Shift+Right", lambda: self.seek(self.controller.current_time + 1)),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        self._enable_transport(False)
        if bag_path:
            QTimer.singleShot(0, lambda: self.open_bag(bag_path))

    def _build_graphs(self, specs):
        # Rebuild from loaded series so optional motor topics need no manual setup.
        self._building_graphs = True
        self.custom_compare = None
        while self.graph_tabs.count():
            page = self.graph_tabs.widget(0)
            self.graph_tabs.removeTab(0)
            page.deleteLater()
        self.graph_menu.clear()
        self.plots = []
        self.graph_cards = []
        self.legend_checks = []
        self.graph_actions = []
        self.card_columns = []
        groups = {}
        for spec in specs:
            if spec.group not in groups:
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QScrollArea.Shape.NoFrame)
                page = QWidget()
                column = QVBoxLayout(page)
                column.setAlignment(Qt.AlignmentFlag.AlignTop)
                scroll.setWidget(page)
                self.graph_tabs.addTab(scroll, spec.group)
                groups[spec.group] = column
            plot = SeriesPlot(spec)
            plot.seek_requested.connect(self.seek)
            plot.getViewBox().sigXRangeChanged.connect(self._sync_plot_ranges)
            card = QWidget()
            card.setMinimumHeight(235)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(4, 4, 4, 4)
            title = QLabel(spec.name)
            title.setTextFormat(Qt.TextFormat.PlainText)
            title.setStyleSheet("font-weight: 600; color: #202b38;")
            card_layout.addWidget(title)
            legend = QHBoxLayout()
            checks = []
            for i, (label, curve) in enumerate(zip(spec.labels, plot.curves)):
                check = QCheckBox(label)
                check.setChecked(True)
                color = plot.colors[i % len(plot.colors)]
                check.setStyleSheet(f"QCheckBox {{ color: {color}; font-size: 11px; }}")
                check.toggled.connect(curve.setVisible)
                legend.addWidget(check)
                checks.append(check)
            legend.addStretch()
            card_layout.addLayout(legend)
            card_layout.addWidget(plot, 1)
            groups[spec.group].addWidget(card)
            action = self.graph_menu.addAction(f"{spec.group} / {spec.name}")
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(card.setVisible)
            self.graph_actions.append(action)
            self.legend_checks.append(checks)
            self.graph_cards.append(card)
            self.card_columns.append(groups[spec.group])
            self.plots.append(plot)
        compare = QScrollArea()
        compare.setWidgetResizable(True)
        compare.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget()
        self.compare_column = QVBoxLayout(page)
        self.compare_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        compare.setWidget(page)
        self.compare_index = self.graph_tabs.addTab(compare, "All / Compare")
        self.custom_compare = CustomCompare()
        self.custom_index = self.graph_tabs.addTab(self.custom_compare, "Custom Compare")
        for plot in self.custom_compare.plots:
            plot.seek_requested.connect(self.seek)
            plot.getViewBox().sigXRangeChanged.connect(self._sync_plot_ranges)
        self._building_graphs = False

    def _time_plots(self):
        extra = self.custom_compare.plots if self.custom_compare is not None else []
        return self.plots + extra

    def _arrange_graphs(self, index):
        if self._building_graphs:
            return
        for card, column, action in zip(self.graph_cards, self.card_columns, self.graph_actions):
            target = self.compare_column if index == self.compare_index else column
            target.addWidget(card)
            card.setVisible(action.isChecked())

    def _sync_plot_ranges(self, source_view, time_range):
        # Explicit linking also works when the source/target tab is hidden.
        if self._syncing_ranges:
            return
        self._syncing_ranges = True
        try:
            for plot in self._time_plots():
                if plot.getViewBox() is not source_view:
                    plot.setXRange(*time_range, padding=0)
        finally:
            self._syncing_ranges = False

    def _enable_transport(self, enabled):
        self.controls.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.custom_compare.setEnabled(enabled)
        for plot in self._time_plots():
            plot.setEnabled(enabled)
        for shortcut in getattr(self, "shortcuts", []):
            shortcut.setEnabled(enabled)

    def choose_bag(self):
        path = QFileDialog.getExistingDirectory(self, "Open ROS2 MCAP bag")
        if path:
            self.open_bag(path)

    def open_bag(self, path):
        if self.loader is not None:
            return
        self.controller.pause()
        self._enable_transport(False)
        self.open_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.statusBar().showMessage("Scanning bag…")
        self.loader = LoadThread(self.config, path, self)
        self.loader.progress.connect(self.statusBar().showMessage)
        self.loader.loaded.connect(self._loaded)
        self.loader.failed.connect(self._failed)
        self.loader.finished.connect(self._load_finished)
        self.loader.start()

    def cancel_loading(self):
        if self.loader:
            self.loader.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.statusBar().showMessage("Cancelling…")

    def _loaded(self, source):
        if self.closing or self.loader.isInterruptionRequested():
            source.close()
            return
        if self.source:
            self.source.close()
        self.source = source
        self._build_graphs([s.spec for s in source.series])
        self.path_label.setText(self.loader.path)
        self.path_label.setToolTip("\n".join(f"{k}: {v}" for k, v in source.topics.items()))
        self.last_frame = None
        # QSlider uses signed 32-bit integers. Retain milliseconds for normal bags.
        self.slider_scale = min(1000.0, (2**31 - 2) / max(source.duration, 0.001))
        with QSignalBlocker(self.slider):
            self.slider.setRange(0, math.ceil(source.duration * self.slider_scale))
        for plot, series in zip(self.plots, source.series):
            plot.set_series(series, source.duration)
        self.custom_compare.set_data(source.series, source.duration)
        text = f"{len(source.images.timestamps):,} frames · {format_time(source.duration)}"
        if source.warnings:
            text += " · " + "; ".join(source.warnings)
        self.statusBar().showMessage(text)
        self.controller.set_data(source.duration, source.images.timestamps)

    def _failed(self, message):
        if not self.closing:
            self.statusBar().showMessage("Loading failed")
            QMessageBox.critical(self, "Cannot open bag", message)

    def _load_finished(self):
        loader = self.loader
        self.loader = None
        loader.deleteLater()
        if self.closing:
            self.close()
            return
        self.open_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._enable_transport(self.source is not None)
        if loader.isInterruptionRequested():
            self.statusBar().showMessage("Loading cancelled")

    def seek(self, time_s):
        if self.source is not None:
            self.controller.seek(time_s)

    def update_position(self, time_s):
        for plot in self._time_plots():
            with QSignalBlocker(plot.cursor):
                plot.cursor.setValue(time_s)
        with QSignalBlocker(self.slider):
            self.slider.setValue(round(time_s * self.slider_scale))
        self.time_label.setText(f"{format_time(time_s)} / {format_time(self.controller.duration)}")
        if self.source is None:
            return
        index = self.source.images.index_at(time_s)
        if index == self.last_frame:
            return
        self.last_frame = index
        try:
            self.video.show_rgb(self.source.images.frame(index))
        except Exception as exc:
            self.controller.pause()
            self.video.show_rgb(None)
            self.video.setText("Image decoding failed")
            self.statusBar().showMessage(f"Frame {index}: {exc}")

    def closeEvent(self, event):
        self.controller.pause()
        if self.loader is not None:
            self.closing = True
            self.loader.requestInterruption()
            self.statusBar().showMessage("Closing after loader stops…")
            event.ignore()
            return
        if self.source:
            self.source.close()
        event.accept()
