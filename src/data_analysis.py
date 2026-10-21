from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

# Settings: edit this section to choose the recording, interval and figures.
DATA_DIR = Path("rosbag_data")
RECORDING = "2026-10-15_1"
START_SEC = 38
END_SEC = 400  # Exclusive; use None to keep the rest of the recording.
PLOT_GROUPS = {"status", "timing", "command", "pose", "wheels"}
# Example: PLOT_GROUPS = {"wheels"} opens only the wheel RPM figure.

SOURCES = {
    "cmd_vel": (f"cmd_vel_data_{RECORDING}.parquet", "timestamp"),
    "motor": (f"motor_data_{RECORDING}.parquet", "timestamp"),
    "pose": (f"pose_data_{RECORDING}.parquet", "sensor_time"),
}
FIGSIZE = (10, 5)
HIST_BINS = 100
POINT_STYLE = {
    "linestyle": "solid",
    "marker": "o",
    "markersize": 3,
    "markeredgecolor": (0, 0, 1, 0.1),
    "markerfacecolor": "none",
}
COMMAND_STYLE = {
    "marker": "o",
    "markersize": 3,
    "markeredgecolor": (1, 0, 0, 0.1),
    "markerfacecolor": "none",
}


def load_data():
    """Load all topics and select one shared recording-relative interval."""
    frames = {
        name: pd.read_parquet(DATA_DIR / filename, engine="pyarrow")
        for name, (filename, _) in SOURCES.items()
    }
    for frame in frames.values():
        print(frame.head())

    # Preserve the original clock columns; no sensor/recording clock conversion.
    t0 = min(frames[name][column].min() for name, (_, column) in SOURCES.items())
    times = {}
    for name, (_, column) in SOURCES.items():
        elapsed = frames[name][column] - t0
        mask = elapsed >= START_SEC
        if END_SEC is not None:
            mask = mask & (elapsed < END_SEC)
        frames[name] = frames[name].loc[mask].reset_index(drop=True)
        times[name] = (frames[name][column] - t0).to_numpy()
    return frames, times


def calculate_diagnostics(frames, times):
    """Calculate intervals and sequence differences without filtering messages."""
    intervals = {name: np.diff(timestamps) for name, timestamps in times.items()}
    messages = frames["motor"]["message"]
    sequence = np.array([message["seq"] for message in messages], dtype=np.int64)
    sequence_diff = np.diff(sequence) % 256
    any_invalid = any(message["validity"] != 63 for message in messages)
    any_skipped = bool(np.any(sequence_diff != 1))
    print(f"Any motor message with validity != 63: {any_invalid}")
    print(f"Any motor message with skipped sequence: {any_skipped}")
    return intervals, sequence_diff


def make_axes(number, rows=1):
    figure, axes = plt.subplots(rows, 1, num=number, figsize=FIGSIZE, squeeze=False)
    return figure, axes[:, 0]


def label_axes(ax, title, ylabel, xlabel="Timestamp (s)"):
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    ax.grid(True)


def plot_motor_status(frame, timestamps, sequence_diff):
    figure, axes = make_axes(1, rows=3)
    for ax, field, ylabel in zip(
        axes[:2], ("system_error", "validity"), ("System Error", "Validity")
    ):
        values = frame["message"].apply(lambda message: message[field])
        ax.plot(timestamps, values, marker="o", markersize=3)
        label_axes(ax, f"Motor {ylabel} Over Time", ylabel, xlabel="")

    # Keep the original convention: differences are placed at the earlier time.
    axes[2].plot(timestamps[:-1], sequence_diff, marker="o", markersize=3)
    label_axes(axes[2], "Motor Sequence Differences Over Time", "Sequence")
    figure.tight_layout()
    figure.savefig(f"img/motor_status_{RECORDING}.png", dpi=300)


def plot_timing(topic, timestamps, intervals, number, histogram_number=None):
    figure, (ax,) = make_axes(number)
    ax.plot(timestamps[:-1], intervals, **POINT_STYLE)
    label_axes(ax, f"Time Differences for {topic}", "Time Difference (s)")
    figure.tight_layout()
    figure.savefig(f"img/timing_{topic.replace('/', '-')}_{RECORDING}.png", dpi=300)

    if histogram_number is not None:
        counts, edges = np.histogram(intervals, bins=HIST_BINS)
        figure, (ax,) = make_axes(histogram_number)
        ax.bar(edges[:-1], counts, width=np.diff(edges), edgecolor="black")
        label_axes(
            ax,
            f"Histogram of Time Differences for {topic}",
            "Frequency",
            xlabel="Time Difference (s)",
        )
        figure.tight_layout()
        figure.savefig(
            f"img/timing_{topic.replace('/', '-')}_hist_{RECORDING}.png", dpi=300
        )


