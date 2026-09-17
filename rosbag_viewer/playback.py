"""Timestamp-based playback independent of camera FPS and GUI refresh rate."""
import math
import time

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal


def format_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    minutes, ms = divmod(ms, 60_000)
    seconds, ms = divmod(ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{ms:03d}"


class PlaybackController(QObject):
    position_changed = Signal(float)
    playing_changed = Signal(bool)

    def __init__(self, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.clock = clock
        self.current_time = self.duration = 0.0
        self.playing = False
        self.playback_rate = 1.0
        self.timestamps = np.empty(0)
        self.anchor_time = 0.0
        self.anchor_clock = clock()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    def set_data(self, duration, timestamps):
        self.pause()
        self.duration = duration
        self.timestamps = timestamps
        self.seek(0)

    def seek(self, time_s):
        if not math.isfinite(time_s):
            return
        self.current_time = min(self.duration, max(0.0, float(time_s)))
        self.anchor_time = self.current_time
        self.anchor_clock = self.clock()
        self.position_changed.emit(self.current_time)
        if self.current_time >= self.duration:
            self.pause()

    def play(self):
        if self.duration <= 0 or self.playing:
            return
        if self.current_time >= self.duration:
            self.seek(0)
        self.anchor_time = self.current_time
        self.anchor_clock = self.clock()
        self.playing = True
        self.timer.start()
        self.playing_changed.emit(True)

    def pause(self):
        if self.playing:
            self.playing = False
            self.timer.stop()
            self.playing_changed.emit(False)

    def toggle(self):
        self.pause() if self.playing else self.play()

    def tick(self):
        if self.playing:
            target = self.anchor_time + (self.clock() - self.anchor_clock) * self.playback_rate
            self.current_time = min(self.duration, target)
            self.position_changed.emit(self.current_time)
            if self.current_time >= self.duration:
                self.pause()

    def set_rate(self, rate):
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Playback rate must be positive")
        self.tick()
        self.playback_rate = rate
        self.anchor_time = self.current_time
        self.anchor_clock = self.clock()

    def step_frame(self, direction):
        self.pause()
        if not len(self.timestamps):
            return
        if direction > 0:
            index = np.searchsorted(self.timestamps, self.current_time, side="right")
        else:
            index = np.searchsorted(self.timestamps, self.current_time, side="left") - 1
        index = int(np.clip(index, 0, len(self.timestamps) - 1))
        self.seek(float(self.timestamps[index]))
