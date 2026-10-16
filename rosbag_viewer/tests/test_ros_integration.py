"""Create a real MCAP fixture with ROS serialization and read/decode it."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace

import numpy as np

from rosbag_viewer.config import ViewerConfig
from rosbag_viewer.data import BagDataSource

ROS_AVAILABLE = all(importlib.util.find_spec(name) for name in
                    ("rosbag2_py", "sensor_msgs", "rclpy", "cv_bridge"))


@unittest.skipUnless(ROS_AVAILABLE, "Source ROS2 to run MCAP integration tests")
class RosIntegrationTests(unittest.TestCase):
    def test_multicamera_scan_command_disk_roundtrip(self):
        import rosbag2_py
        import cv2
        from rclpy.serialization import serialize_message
        from sensor_msgs.msg import Image, CompressedImage, LaserScan
        from geometry_msgs.msg import Twist, TwistStamped
        config = ViewerConfig(series=(), motor_topic=None, pose_topic=None, image_topic="/a")
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "bag")
            writer = rosbag2_py.SequentialWriter()
            writer.open(rosbag2_py.StorageOptions(uri=path, storage_id="mcap"),
                        rosbag2_py.ConverterOptions("cdr", "cdr"))
            topics = (("/a", "sensor_msgs/msg/Image"), ("/b", "sensor_msgs/msg/Image"),
                      ("/compressed", "sensor_msgs/msg/CompressedImage"),
                      ("/scan", "sensor_msgs/msg/LaserScan"), ("/cmd_vel", "geometry_msgs/msg/Twist"),
                      ("/stamped", "geometry_msgs/msg/TwistStamped"))
            for i, (name, kind) in enumerate(topics):
                writer.create_topic(rosbag2_py.TopicMetadata(id=i, name=name, type=kind, serialization_format="cdr"))
            for i, topic in enumerate(("/a", "/b")):
                msg = Image()
                msg.header.stamp.sec = 100
                msg.header.stamp.nanosec = i * 100_000_000
                msg.width = msg.height = msg.step = 1
                msg.encoding = "mono8"
                msg.data = [20 + i]
                writer.write(topic, serialize_message(msg), 100_000_000_000 + i * 100_000_000)
            compressed = CompressedImage()
            compressed.header.stamp.sec = 100
            compressed.format = "png"
            ok, encoded = cv2.imencode(".png", np.array([[[0, 0, 255]]], dtype=np.uint8))
            self.assertTrue(ok)
            compressed.data = encoded.tobytes()
            writer.write("/compressed", serialize_message(compressed), 100_200_000_000)
            scan = LaserScan()
            scan.header.stamp.sec = 100
            scan.header.stamp.nanosec = 50_000_000
            scan.header.frame_id = "laser"
            scan.angle_increment = np.pi / 2
            scan.range_min, scan.range_max = 0.1, 12.0
            scan.ranges = [1.0, 2.0, float("inf"), float("nan")]
            writer.write("/scan", serialize_message(scan), 100_300_000_000)
            cmd = Twist()
            cmd.linear.x, cmd.angular.z = 0.5, -0.3
            writer.write("/cmd_vel", serialize_message(cmd), 100_400_000_000)
            stamped = TwistStamped()
            stamped.header.stamp.sec = 101
            stamped.twist = cmd
            writer.write("/stamped", serialize_message(stamped), 102_000_000_000)
            del writer
            source = BagDataSource(config)
            try:
                source.load(path)
                self.assertEqual(set(source.cameras), {"/a", "/b", "/compressed"})
                self.assertIs(source.images, source.cameras["/a"])
                self.assertEqual(source.cameras["/b"].index_at(0.05), -1)
                self.assertEqual(source.cameras["/b"].frame(0)[0, 0, 0], 21)
                np.testing.assert_array_equal(source.cameras["/compressed"].frame(0)[0, 0], [255, 0, 0])
                self.assertLessEqual(sum(c.cache_bytes for c in source.cameras.values()), config.cache_bytes)
                self.assertEqual(source.scan.index_at(0.04), -1)
                self.assertEqual(source.scan.index_at(0.06), 0)
                np.testing.assert_allclose(source.scan.frame(0).x, [1, 0], atol=1e-6)
                np.testing.assert_allclose(source.scan.frame(0).y, [0, 2], atol=1e-6)
                self.assertEqual(source.series[0].spec.group, "Command")
                np.testing.assert_allclose(source.series[0].time, [0.4])
                np.testing.assert_allclose(source.series[0].values[0], [0.5, 0, 0])
                handles = [c.spool for c in source.cameras.values()] + [source.scan.spool]
            finally:
                source.close()
            self.assertTrue(all(f.closed for f in handles))
            stamped_source = BagDataSource(replace(config, scan_topic=None, cmd_vel_topic="/stamped"))
            try:
                stamped_source.load(path)
                self.assertIsNone(stamped_source.scan)
                np.testing.assert_allclose(stamped_source.series[0].time, [1])
            finally:
                stamped_source.close()

    def test_pose_autodetection_relative_time_and_invalid_quaternion(self):
        import rosbag2_py
        from rclpy.serialization import serialize_message
        from sensor_msgs.msg import Image
        from nav_msgs.msg import Odometry
        config = ViewerConfig(series=(), motor_topic=None)
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "bag")
            writer = rosbag2_py.SequentialWriter()
            writer.open(rosbag2_py.StorageOptions(uri=path, storage_id="mcap"),
                        rosbag2_py.ConverterOptions("cdr", "cdr"))
            for i, (name, kind) in enumerate(((config.image_topic, "sensor_msgs/msg/Image"),
                                               (config.pose_topic, "nav_msgs/msg/Odometry"))):
                writer.create_topic(rosbag2_py.TopicMetadata(
                    id=i, name=name, type=kind, serialization_format="cdr"))
            image = Image()
            image.header.stamp.sec = 100
            writer.write(config.image_topic, serialize_message(image), 100_000_000_000)
            for i in range(2):
                msg = Odometry()
                msg.header.stamp.sec = 101 + i
                msg.pose.pose.position.x = 2.0 + i
                if i == 0:
                    msg.pose.pose.orientation.z = 2 ** -0.5
                    msg.pose.pose.orientation.w = 2 ** -0.5
                else:
                    msg.pose.pose.orientation.w = 0.0
                writer.write(config.pose_topic, serialize_message(msg), (101 + i) * 1_000_000_000 + 5)
            del writer
            source = BagDataSource(config)
            try:
                source.load(path)
                self.assertEqual(len(source.series), 2)
                position, orientation = source.series
                np.testing.assert_allclose(position.time, [1, 2])
                np.testing.assert_allclose(position.values[:, 0], [2, 3])
                self.assertEqual(orientation.values.shape, (2, 3))
                np.testing.assert_allclose(orientation.values[0], [0, 0, np.pi / 2], atol=1e-12)
                self.assertTrue(np.isnan(orientation.values[1]).all())
                self.assertEqual(source.duration, 2)
            finally:
                source.close()
            disabled = BagDataSource(replace(config, pose_topic=None))
            try:
                disabled.load(path)
                self.assertEqual(disabled.series, [])
            finally:
                disabled.close()

    def test_motor_json_autodetection_and_invalid_payload_gaps(self):
        import rosbag2_py
        from rclpy.serialization import serialize_message
        from sensor_msgs.msg import Image
        from std_msgs.msg import String
        config = ViewerConfig(series=())
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "bag")
            writer = rosbag2_py.SequentialWriter()
            writer.open(rosbag2_py.StorageOptions(uri=path, storage_id="mcap"),
                        rosbag2_py.ConverterOptions("cdr", "cdr"))
            for i, (name, kind) in enumerate(((config.image_topic, "sensor_msgs/msg/Image"),
                                               (config.motor_topic, "std_msgs/msg/String"))):
                writer.create_topic(rosbag2_py.TopicMetadata(
                    id=i, name=name, type=kind, serialization_format="cdr"))
            image = Image()
            image.header.stamp.sec = 100
            image.width = image.height = image.step = 1
            image.encoding = "mono8"
            image.data = [0]
            writer.write(config.image_topic, serialize_message(image), 100_000_000_000)
            payload = {"wheels": {"lf": {"valid": True, "rpm": -150, "current_deci_amp": 31}},
                       "drivers": {"a": {"valid": True, "voltage_mv": 26700}}}
            for i, text in enumerate((json.dumps(payload), "not json", "[]")):
                writer.write(config.motor_topic, serialize_message(String(data=text)),
                             100_000_000_000 + (i + 1) * 1_000_000)
            del writer
            source = BagDataSource(config)
            try:
                source.load(path)
                self.assertEqual(len(source.series), 4)
                rpm, current, output, voltage = source.series
                self.assertEqual(rpm.values[0, 0], -150)
                self.assertAlmostEqual(current.values[0, 0], 3.1)
                self.assertAlmostEqual(voltage.values[0, 0], 26.7)
                self.assertTrue(np.isnan(current.values[1:]).all())
                np.testing.assert_allclose(current.time, [0.001, 0.002, 0.003])
                self.assertTrue(any("2 invalid JSON" in text for text in source.warnings))
            finally:
                source.close()
            disabled = BagDataSource(replace(config, motor_topic=None))
            try:
                disabled.load(path)
                self.assertEqual(disabled.series, [])
            finally:
                disabled.close()

    def test_mcap_roundtrip_and_shared_imu_topic(self):
        import rosbag2_py
        from rclpy.serialization import serialize_message
        from sensor_msgs.msg import Image, Imu
        config = ViewerConfig()
        config = replace(config, series=tuple(replace(s, topic="/imu") for s in config.series))
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "bag")
            writer = rosbag2_py.SequentialWriter()
            writer.open(rosbag2_py.StorageOptions(uri=path, storage_id="mcap"),
                        rosbag2_py.ConverterOptions("cdr", "cdr"))
            for i, (name, kind) in enumerate(((config.image_topic, "sensor_msgs/msg/Image"),
                                               ("/imu", "sensor_msgs/msg/Imu"))):
                writer.create_topic(rosbag2_py.TopicMetadata(
                    id=i, name=name, type=kind, serialization_format="cdr"))
            epoch = 1_700_000_000_000_000_000
            # Out-of-order header stamps and duplicate timestamps must retain alignment.
            for i, ns in enumerate((200_000_000, 0, 200_000_000)):
                msg = Image()
                msg.header.stamp.sec = 100
                msg.header.stamp.nanosec = ns
                msg.width, msg.height, msg.step = 2, 2, 2
                msg.encoding = "mono8"
                msg.data = [i * 40] * 4
                writer.write(config.image_topic, serialize_message(msg), epoch + i * 10)
                imu = Imu()
                imu.header = msg.header
                imu.angular_velocity.x = float(i)
                imu.linear_acceleration.z = float(i + 10)
                writer.write("/imu", serialize_message(imu), epoch + i * 10 + 1)
            del writer
            source = BagDataSource(config)
            try:
                source.load(path)
                np.testing.assert_allclose(source.images.timestamps, [0, 0.2, 0.2])
                np.testing.assert_allclose(source.series[0].values[:, 0], [1, 0, 2])
                np.testing.assert_allclose(source.series[1].values[:, 2], [11, 10, 12])
                np.testing.assert_array_equal(source.images.record_ns, [epoch + 10, epoch, epoch + 20])
                self.assertEqual(source.images.frame(2)[0, 0, 0], 80)
                self.assertEqual(source.images.frame(0)[0, 0, 0], 40)
                self.assertEqual(source.images.index_at(0.2), 2)
                self.assertAlmostEqual(source.duration, 0.2)
            finally:
                source.close()
            record_source = BagDataSource(replace(config, timestamp_mode="record"))
            try:
                record_source.load(path)
                np.testing.assert_allclose(record_source.images.timestamps, [0, 1e-8, 2e-8])
                self.assertEqual(record_source.origin_ns, epoch)
            finally:
                record_source.close()
            with self.assertRaises(InterruptedError):
                BagDataSource(config).load(path, cancelled=lambda: True)
            bad = BagDataSource(replace(config, image_topic="/missing"))
            try:
                bad.load(path)
                self.assertIs(bad.images, bad.cameras[config.image_topic])
                self.assertTrue(any("Default camera unavailable" in text for text in bad.warnings))
            finally:
                bad.close()


if __name__ == "__main__":
    unittest.main()
