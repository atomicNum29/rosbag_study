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
    args = parser.parse_args()
    if args.cache_mib < 0:
        parser.error("--cache-mib must be nonnegative")
    gyro, accel = default_series()
    config = ViewerConfig(args.image_topic,
                          (replace(gyro, topic=args.gyro_topic), replace(accel, topic=args.accel_topic)),
                          args.timestamp, args.cache_mib * 1024**2, args.temp_dir)
    from PySide6.QtWidgets import QApplication
    from rosbag_viewer.window import MainWindow
    app = QApplication(sys.argv[:1])
    window = MainWindow(config, args.bag)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
