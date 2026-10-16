"""Launch from the workspace with uv run python -m rosbag_viewer."""
import argparse
from dataclasses import replace
import sys
from pathlib import Path

# Also support `uv run python rosbag_viewer/main.py`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rosbag_viewer.config import ViewerConfig, default_series


def main():
    parser = argparse.ArgumentParser(description="Synchronized ROS2 MCAP camera/IMU viewer")
    parser.add_argument("bag", nargs="?", help="Directory containing metadata.yaml")
    parser.add_argument("--image-topic", default=ViewerConfig.image_topic)
    parser.add_argument("--gyro-topic", default="/camera/gyro/sample")
    parser.add_argument("--accel-topic", default="/camera/accel/sample")
    parser.add_argument("--timestamp", choices=("header", "record"), default="header")
    parser.add_argument("--cache-mib", type=int, default=64)
    parser.add_argument("--temp-dir", help="Directory for temporary serialized camera data")
    parser.add_argument("--motor-topic", default="/motor_bridge_node/status",
                        help="Optional JSON motor telemetry topic (auto-enabled when present)")
    parser.add_argument("--no-motor", action="store_true", help="Disable motor telemetry graphs")
    parser.add_argument("--pose-topic", default="/camera/pose/sample", help="Optional pose topic")
    parser.add_argument("--no-pose", action="store_true", help="Disable pose graphs")
    parser.add_argument("--scan-topic", default="/scan", help="Optional LaserScan topic")
    parser.add_argument("--no-scan", action="store_true", help="Disable LaserScan loading")
    parser.add_argument("--cmd-vel-topic", default="/cmd_vel", help="Optional Twist/TwistStamped topic")
    parser.add_argument("--no-cmd-vel", action="store_true", help="Disable velocity command graphs")
    args = parser.parse_args()
    if args.cache_mib < 0:
        parser.error("--cache-mib must be nonnegative")
    gyro, accel = default_series()
    config = ViewerConfig(args.image_topic,
                          (replace(gyro, topic=args.gyro_topic), replace(accel, topic=args.accel_topic)),
                          args.timestamp, args.cache_mib * 1024**2, args.temp_dir,
                          None if args.no_motor else args.motor_topic,
                          None if args.no_pose else args.pose_topic,
                          None if args.no_scan else args.scan_topic,
                          None if args.no_cmd_vel else args.cmd_vel_topic)
    from PySide6.QtWidgets import QApplication
    from rosbag_viewer.window import MainWindow
    app = QApplication(sys.argv[:1])
    window = MainWindow(config, args.bag)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
