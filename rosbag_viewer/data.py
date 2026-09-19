"""ROS bag scan and a disk-backed random-access image index.

Only numeric series/indexes stay in memory. Serialized camera messages live in
an automatically removed temporary file; decoding happens on demand.
"""
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import tempfile
import re
import json
from typing import Callable

import numpy as np

from .config import SeriesSpec, ViewerConfig, motor_series


def sensor_timestamp(msg, record_ns: int, mode: str) -> tuple[int, bool]:
    stamp = getattr(getattr(msg, "header", None), "stamp", None)
    if mode == "header" and stamp is not None:
        ns = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
        if ns > 0 and 0 <= stamp.nanosec < 1_000_000_000:
            return ns, False
    return int(record_ns), mode == "header"


def field_value(msg, path: str) -> float:
    for part in path.split("."):
        match = re.fullmatch(r"([A-Za-z_]\w*)((?:\[\d+\])*)", part)
        if not match:
            raise ValueError(f"Invalid numeric field path: {path}")
        if isinstance(msg, dict):
            if match[1] not in msg:
                return float("nan")
            msg = msg[match[1]]
        else:
            msg = getattr(msg, match[1])
        for index in re.findall(r"\[(\d+)\]", match[2]):
            # A missing array entry is a gap, not a zero-valued wheel sample.
            if int(index) >= len(msg):
                return float("nan")
            msg = msg[int(index)]
    return float(msg)


def series_values(payload, spec):
    values = []
    for i, (path, scale) in enumerate(zip(spec.fields, spec.scales or (1.0,) * len(spec.fields))):
        try:
            if spec.validity_fields and field_value(payload, spec.validity_fields[i]) != 1:
                values.append(float("nan"))
                continue
            values.append(field_value(payload, path) * scale)
        except (TypeError, ValueError, AttributeError):
            if spec.payload != "json":
                raise
            values.append(float("nan"))
    return tuple(values)


@dataclass
class TimeSeriesData:
    spec: SeriesSpec
    time: np.ndarray
    values: np.ndarray
    record_ns: np.ndarray


# IMU and future numeric topics share the same representation.
ImuData = TimeSeriesData


class ImageSource:
    def __init__(self, spool, timestamps, records, offsets, lengths, decoder,
                 cache_bytes=64 * 1024 * 1024):
        self.spool = spool
        self.timestamps = timestamps
        self.record_ns = records
        self.offsets = offsets
        self.lengths = lengths
        self.decoder = decoder
        self.cache_bytes = cache_bytes
        self.cache = OrderedDict()
        self.cached_bytes = 0

    def index_at(self, time_s: float) -> int:
        return int(np.searchsorted(self.timestamps, time_s, side="right")) - 1

    def frame(self, index: int):
        if index < 0 or index >= len(self.timestamps):
            return None
        if index in self.cache:
            self.cache.move_to_end(index)
            return self.cache[index]
        self.spool.seek(int(self.offsets[index]))
        raw = self.spool.read(int(self.lengths[index]))
        if len(raw) != self.lengths[index]:
            raise OSError("Incomplete image cache read")
        rgb = np.ascontiguousarray(self.decoder(raw))
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("Image decoder must return RGB uint8")
        while self.cache and self.cached_bytes + rgb.nbytes > self.cache_bytes:
            _, old = self.cache.popitem(last=False)
            self.cached_bytes -= old.nbytes
        if rgb.nbytes <= self.cache_bytes:
            self.cache[index] = rgb
            self.cached_bytes += rgb.nbytes
        return rgb

    def close(self):
        self.cache.clear()
        self.cached_bytes = 0
        self.spool.close()


