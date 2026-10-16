"""Topic configuration; add SeriesSpec entries to extend the viewer."""
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class SeriesSpec:
    name: str
    topic: str
    message_type: str
    fields: tuple[str, ...]
    labels: tuple[str, ...]
    units: str
    group: str = "Other"
    scales: tuple[float, ...] = ()
    payload: str = "ros"
    validity_fields: tuple[str, ...] = ()
    transform: str = "identity"


def default_series():
    return (
        SeriesSpec("Gyroscope", "/camera/gyro/sample", "sensor_msgs/msg/Imu",
                   tuple(f"angular_velocity.{axis}" for axis in "xyz"),
                   ("x", "y", "z"), "rad/s", group="IMU"),
        SeriesSpec("Accelerometer", "/camera/accel/sample", "sensor_msgs/msg/Imu",
                   tuple(f"linear_acceleration.{axis}" for axis in "xyz"),
                   ("x", "y", "z"), "m/s²", group="IMU"),
    )


@dataclass(frozen=True)
class ViewerConfig:
    image_topic: str = "/camera/fisheye1/image_raw"
    series: tuple[SeriesSpec, ...] = field(default_factory=default_series)
    timestamp_mode: str = "header"  # "record" for incompatible sensor clocks
    cache_bytes: int = 64 * 1024 * 1024
    temp_dir: str | None = None
    motor_topic: str | None = "/motor_bridge_node/status"
    pose_topic: str | None = "/camera/pose/sample"
    scan_topic: str | None = "/scan"
    cmd_vel_topic: str | None = "/cmd_vel"

    def __post_init__(self):
        if self.timestamp_mode not in ("header", "record"):
            raise ValueError("timestamp_mode must be header or record")
        if self.cache_bytes < 0:
            raise ValueError("cache_bytes must be nonnegative")
        if len({s.name for s in self.series}) != len(self.series):
            raise ValueError("Series names must be unique")
        for spec in self.series:
            if spec.transform not in ("identity", "quaternion_rpy"):
                raise ValueError("Unsupported series transform")
            if spec.transform == "quaternion_rpy":
                if len(spec.fields) != 4 or len(spec.labels) != 3 or spec.scales or spec.validity_fields:
                    raise ValueError("quaternion_rpy needs xyzw fields and three labels, without scales/validity")
            elif not spec.fields or len(spec.fields) != len(spec.labels):
                raise ValueError("Each series needs matching fields and labels")
            if spec.scales and (len(spec.scales) != len(spec.fields) or
                                not all(math.isfinite(s) for s in spec.scales)):
                raise ValueError("scales must contain one finite multiplier per field")
            if spec.payload not in ("ros", "json"):
                raise ValueError("payload must be ros or json")
            if spec.validity_fields and len(spec.validity_fields) != len(spec.fields):
                raise ValueError("validity_fields must match fields")
            if not spec.group.strip():
                raise ValueError("Series group must not be empty")


def motor_series(topic: str) -> tuple[SeriesSpec, ...]:
    """Motor bridge v1 JSON telemetry. Wheel order is explicit, never inferred."""
    wheels = ("lf", "rf", "lr", "rr")
    labels = ("LF · Front left", "RF · Front right", "LR · Rear left", "RR · Rear right")
    valid = tuple(f"wheels.{wheel}.valid" for wheel in wheels)
    specs = []
    for name, key, units, scale, group in (
        ("Wheel RPM", "rpm", "rpm", 1.0, "Wheels"),
        ("Wheel current", "current_deci_amp", "A", 0.1, "Wheels"),
        ("Controller output", "controller_output", "raw", 1.0, "Motor"),
    ):
        specs.append(SeriesSpec(name, topic, "std_msgs/msg/String",
                     tuple(f"wheels.{wheel}.{key}" for wheel in wheels), labels, units,
                     group=group, scales=(scale,) * 4, payload="json", validity_fields=valid))
    specs.append(SeriesSpec("Driver voltage", topic, "std_msgs/msg/String",
                 ("drivers.a.voltage_mv", "drivers.b.voltage_mv"), ("Driver A", "Driver B"), "V",
                 group="Motor", scales=(0.001, 0.001), payload="json",
                 validity_fields=("drivers.a.valid", "drivers.b.valid")))
    return tuple(specs)


def pose_series(topic: str, message_type: str) -> tuple[SeriesSpec, ...]:
    prefixes = {
        "nav_msgs/msg/Odometry": "pose.pose",
        "geometry_msgs/msg/PoseStamped": "pose",
        "geometry_msgs/msg/PoseWithCovarianceStamped": "pose.pose",
    }
    if message_type not in prefixes:
        raise ValueError(f"Unsupported pose type: {message_type}")
    prefix = prefixes[message_type]
    return (
        SeriesSpec("Pose position", topic, message_type,
                   tuple(f"{prefix}.position.{axis}" for axis in "xyz"),
                   ("x", "y", "z"), "m", group="Pose"),
        SeriesSpec("Pose orientation", topic, message_type,
                   tuple(f"{prefix}.orientation.{axis}" for axis in "xyzw"),
                   ("roll", "pitch", "yaw"), "rad", group="Pose", transform="quaternion_rpy"),
    )


def command_series(topic: str, message_type: str) -> tuple[SeriesSpec, ...]:
    if message_type not in ("geometry_msgs/msg/Twist", "geometry_msgs/msg/TwistStamped"):
        raise ValueError(f"Unsupported velocity command type: {message_type}")
    prefix = "twist." if message_type.endswith("TwistStamped") else ""
    return tuple(SeriesSpec(name, topic, message_type,
                           tuple(f"{prefix}{field}.{axis}" for axis in "xyz"),
                           ("x", "y", "z"), units, group="Command")
                 for name, field, units in (("Command linear velocity", "linear", "m/s"),
                                            ("Command angular velocity", "angular", "rad/s")))
