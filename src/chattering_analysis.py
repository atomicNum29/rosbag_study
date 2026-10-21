from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

DATA_DIR = Path("rosbag_data")
RECORDING = "2026-10-21_1"
OUTPUT_DIR = Path("img") / f"chattering_{RECORDING}"
# Recording-relative seconds; include start, exclude end: [start, end).
SEGMENTS = (
    (29, 36.3), (38.5, 47), (60.5, 64.48), (66, 70),
    (84.2, 86.9), (89, 92.1), (103.1, 104.83), (107.1, 109),
    (118.85, 120.3), (121.5, 123.4), (137.2, 142.2), (144, 151.7),
    (165.3, 168.9), (170.3, 174.35), (184.3, 186.6), (187.62, 190.95),
    (208.7, 211.6), (213, 217.8), (226.75, 229.75), (231.25, 234.55),
    (244.4, 246.9), (248.35, 251.5), (266.55, 268.1), (269, 270.05),
    (279.7, 281.67), (282.85, 284.65), (295.4, 298.43),
    (299.6, 301.65), (302.6, 304.8),
)
# Absolute tolerance only, applied to each component's full range (max - min).
CONSTANT_ATOL = 1e-9
SOURCES = {
    "cmd_vel": (f"cmd_vel_data_{RECORDING}.parquet", "timestamp"),
    "motor": (f"motor_data_{RECORDING}.parquet", "timestamp"),
    "pose": (f"pose_data_{RECORDING}.parquet", "sensor_time"),
}
COLORS = list(plt.get_cmap("tab20")(np.arange(20))) + list(
    plt.get_cmap("tab20b")(np.arange(9))
)


def load_data():
    """Split topics using the original shared clock, retaining original timestamps."""
    if any(end <= start for start, end in SEGMENTS) or any(
        end > next_start for (_, end), (next_start, _) in zip(SEGMENTS, SEGMENTS[1:])
    ):
        raise ValueError("Segments must be ordered, positive-length and non-overlapping")
    frames = {
        name: pd.read_parquet(DATA_DIR / filename, engine="pyarrow")
        for name, (filename, _) in SOURCES.items()
    }
    t0 = min(frames[name][column].min() for name, (_, column) in SOURCES.items())
    for name, (_, column) in SOURCES.items():
        frames[name] = frames[name].sort_values(column).reset_index(drop=True)
        frames[name]["elapsed_sec"] = frames[name][column] - t0
    segments = []
    offset = 0.0
    for number, (start, end) in enumerate(SEGMENTS, 1):
        topics = {}
        for name, (_, column) in SOURCES.items():
            elapsed = frames[name][column] - t0
            frame = frames[name].loc[(elapsed >= start) & (elapsed < end)].copy()
            frame = frame.sort_values(column).reset_index(drop=True)
            frame["elapsed_sec"] = frame[column] - t0
            frame["plot_sec"] = frame["elapsed_sec"] - start + offset
            frame["segment"] = number
            topics[name] = frame
        # Omit wholly empty segments from the common compressed axis.
        if any(not frame.empty for frame in topics.values()):
            segments.append(dict(number=number, start=start, end=end,
                                 offset=offset, topics=topics))
            offset += end - start
        else:
            print(f"Segment {number} ({start:g}-{end:g}s): no data; omitted")
    return frames, segments


def check_commands(segments):
    """Report all six command components; missing/single samples are inconclusive."""
    records = []
    for segment in segments:
        frame = segment["topics"]["cmd_vel"]
        record = {key: segment[key] for key in ("number", "start", "end")}
        record.update({f"{name}_samples": len(data)
                       for name, data in segment["topics"].items()})
        constant, valid = True, True
        for field in ("linear", "angular"):
            for component in ("x", "y", "z"):
                values = np.array([v[component] for v in frame[field]], dtype=float)
                key = f"{field}.{component}"
                finite = bool(len(values) and np.isfinite(values).all())
                span = float(np.ptp(values)) if finite else np.nan
                record[f"{key}_min"] = float(values.min()) if finite else np.nan
                record[f"{key}_max"] = float(values.max()) if finite else np.nan
                record[f"{key}_range"] = span
                valid &= finite
                constant &= finite and span <= CONSTANT_ATOL
        record["status"] = (
            "no_data" if frame.empty else "invalid" if not valid else
            "insufficient_samples" if len(frame) < 2 else
            "constant" if constant else "varying"
        )
        records.append(record)
    report = pd.DataFrame(records)
    report.to_csv(OUTPUT_DIR / "cmd_vel_constancy.csv", index=False)
    print(f"cmd_vel constancy: max-min <= {CONSTANT_ATOL:g} for all 6 components")
    print(report[["number", "start", "end", "cmd_vel_samples", "status"]].to_string(index=False))
    return report