class BagDataSource:
    def __init__(self, config: ViewerConfig):
        self.config = config
        self.topics = {}
        self.series = []
        self.images = None
        self.origin_ns = 0
        self.duration = 0.0
        self.warnings = []

    def load(self, path: str, progress: Callable[[str], None] = lambda _: None,
             cancelled: Callable[[], bool] = lambda: False):
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message

        self.close()
        self.series = []
        self.warnings = []
        bag_path = Path(path).expanduser().resolve()
        if not bag_path.is_dir() or not (bag_path / "metadata.yaml").is_file():
            raise ValueError("metadata.yaml이 있는 ROS2 bag 디렉터리를 선택하세요.")
        reader = rosbag2_py.SequentialReader()
        reader.open(rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
                    rosbag2_py.ConverterOptions("cdr", "cdr"))
        self.topics = {t.name: t.type for t in reader.get_all_topics_and_types()}
        specs = list(self.config.series)
        if self.config.motor_topic in self.topics:
            names = {s.name for s in specs}
            specs.extend(s for s in motor_series(self.config.motor_topic) if s.name not in names)
        expected = {self.config.image_topic: "sensor_msgs/msg/Image"}
        for spec in specs:
            if spec.topic in expected and expected[spec.topic] != spec.message_type:
                raise ValueError(f"Conflicting types for {spec.topic}")
            expected[spec.topic] = spec.message_type
        for topic, kind in expected.items():
            actual = self.topics.get(topic)
            if actual != kind:
                available = "\n".join(f"{k}: {v}" for k, v in self.topics.items())
                raise ValueError(f"{topic}: expected {kind}, found {actual}\n\n{available}")
        types = {t: get_message(kind) for t, kind in expected.items()}
        reader.set_filter(rosbag2_py.StorageFilter(topics=list(expected)))
        spool = tempfile.TemporaryFile(dir=self.config.temp_dir)
        image_rows = []
        rows = [[] for _ in specs]
        json_topics = {s.topic for s in specs if s.payload == "json"}
        count = fallback_count = malformed_count = 0
        try:
            while reader.has_next():
                if cancelled():
                    raise InterruptedError("Loading cancelled")
                topic, raw, record_ns = reader.read_next()
                msg = deserialize_message(raw, types[topic])
                stamp_ns, fallback = sensor_timestamp(msg, record_ns, self.config.timestamp_mode)
                fallback_count += fallback
                if topic == self.config.image_topic:
                    offset = spool.tell()
                    spool.write(raw)
                    image_rows.append((stamp_ns, record_ns, offset, len(raw)))
                payload = None
                if topic in json_topics:
                    try:
                        payload = json.loads(msg.data)
                        if not isinstance(payload, dict):
                            raise ValueError("Expected JSON object")
                    except (ValueError, TypeError):
                        payload = {}
                        malformed_count += 1
                for spec, samples in zip(specs, rows):
                    if topic == spec.topic:
                        samples.append((stamp_ns, record_ns,
                                        series_values(payload if spec.payload == "json" else msg, spec)))
                count += 1
                if count % 500 == 0:
                    progress(f"Scanning: {count:,} messages / image cache {spool.tell()/2**20:.1f} MiB")
            if not image_rows:
                raise ValueError("선택한 카메라 토픽에 프레임이 없습니다.")
            # Subtract integer nanoseconds before conversion to avoid epoch precision loss.
            self.origin_ns = min([min(r[0] for r in image_rows)] +
                                 [min(r[0] for r in samples) for samples in rows if samples])
            image_rows.sort(key=lambda r: r[0])  # stable for duplicate sensor timestamps
            index = np.asarray(image_rows, dtype=np.int64)
            times = (index[:, 0] - self.origin_ns).astype(np.float64) * 1e-9
            for spec, samples in zip(specs, rows):
                samples.sort(key=lambda r: r[0])
                if not samples:
                    self.warnings.append(f"No samples: {spec.topic}")
                stamps = np.asarray([r[0] for r in samples], dtype=np.int64)
                self.series.append(TimeSeriesData(
                    spec, (stamps - self.origin_ns).astype(np.float64) * 1e-9,
                    np.asarray([r[2] for r in samples], dtype=np.float64).reshape(-1, len(spec.fields)),
                    np.asarray([r[1] for r in samples], dtype=np.int64)))
            self.duration = max([float(times[-1])] +
                                [float(s.time[-1]) for s in self.series if len(s.time)])
            if fallback_count:
                self.warnings.append(f"{fallback_count:,} messages used record timestamps (missing/zero header)")
            if malformed_count:
                self.warnings.append(f"{malformed_count:,} invalid JSON messages shown as gaps")
            spool.flush()
            self.images = ImageSource(spool, times, index[:, 1], index[:, 2], index[:, 3],
                                      self._decoder(types[self.config.image_topic]), self.config.cache_bytes)
            progress(f"Loaded {count:,} messages; {len(times):,} frames")
            return self
        except BaseException:
            spool.close()
            raise
        finally:
            del reader

    @staticmethod
    def _decoder(message_type):
        # CvBridge is constructed only when the GUI first requests a frame.
        bridge = None

        def decode(raw):
            nonlocal bridge
            import cv2
            from cv_bridge import CvBridge
            from rclpy.serialization import deserialize_message
            if bridge is None:
                bridge = CvBridge()
            msg = deserialize_message(raw, message_type)
            if msg.encoding in ("mono8", "8UC1"):
                return cv2.cvtColor(bridge.imgmsg_to_cv2(msg, "passthrough"), cv2.COLOR_GRAY2RGB)
            if msg.encoding in ("mono16", "16UC1"):
                gray = bridge.imgmsg_to_cv2(msg, "passthrough")
                return cv2.cvtColor((gray / 256).astype(np.uint8), cv2.COLOR_GRAY2RGB)
            return bridge.imgmsg_to_cv2(msg, "rgb8")
        return decode

    def close(self):
        if self.images is not None:
            self.images.close()
            self.images = None
