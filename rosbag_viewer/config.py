"""Topic configuration; add SeriesSpec entries to extend the viewer."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SeriesSpec:
    name: str
    topic: str
    message_type: str
    fields: tuple[str, ...]
    labels: tuple[str, ...]
    units: str


def default_series():
    return (
        SeriesSpec("Gyroscope", "/camera/gyro/sample", "sensor_msgs/msg/Imu",
                   tuple(f"angular_velocity.{axis}" for axis in "xyz"),
                   ("x", "y", "z"), "rad/s"),
        SeriesSpec("Accelerometer", "/camera/accel/sample", "sensor_msgs/msg/Imu",
                   tuple(f"linear_acceleration.{axis}" for axis in "xyz"),
                   ("x", "y", "z"), "m/s²"),
    )


@dataclass(frozen=True)
class ViewerConfig:
    image_topic: str = "/camera/fisheye1/image_raw"
    series: tuple[SeriesSpec, ...] = field(default_factory=default_series)
    timestamp_mode: str = "header"  # "record" for incompatible sensor clocks
    cache_bytes: int = 64 * 1024 * 1024
    temp_dir: str | None = None

    def __post_init__(self):
        if self.timestamp_mode not in ("header", "record"):
            raise ValueError("timestamp_mode must be header or record")
        if self.cache_bytes < 0:
            raise ValueError("cache_bytes must be nonnegative")
        if len({s.name for s in self.series}) != len(self.series):
            raise ValueError("Series names must be unique")
        for spec in self.series:
            if not spec.fields or len(spec.fields) != len(spec.labels):
                raise ValueError("Each series needs matching fields and labels")
