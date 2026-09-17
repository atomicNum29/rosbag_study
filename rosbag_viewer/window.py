"""Qt widgets and synchronization; loading runs outside the GUI thread."""
import math

import pyqtgraph as pg
from PySide6.QtCore import Qt, QThread, Signal, QSignalBlocker, QTimer
from PySide6.QtGui import QImage, QPixmap, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog, QMessageBox, QSplitter,
)

from .data import BagDataSource
from .playback import PlaybackController, format_time


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
        self.setStyleSheet("background: #15191f; color: #d5dbe5;")
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


class SeriesPlot(pg.PlotWidget):
    seek_requested = Signal(float)

    def __init__(self, spec):
        super().__init__()
        self.setMinimumHeight(130)
        self.setTitle(spec.name)
        self.setLabel("bottom", "Time [s]")
        ylabel = {"Gyroscope": "Angular velocity", "Accelerometer": "Acceleration"}.get(spec.name, spec.name)
        self.setLabel("left", f"{ylabel} [{spec.units}]")
        self.showGrid(x=True, y=True, alpha=0.2)
        self.addLegend()
        colors = ("#ef6b73", "#70d89d", "#6cb8ff", "#e8c46b")
        self.curves = []
        for i, label in enumerate(spec.labels):
            curve = self.plot(pen=pg.mkPen(colors[i % len(colors)], width=1), name=label)
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")
            self.curves.append(curve)
        self.cursor = pg.InfiniteLine(pos=0, angle=90, movable=True,
                                      pen=pg.mkPen("#f5e378", width=2))
        self.addItem(self.cursor)
        self.cursor.sigDragged.connect(lambda _: self.seek_requested.emit(float(self.cursor.value())))
        self.scene().sigMouseClicked.connect(self._clicked)

    def _clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not event.isAccepted():
            view = self.getViewBox()
            if view.sceneBoundingRect().contains(event.scenePos()):
                self.seek_requested.emit(float(view.mapSceneToView(event.scenePos()).x()))

    def set_series(self, series, duration):
        for i, curve in enumerate(self.curves):
            curve.setData(series.time, series.values[:, i])
        self.cursor.setBounds((0, duration))
        self.setXRange(0, max(duration, 0.001), padding=0.01)


class MainWindow(QMainWindow):
    def __init__(self, config, bag_path=None):
        super().__init__()
        self.config = config
        self.source = None
        self.loader = None
        self.closing = False
        self.last_frame = None
        self.slider_scale = 1000.0
        self.setWindowTitle("ROS2 MCAP Viewer")
        self.resize(1100, 900)
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
        self.plots = [SeriesPlot(spec) for spec in config.series]
        for plot in self.plots:
            splitter.addWidget(plot)
            plot.seek_requested.connect(self.seek)
            if plot is not self.plots[0]:
                plot.setXLink(self.plots[0])
        splitter.setSizes([420] + [200] * len(self.plots))
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

    def _enable_transport(self, enabled):
        self.controls.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        for plot in self.plots:
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
        self.path_label.setText(self.loader.path)
        self.path_label.setToolTip("\n".join(f"{k}: {v}" for k, v in source.topics.items()))
        self.last_frame = None
        # QSlider uses signed 32-bit integers. Retain milliseconds for normal bags.
        self.slider_scale = min(1000.0, (2**31 - 2) / max(source.duration, 0.001))
        with QSignalBlocker(self.slider):
            self.slider.setRange(0, math.ceil(source.duration * self.slider_scale))
        for plot, series in zip(self.plots, source.series):
            plot.set_series(series, source.duration)
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
        for plot in self.plots:
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
