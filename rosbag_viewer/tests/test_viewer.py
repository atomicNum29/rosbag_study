"""Core and offscreen Qt regression tests; no ROS installation required."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
from PySide6.QtWidgets import QApplication

from rosbag_viewer.config import ViewerConfig, motor_series
from rosbag_viewer.data import ImageSource, sensor_timestamp, TimeSeriesData, series_values, field_value
from rosbag_viewer.playback import PlaybackController, format_time
from rosbag_viewer.window import MainWindow

APP = QApplication.instance() or QApplication([])


class ImageTests(unittest.TestCase):
    def test_random_reads_and_cache_budget(self):
        spool = tempfile.TemporaryFile()
        spool.write(b"\x01\x02\x03")
        calls = []
        def decode(raw):
            calls.append(raw)
            return np.full((2, 2, 3), raw[0], dtype=np.uint8)
        source = ImageSource(spool, np.array([0.1, 0.2, 0.2]), np.zeros(3),
                             np.arange(3), np.ones(3), decode, cache_bytes=12)
        try:
            self.assertEqual(source.index_at(0), -1)
            self.assertEqual(source.index_at(0.2), 2)
            self.assertIsNone(source.frame(-1))
            self.assertEqual(source.frame(2)[0, 0, 0], 3)
            source.frame(2)
            self.assertEqual(len(calls), 1)
            self.assertEqual(source.frame(0)[0, 0, 0], 1)
            self.assertEqual(source.cached_bytes, 12)
            self.assertEqual(list(source.cache), [0])
        finally:
            source.close()
        self.assertTrue(spool.closed)

    def test_timestamps_and_format(self):
        msg = SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=12, nanosec=345)))
        self.assertEqual(sensor_timestamp(msg, 99, "header"), (12_000_000_345, False))
        self.assertEqual(sensor_timestamp(msg, 99, "record"), (99, False))
        msg.header.stamp.sec = msg.header.stamp.nanosec = 0
        self.assertEqual(sensor_timestamp(msg, 99, "header"), (99, True))
        self.assertEqual(format_time(59.9996), "01:00.000")
        self.assertEqual(format_time(95.824), "01:35.824")


class MotorTests(unittest.TestCase):
    def test_units_validity_and_missing_values(self):
        rpm, current, output, voltage = motor_series("/motor_bridge_node/status")
        payload = {
            "wheels": {
                "lf": {"valid": True, "rpm": -120, "current_deci_amp": 23, "controller_output": 50},
                "rf": {"valid": False, "rpm": 200, "current_deci_amp": 99},
                "lr": {"valid": True, "rpm": 80, "current_deci_amp": -5},
            },
            "drivers": {"a": {"valid": True, "voltage_mv": 26500},
                        "b": {"valid": False, "voltage_mv": 27000}},
        }
        np.testing.assert_allclose(series_values(payload, rpm), [-120, np.nan, 80, np.nan])
        np.testing.assert_allclose(series_values(payload, current), [2.3, np.nan, -0.5, np.nan])
        np.testing.assert_allclose(series_values(payload, voltage), [26.5, np.nan])
        self.assertTrue(np.isnan(series_values({}, output)).all())
        self.assertTrue(np.isnan(series_values({"wheels": None}, rpm)).all())
        self.assertEqual(field_value(SimpleNamespace(data=[3, 4]), "data[1]"), 4)
        self.assertTrue(np.isnan(field_value(SimpleNamespace(data=[]), "data[0]")))


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.player = PlaybackController(clock=lambda: self.now)
        self.player.set_data(10, np.array([0.1, 0.2, 0.5, 9.9]))

    def tearDown(self):
        self.player.pause()

    def test_wall_time_seek_rate_and_end(self):
        p = self.player
        p.play()
        self.now += 1.25
        p.tick()
        self.assertEqual(p.current_time, 1.25)
        p.set_rate(2)
        self.now += 0.5
        p.tick()
        self.assertEqual(p.current_time, 2.25)
        p.seek(7)
        self.now += 1
        p.tick()
        self.assertEqual(p.current_time, 9)
        self.now += 1
        p.tick()
        self.assertEqual(p.current_time, 10)
        self.assertFalse(p.playing)
        p.seek(-3)
        self.assertEqual(p.current_time, 0)

    def test_frame_steps_between_frames(self):
        p = self.player
        p.seek(0.3)
        p.step_frame(-1)
        self.assertEqual(p.current_time, 0.2)
        p.step_frame(1)
        self.assertEqual(p.current_time, 0.5)
        p.seek(0)
        p.step_frame(-1)
        self.assertEqual(p.current_time, 0.1)


class WindowTests(unittest.TestCase):
    def test_tabs_comparison_visibility_and_linked_ranges(self):
        config = ViewerConfig(series=ViewerConfig().series + motor_series("/motor_bridge_node/status"))
        window = MainWindow(config)
        window.show()
        APP.processEvents()
        self.assertEqual([window.graph_tabs.tabText(i) for i in range(4)],
                         ["IMU", "Wheels", "Motor", "All / Compare"])
        window.graph_tabs.setCurrentIndex(1)
        APP.processEvents()
        window.plots[2].setXRange(10, 20, padding=0)
        for plot in window.plots:
            np.testing.assert_allclose(plot.viewRange()[0], [10, 20])
        window.legend_checks[2][0].setChecked(False)
        self.assertFalse(window.plots[2].curves[0].isVisible())
        window.graph_actions[1].setChecked(False)
        window.graph_tabs.setCurrentIndex(3)
        APP.processEvents()
        self.assertIs(window.graph_cards[2].parentWidget(), window.compare_column.parentWidget())
        self.assertTrue(window.graph_cards[1].isHidden())
        window.graph_tabs.setCurrentIndex(0)
        APP.processEvents()
        self.assertIs(window.graph_cards[2].parentWidget(), window.card_columns[2].parentWidget())
        self.assertTrue(window.graph_cards[1].isHidden())
        window.video_toggle.setChecked(False)
        self.assertTrue(window.video.isHidden())
        window.close()

    def test_seek_synchronizes_without_recursive_signals(self):
        config = ViewerConfig()
        window = MainWindow(config)
        class Images:
            timestamps = np.array([0.1, 0.5, 1.0])
            def index_at(self, t):
                return int(np.searchsorted(self.timestamps, t, side="right")) - 1
            def frame(self, i):
                return None if i < 0 else np.full((10, 20, 3), i * 40, np.uint8)
        series = [TimeSeriesData(spec, np.array([0.0, 1.0]), np.zeros((2, 3)), np.array([0, 1]))
                  for spec in config.series]
        window.source = SimpleNamespace(images=Images(), close=lambda: None)
        for plot, data in zip(window.plots, series):
            plot.set_series(data, 1)
        window.slider.setRange(0, 1000)
        window.controller.set_data(1, Images.timestamps)
        emissions = []
        window.controller.position_changed.connect(emissions.append)
        window.seek(0.6)
        self.assertEqual(emissions, [0.6])
        self.assertEqual(window.last_frame, 1)
        self.assertEqual(window.slider.value(), 600)
        self.assertEqual(window.plots[0].cursor.value(), 0.6)
        self.assertEqual(window.plots[1].cursor.value(), 0.6)
        window.slider.setValue(800)
        self.assertEqual(window.controller.current_time, 0.8)
        window.plots[0].cursor.setValue(0.2)
        window.plots[0].cursor.sigDragged.emit(window.plots[0].cursor)
        self.assertEqual(window.controller.current_time, 0.2)
        self.assertEqual(window.plots[1].cursor.value(), 0.2)
        window.seek(0)
        self.assertIsNone(window.video.original)
        window.close()


if __name__ == "__main__":
    unittest.main()
