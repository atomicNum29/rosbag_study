"""Create a real MCAP fixture with ROS serialization and read/decode it."""
import importlib.util
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
            with self.assertRaisesRegex(ValueError, "/missing"):
                bad.load(path)


if __name__ == "__main__":
    unittest.main()