def plot_segments(segments, topic, panels, filename, title):
    figure, axes = plt.subplots(len(panels), 1, figsize=(18, 9), sharex=True,
                                squeeze=False)
    axes = axes[:, 0]
    for ax, (ylabel, series) in zip(axes, panels):
        for segment in segments:
            frame = segment["topics"][topic]
            color = COLORS[(segment["number"] - 1) % len(COLORS)]
            for _, style, extract in series:
                values = [extract(row) for row in frame.to_dict("records")]
                # Separate plot calls prevent lines crossing a removed time gap.
                ax.plot(frame["plot_sec"], values, color=color, linestyle=style,
                        linewidth=1, marker="." if topic == "cmd_vel" else None,
                        markersize=2)
            ax.axvline(segment["offset"], color="0.65", linewidth=0.5, linestyle=":")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        ax.legend(handles=[Line2D([], [], color="black", linestyle=style, label=label)
                           for label, style, _ in series], loc="upper right")
    last = segments[-1]
    axes[-1].set_xlim(0, last["offset"] + last["end"] - last["start"])
    # A joined boundary represents two original times: the previous interval's
    # end and the next interval's start. Show both instead of implying continuity.
    tick_positions = [s["offset"] for s in segments]
    tick_labels = [f'{segments[0]["start"]:g}']
    for previous, current in zip(segments, segments[1:]):
        tick_labels.append(
            f'{current["start"]:g}' if previous["end"] == current["start"]
            else f'{previous["end"]:g} / {current["start"]:g}'
        )
    tick_positions.append(last["offset"] + last["end"] - last["start"])
    tick_labels.append(f'{last["end"]:g}')
    axes[-1].set_xticks(tick_positions, tick_labels, rotation=90, fontsize=8)
    axes[-1].set_xlabel(
        "Recording time (s); at joins: previous end / next start (gaps removed)"
    )
    top = axes[0].secondary_xaxis("top")
    top.set_xticks([s["offset"] + (s["end"] - s["start"]) / 2 for s in segments],
                  [str(s["number"]) for s in segments], fontsize=8)
    top.set_xlabel("Segment number")
    handles = [Line2D([], [], color=COLORS[(s["number"] - 1) % len(COLORS)], lw=3,
                       label=f'{s["number"]:02d}: {s["start"]:g}-{s["end"]:g} s')
               for s in segments]
    figure.suptitle(title)
    figure.legend(handles=handles, loc="lower center", ncol=6, fontsize=9,
                  title="Original recording intervals [start, end)")
    figure.tight_layout(rect=(0, 0.20, 1, 0.96))
    figure.savefig(OUTPUT_DIR / filename, dpi=200)
    return figure


def plot_full_recording(frame, segments, topic, panels, filename, title, time_end):
    """Draw every sample on the original time axis, marking only selected samples."""
    figure, axes = plt.subplots(len(panels), 1, figsize=(18, 9), sharex=True,
                                squeeze=False)
    records = frame.to_dict("records")
    timestamps = frame["elapsed_sec"].to_numpy()
    markers = ("o", "s", "^")
    for ax, (ylabel, series) in zip(axes[:, 0], panels):
        handles = []
        for index, (label, style, extract) in enumerate(series):
            values = np.array([extract(row) for row in records])
            marker = markers[index % len(markers)]
            ax.plot(timestamps, values, color=str(0.25 + index * 0.2),
                    linestyle=style, linewidth=0.8, alpha=0.8)
            for segment in segments:
                selected = (timestamps >= segment["start"]) & (timestamps < segment["end"])
                ax.plot(timestamps[selected], values[selected], linestyle="none",
                        marker=marker, markersize=3, markerfacecolor="none",
                        markeredgewidth=0.6, zorder=3,
                        color=COLORS[(segment["number"] - 1) % len(COLORS)])
            handles.append(Line2D([], [], color="0.3", linestyle=style,
                                  marker=marker, markerfacecolor="none", label=label))
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        ax.legend(handles=handles, loc="upper right")
    axes[-1, 0].set(xlim=(0, time_end), xlabel="Recording time (s)")
    handles = [Line2D([], [], linestyle="none", marker="o", markerfacecolor="none",
                      color=COLORS[(s["number"] - 1) % len(COLORS)],
                      label=f'{s["number"]:02d}: {s["start"]:g}-{s["end"]:g} s')
               for s in segments]
    figure.suptitle(title)
    figure.legend(handles=handles, loc="lower center", ncol=6, fontsize=9,
                  title="Markers: selected intervals [start, end); lines: full recording")
    figure.tight_layout(rect=(0, 0.20, 1, 0.96))
    figure.savefig(OUTPUT_DIR / filename, dpi=200)
    return figure


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames, segments = load_data()
    if not segments:
        raise ValueError("No data in the selected intervals")
    check_commands(segments)
    # Persist the selected records with segment IDs and both time axes.
    for topic in SOURCES:
        pd.concat([s["topics"][topic] for s in segments], ignore_index=True).to_parquet(
            OUTPUT_DIR / f"{topic}_segments.parquet", index=False)
    def plot_both(topic, panels, filename, title):
        plot_segments(segments, topic, panels, filename, f"{title} — selected intervals")
        plot_full_recording(
            frames[topic], segments, topic, panels, f"{Path(filename).stem}_full.png",
            f"{title} — full recording with selected samples",
            max(frame["elapsed_sec"].max() for frame in frames.values()),
        )

    plot_both("cmd_vel", [
        ("Linear X (m/s)", [("linear.x", "-", lambda r: r["linear"]["x"])]),
        ("Angular Z (rad/s)", [("angular.z", "-", lambda r: r["angular"]["z"])]),
    ], "cmd_vel.png", "cmd_vel")
    plot_both("pose", [
        (f"{field.title()} ({unit})", [
            (f"{field}.{component}", style,
             lambda r, f=field, c=component: r["twist"][f][c])
            for component, style in zip("xyz", ("-", "--", ":"))])
        for field, unit in (("linear", "m/s"), ("angular", "rad/s"))
    ], "pose.png", "Pose twist velocity")
    plot_both("motor", [
        (f"{axle} RPM", [(label, style, lambda r, w=wheel: r["message"]["wheels"][w]["rpm"])
                         for wheel, label, style in wheels])
        for axle, wheels in (
            ("Front", (("lf", "left front", "-"), ("rf", "right front", "--"))),
            ("Rear", (("lr", "left rear", "-"), ("rr", "right rear", "--"))),
        )
    ], "rpm.png", "Wheel RPM")
    print(f"Saved 6 figures, segmented data and command report to {OUTPUT_DIR}")
    plt.show()


if __name__ == "__main__":
    main()
