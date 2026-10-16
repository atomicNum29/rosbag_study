"""Multi-camera, LaserScan and command regression tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from types import SimpleNamespace
import numpy as np
from PySide6.QtWidgets import QApplication

from rosbag_viewer.config import command_series, ViewerConfig
from rosbag_viewer.data import scan_frame, series_values
from rosbag_viewer.window import MainWindow

APP = QApplication.instance() or QApplication([])


class MediaTests(unittest.TestCase):
    def test_scan_geometry_and_invalid_ranges(self):
        msg = SimpleNamespace(ranges=[1, 2, np.nan, np.inf, 0.05, 13],
                              angle_min=0, angle_increment=np.pi/2, range_min=0.1, range_max=12,
                              header=SimpleNamespace(frame_id="laser"))
        frame = scan_frame(msg)
        np.testing.assert_allclose(frame.x, [1, 0], atol=1e-12)
        np.testing.assert_allclose(frame.y, [0, 2], atol=1e-12)
        self.assertEqual(frame.total_rays, 6)
        msg.ranges = []
        self.assertEqual(len(scan_frame(msg).x), 0)

    def test_command_paths(self):
        twist = SimpleNamespace(linear=SimpleNamespace(x=1, y=2, z=3),
                                angular=SimpleNamespace(x=4, y=5, z=6))
        for kind, msg in (("geometry_msgs/msg/Twist", twist),
                          ("geometry_msgs/msg/TwistStamped", SimpleNamespace(twist=twist))):
            linear, angular = command_series("/cmd_vel", kind)
            self.assertEqual(series_values(msg, linear), (1, 2, 3))
            self.assertEqual(series_values(msg, angular), (4, 5, 6))

    def test_camera_switch_step_all_views_and_scan_seek(self):
        class Camera:
            def __init__(self, times):
                self.timestamps = np.asarray(times)
            def index_at(self, t):
                return int(np.searchsorted(self.timestamps, t, side="right")) - 1
            def frame(self, i):
                return None if i < 0 else np.full((4, 4, 3), i * 20, np.uint8)
        class Scan(Camera):
            def frame(self, i):
                return None if i < 0 else SimpleNamespace(x=np.array([i+1]), y=np.array([2]),
                                                         frame_id="laser", range_max=12, total_rays=1)
        w = MainWindow(ViewerConfig())
        try:
            a, b = Camera([0, 0.5, 1]), Camera([0.2, 0.6, 0.9])
            scan = Scan([0.1, 0.4, 0.8])
            w.source = SimpleNamespace(cameras={"/a": a, "/b": b}, images=a, scan=scan, close=lambda: None)
            w.spatial_panel.set_sources(w.source.cameras, a, scan, "/scan")
            w.controller.set_data(1, a.timestamps)
            w.camera_panel.selector.setCurrentText("/b")
            self.assertIs(w.controller.timestamps, b.timestamps)
            w.spatial_panel.actions["/a"].setChecked(False)
            w.spatial_panel.actions["/b"].setChecked(True)
            b_video = next(video for topic, _, video in w.spatial_panel.cells if topic == "/b")
            self.assertIsNone(b_video.original)
            w.controller.step_frame(1)
            self.assertEqual(w.controller.current_time, 0.2)
            self.assertIsNotNone(b_video.original)
            w.spatial_panel._select_all(True)
            w.seek(0.55)
            self.assertEqual(w.camera_panel.last_indices, {"/a": 1, "/b": 0})
            self.assertEqual(w.scan_view.last_index, 1)
            w.seek(0)
            self.assertEqual(w.scan_view.last_index, -1)
            self.assertIn("No scan", w.scan_view.info.text())
            w.seek(0.9)
            self.assertEqual(w.scan_view.last_index, 2)
            w.scan_view.flip_y.setChecked(True)
            np.testing.assert_allclose(w.scan_view.points.xData, [-2])
            np.testing.assert_allclose(w.scan_view.points.yData, [3])
            np.testing.assert_allclose(scan.frame(2).y, [2])
            w.scan_view.flip_y.setChecked(False)
            np.testing.assert_allclose(w.scan_view.points.xData, [2])
            self.assertTrue(w.scan_view.plot.getViewBox().state["xInverted"])
            w.spatial_panel.actions["/scan"].setChecked(False)
            w.seek(0.2)
            self.assertEqual(w.scan_view.last_index, 2)  # hidden scan is not decoded
            w.spatial_panel.actions["/scan"].setChecked(True)
            self.assertEqual(w.scan_view.last_index, 0)
            w.seek(0.9)
            w.spatial_panel.columns.setCurrentIndex(2)
            self.assertEqual(w.spatial_panel.grid.columnCount(), 3)
            self.assertEqual(w.camera_panel.last_indices, {"/a": 1, "/b": 2})
            w.camera_panel.set_sources({"/a": a}, a)
            self.assertEqual(len(w.camera_panel.cells), 1)
            self.assertNotIn("/scan", w.spatial_panel.actions)
            self.assertTrue(w.scan_view.isHidden())
            w.spatial_panel._select_all(False)
            self.assertFalse(w.spatial_panel.empty.isHidden())
        finally:
            w.close()
