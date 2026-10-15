"""Shared white-background time-series plot and seek cursor."""
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal


class SeriesPlot(pg.PlotWidget):
    seek_requested = Signal(float)

    def __init__(self, spec):
        super().__init__()
        self.setBackground("#ffffff")
        self.setMinimumHeight(185)
        for name in ("left", "bottom"):
            self.getAxis(name).enableAutoSIPrefix(False)
            self.getAxis(name).setPen(pg.mkPen("#9aa7b5"))
            self.getAxis(name).setTextPen(pg.mkPen("#344256"))
        self.setLabel("bottom", "Time [s]")
        ylabel = {"Gyroscope": "Angular velocity", "Accelerometer": "Acceleration"}.get(spec.name, spec.name)
        self.setLabel("left", f"{ylabel} [{spec.units}]")
        self.showGrid(x=True, y=True, alpha=0.2)
        self.colors = ("#c03639", "#167344", "#2067b2", "#9550a2", "#a66300", "#007e87")
        self.curves = []
        for i, label in enumerate(spec.labels):
            curve = self.plot(pen=pg.mkPen(self.colors[i % len(self.colors)], width=1.3),
                              name=label, connect="finite")
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")
            self.curves.append(curve)
        self.cursor = pg.InfiniteLine(pos=0, angle=90, movable=True,
                                      pen=pg.mkPen("#596579", width=2),
                                      hoverPen=pg.mkPen("#d46a00", width=2))
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

