"""Pose conversion and independently selected, timestamp-preserving overlays."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import math
from types import SimpleNamespace
import unittest

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from rosbag_viewer.config import ViewerConfig, pose_series
from rosbag_viewer.data import TimeSeriesData, quaternion_rpy, series_values
from rosbag_viewer.comparison import normalize_values
from rosbag_viewer.window import MainWindow

APP = QApplication.instance() or QApplication([])


def quaternion(roll, pitch, yaw):
    cr, cp, cy = (math.cos(a / 2) for a in (roll, pitch, yaw))
    sr, sp, sy = (math.sin(a / 2) for a in (roll, pitch, yaw))
    return (sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


class PoseTests(unittest.TestCase):
    def test_rotations_normalization_sign_and_invalid(self):
        for rpy in ((0, 0, 0), (0.3, -0.4, 1.2), (-0.7, 0.4, -2), (0, 0, math.pi / 2)):
            q = quaternion(*rpy)
            for scale in (1, 3, -2):
                np.testing.assert_allclose(quaternion_rpy(*(v * scale for v in q)), rpy, atol=1e-12)
        self.assertTrue(np.isnan(quaternion_rpy(0, 0, 0, 0)).all())
        self.assertTrue(np.isnan(quaternion_rpy(float("nan"), 0, 0, 1)).all())
        for pitch in (math.pi / 2, -math.pi / 2):
            np.testing.assert_allclose(quaternion_rpy(*quaternion(0, pitch, 0.8)),
                                       [0, pitch, 0.8], atol=1e-12)

    def test_pose_message_paths(self):
        pose = SimpleNamespace(position=SimpleNamespace(x=1, y=-2, z=3),
                               orientation=SimpleNamespace(x=0, y=0, z=0, w=1))
        for kind, msg in (
            ("geometry_msgs/msg/PoseStamped", SimpleNamespace(pose=pose)),
            ("geometry_msgs/msg/PoseWithCovarianceStamped", SimpleNamespace(pose=SimpleNamespace(pose=pose))),
            ("nav_msgs/msg/Odometry", SimpleNamespace(pose=SimpleNamespace(pose=pose))),
        ):
            position, orientation = pose_series("/pose", kind)
            ViewerConfig(series=(position, orientation))
            self.assertEqual(series_values(msg, position), (1, -2, 3))
            self.assertEqual(series_values(msg, orientation), (0, 0, 0))


class CompareTests(unittest.TestCase):
    def test_normalization_preserves_gaps_and_constants(self):
        np.testing.assert_allclose(normalize_values(np.array([-2, 0, 2, np.nan, np.inf])),
                                   [0, 0.5, 1, np.nan, np.nan])
        np.testing.assert_allclose(normalize_values(np.array([7, np.nan, 7])), [0, np.nan, 0])
        self.assertTrue(np.isnan(normalize_values(np.array([np.nan]))).all())

    def test_independent_planes_units_and_timestamp_sync(self):
        window = MainWindow(ViewerConfig())
        try:
            specs = window.config.series
            a = TimeSeriesData(specs[0], np.array([0, 0.25, 1]),
                               np.array([[1, 2, 3], [3, 4, 5], [5, 6, 7]]), np.zeros(3))
            b = TimeSeriesData(specs[1], np.array([0.1, 0.7]),
                               np.array([[10, 20, 30], [20, 30, 40]]), np.zeros(2))
            custom = window.custom_compare
            custom.set_data([a, b], 1)
            window.source = SimpleNamespace(images=SimpleNamespace(
                index_at=lambda t: -1, frame=lambda i: None), close=lambda: None)
            window.controller.set_data(1, np.array([0.0, 1.0]))
            window._enable_transport(True)
            window.graph_tabs.setCurrentIndex(window.custom_index)
            custom.items[0, 0].setCheckState(1, Qt.CheckState.Checked)
            custom.items[1, 2].setCheckState(1, Qt.CheckState.Checked)
            self.assertEqual(set(custom.panes[0].curves), {(0, 0), (1, 2)})
            self.assertIn("Mixed units", custom.panes[0].plot.getAxis("left").labelText)
            np.testing.assert_allclose(custom.panes[0].curves[1, 2].xData, b.time)
            np.testing.assert_allclose(custom.panes[0].curves[1, 2].yData, b.values[:, 2])
            custom.plane_count.setCurrentIndex(1)
            custom.items[0, 0].setCheckState(2, Qt.CheckState.Checked)
            custom.panes[1].scale.setCurrentIndex(1)
            np.testing.assert_allclose(custom.panes[1].curves[0, 0].yData, [0, 0.5, 1])
            np.testing.assert_allclose(custom.panes[0].curves[0, 0].yData, [1, 3, 5])
            custom.plane_count.setCurrentIndex(0)
            self.assertTrue(custom.panes[1].isHidden())
            custom.plane_count.setCurrentIndex(1)
            self.assertIn((0, 0), custom.panes[1].curves)
            custom.plots[0].setXRange(0.2, 0.8, padding=0)
            for plot in window._time_plots():
                np.testing.assert_allclose(plot.viewRange()[0], [0.2, 0.8])
            custom.plots[1].cursor.setValue(0.6)
            custom.plots[1].cursor.sigDragged.emit(custom.plots[1].cursor)
            self.assertEqual(window.controller.current_time, 0.6)
            for plot in window._time_plots():
                self.assertEqual(plot.cursor.value(), 0.6)
            custom.search.setText("Accelerometer")
            self.assertTrue(custom.items[0, 0].isHidden())
            self.assertIn((0, 0), custom.panes[0].curves)  # filtering never deselects
            custom.clear_selection()
            self.assertFalse(custom.panes[0].curves)
            self.assertFalse(custom.panes[1].curves)
            custom.set_data([b], 1)  # no stale selections after reopening a bag
            self.assertEqual(len(custom.items), 3)
            self.assertFalse(custom.panes[0].curves)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