def plot_command(frame, timestamps):
    figure, axes = make_axes(4, rows=2)
    fields = (
        ("linear", "x", "Linear X", "m/s"),
        ("angular", "z", "Angular Z", "rad/s"),
    )
    for index, (ax, (field, component, label, unit)) in enumerate(zip(axes, fields)):
        values = frame[field].apply(lambda vector: vector[component])
        ax.plot(timestamps, values, **COMMAND_STYLE)
        label_axes(
            ax,
            f"{label} Velocity Over Time",
            f"{label} ({unit})",
            xlabel="" if index == 0 else "Timestamp (s)",
        )
    figure.tight_layout()
    figure.savefig(f"img/command_{RECORDING}.png", dpi=300)


def plot_pose_velocity(frame, timestamps):
    figure, axes = make_axes(8, rows=2)
    for index, (ax, field, unit) in enumerate(
        zip(axes, ("linear", "angular"), ("m/s", "rad/s"))
    ):
        for component in ("x", "y", "z"):
            values = frame["twist"].apply(lambda twist: twist[field][component])
            ax.plot(timestamps, values, alpha=0.5, label=f"{field}.{component}")
        label_axes(
            ax,
            f"{field.title()} Velocity Over Time" if index == 0 else "",
            f"{field.title()} Velocity ({unit})",
            xlabel="" if index == 0 else "Timestamp (s)",
        )
        ax.legend()
    figure.tight_layout()
    figure.savefig(f"img/pose_velocity_{RECORDING}.png", dpi=300)


def plot_wheel_rpm(frame, timestamps):
    figure, axes = make_axes(9, rows=2)
    wheel_pairs = (
        (("lf", "left front"), ("rf", "right front")),
        (("lr", "left rear"), ("rr", "right rear")),
    )
    for index, (ax, pair) in enumerate(zip(axes, wheel_pairs)):
        for wheel, label in pair:
            values = frame["message"].apply(
                lambda message: message["wheels"][wheel]["rpm"]
            )
            ax.plot(timestamps, values, alpha=0.5, label=label)
        label_axes(
            ax,
            "Wheel RPM Over Time" if index == 0 else "",
            "RPM",
            xlabel="" if index == 0 else "Timestamp (s)",
        )
        ax.legend()
    figure.tight_layout()
    figure.savefig(f"img/wheel_rpm_{RECORDING}.png", dpi=300)


def plot_wheel_amp(frame, timestamps):
    figure, axes = make_axes(10, rows=2)
    wheel_pairs = (
        (("lf", "left front"), ("rf", "right front")),
        (("lr", "left rear"), ("rr", "right rear")),
    )
    for index, (ax, pair) in enumerate(zip(axes, wheel_pairs)):
        for wheel, label in pair:
            values = frame["message"].apply(
                lambda message: message["wheels"][wheel]["current_deci_amp"] / 10.0
            )
            ax.plot(timestamps, values, alpha=0.5, label=label)
        label_axes(
            ax,
            "Wheel Current (Amp) Over Time" if index == 0 else "",
            "Current (A)",
            xlabel="" if index == 0 else "Timestamp (s)",
        )
        ax.legend()
    figure.tight_layout()
    figure.savefig(f"img/wheel_amp_{RECORDING}.png", dpi=300)


def plot_wheel_output(frame, timestamps):
    figure, axes = make_axes(11, rows=2)
    wheel_pairs = (
        (("lf", "left front"), ("rf", "right front")),
        (("lr", "left rear"), ("rr", "right rear")),
    )
    for index, (ax, pair) in enumerate(zip(axes, wheel_pairs)):
        for wheel, label in pair:
            values = frame["message"].apply(
                lambda message: message["wheels"][wheel]["controller_output"]
            )
            ax.plot(timestamps, values, alpha=0.5, label=label)
        label_axes(
            ax,
            "Wheel Output Over Time" if index == 0 else "",
            "Output",
            xlabel="" if index == 0 else "Timestamp (s)",
        )
        ax.legend()
    figure.tight_layout()
    figure.savefig(f"img/wheel_output_{RECORDING}.png", dpi=300)


def main():
    frames, times = load_data()
    intervals, sequence_diff = calculate_diagnostics(frames, times)

    if "status" in PLOT_GROUPS:
        plot_motor_status(frames["motor"], times["motor"], sequence_diff)
    if "timing" in PLOT_GROUPS:
        for name, topic, number, histogram in (
            ("motor", "/motor", 2, 3),
            ("cmd_vel", "/cmd_vel", 5, 6),
            ("pose", "/camera/pose/sample", 7, None),
        ):
            plot_timing(topic, times[name], intervals[name], number, histogram)
    if "command" in PLOT_GROUPS:
        plot_command(frames["cmd_vel"], times["cmd_vel"])
    if "pose" in PLOT_GROUPS:
        plot_pose_velocity(frames["pose"], times["pose"])
    if "wheels" in PLOT_GROUPS:
        plot_wheel_rpm(frames["motor"], times["motor"])
        plot_wheel_amp(frames["motor"], times["motor"])
        plot_wheel_output(frames["motor"], times["motor"])
    plt.show()


if __name__ == "__main__":
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", None)
    pd.set_option("display.width", None)
    main()
