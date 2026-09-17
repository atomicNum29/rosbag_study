import matplotlib.pyplot as plt
import pandas as pd
import json


def plot_accel_and_gyro():
    accel_df_2 = pd.read_parquet("rosbag_data/accel_data_2.parquet")
    accel_df_3 = pd.read_parquet("rosbag_data/accel_data_3.parquet")
    gyro_df_2 = pd.read_parquet("rosbag_data/gyro_data_2.parquet")
    gyro_df_3 = pd.read_parquet("rosbag_data/gyro_data_3.parquet")

    accel_x_2 = accel_df_2["linear_acceleration"].apply(lambda x: x["x"])
    accel_y_2 = accel_df_2["linear_acceleration"].apply(lambda x: x["y"])
    accel_z_2 = accel_df_2["linear_acceleration"].apply(lambda x: x["z"])
    accel_time_2 = accel_df_2["timestamp"]
    accel_time_2 = accel_time_2 - accel_time_2[0]  # Normalize time to start from 0

    accel_x_3 = accel_df_3["linear_acceleration"].apply(lambda x: x["x"])
    accel_y_3 = accel_df_3["linear_acceleration"].apply(lambda x: x["y"])
    accel_z_3 = accel_df_3["linear_acceleration"].apply(lambda x: x["z"])
    accel_time_3 = accel_df_3["timestamp"]
    accel_time_3 = accel_time_3 - accel_time_3[0]

    gyro_x_2 = gyro_df_2["angular_velocity"].apply(lambda x: x["x"])
    gyro_y_2 = gyro_df_2["angular_velocity"].apply(lambda x: x["y"])
    gyro_z_2 = gyro_df_2["angular_velocity"].apply(lambda x: x["z"])
    gyro_time_2 = gyro_df_2["timestamp"]
    gyro_time_2 = gyro_time_2 - gyro_time_2[0]

    gyro_x_3 = gyro_df_3["angular_velocity"].apply(lambda x: x["x"])
    gyro_y_3 = gyro_df_3["angular_velocity"].apply(lambda x: x["y"])
    gyro_z_3 = gyro_df_3["angular_velocity"].apply(lambda x: x["z"])
    gyro_time_3 = gyro_df_3["timestamp"]
    gyro_time_3 = gyro_time_3 - gyro_time_3[0]

    gyro_y_2_diff = gyro_y_2.diff().fillna(0)
    gyro_y_3_diff = gyro_y_3.diff().fillna(0)
    accel_y_2_diff = accel_y_2.diff().fillna(0)
    accel_y_3_diff = accel_y_3.diff().fillna(0)

    # plt.figure(figsize=(12, 6))
    # plt.subplot(2, 1, 1)
    # plt.plot(accel_time_2, accel_x_2, label="Accel X", color="r")
    # plt.plot(accel_time_2, accel_y_2, label="Accel Y", color="g")
    # plt.plot(accel_time_2, accel_z_2, label="Accel Z", color="b")
    # plt.title("Accelerometer Linear Acceleration Over Time")
    # plt.xlabel("Time (s)")
    # plt.ylabel("Linear Acceleration (m/s²)")
    # plt.legend()
    # plt.grid()

    # plt.subplot(2, 1, 2)
    # plt.plot(accel_time_3, accel_x_3, label="Accel X", color="r")
    # plt.plot(accel_time_3, accel_y_3, label="Accel Y", color="g")
    # plt.plot(accel_time_3, accel_z_3, label="Accel Z", color="b")
    # plt.title("Accelerometer Linear Acceleration Over Time (Second Dataset)")
    # plt.xlabel("Time (s)")
    # plt.ylabel("Linear Acceleration (m/s²)")
    # plt.legend()
    # plt.grid()

    # plt.figure(figsize=(12, 6))
    # plt.plot(accel_time_2, accel_y_2, label="Accel Y (Dataset 2)", color="g", alpha=0.5)
    # plt.plot(accel_time_3, accel_y_3, label="Accel Y (Dataset 3)", color="b", alpha=0.5)
    # plt.title("Accelerometer Linear Acceleration Y-Axis Over Time")
    # plt.xlabel("Time (s)")
    # plt.ylabel("Linear Acceleration (m/s²)")
    # plt.legend()
    # plt.grid()

    # plt.figure(figsize=(12, 6))
    # plt.plot(accel_time_2, accel_y_2_diff, label="Accel Y (Dataset 2)", color="g", alpha=0.5)
    # plt.plot(accel_time_3, accel_y_3_diff, label="Accel Y (Dataset 3)", color="b", alpha=0.5)
    # plt.title("Accelerometer Linear Acceleration Y-Axis Over Time")
    # plt.xlabel("Time (s)")
    # plt.ylabel("Linear Acceleration (m/s²)")
    # plt.legend()
    # plt.grid()

    # plt.figure(figsize=(12, 6))
    # plt.plot(gyro_time_2, gyro_y_2, label="Gyro Y (Dataset 2)", color="g", alpha=0.5)
    # plt.plot(gyro_time_3, gyro_y_3, label="Gyro Y (Dataset 3)", color="b", alpha=0.5)
    # plt.title("Gyroscope Angular Velocity Y-Axis Over Time")
    # plt.xlabel("Time (s)")
    # plt.ylabel("Angular Velocity (rad/s)")
    # plt.legend()
    # plt.grid()

    # plt.figure(figsize=(12, 6))
    # plt.plot(gyro_time_2, gyro_y_2_diff, label="Gyro Y (Dataset 2)", color="g", alpha=0.5)
    # plt.plot(gyro_time_3, gyro_y_3_diff, label="Gyro Y (Dataset 3)", color="b", alpha=0.5)
    # plt.title("Gyroscope Angular Velocity Y-Axis Over Time")
    # plt.xlabel("Time (s)")
    # plt.ylabel("Angular Velocity (rad/s)")
    # plt.legend()
    # plt.grid()

    plt.show()


motor_data_df = pd.read_parquet("rosbag_data/motor_data.parquet")

motor_data = []

for index, row in motor_data_df.iterrows():
    msg = json.loads(row["message"])
    # print(msg)
    # exit(0)
    motor_data.append(
        {
            "timestamp": row["timestamp"],
            "state": msg.get("state", None),
            "seq": msg.get("seq", None),
            "system_error": msg.get("system_error", None),
            "validity": msg.get("validity", None),
            "lf_state": msg.get("wheels", {}).get("lf", {}).get("status", None),
            "rf_state": msg.get("wheels", {}).get("rf", {}).get("status", None),
            "lr_state": msg.get("wheels", {}).get("lr", {}).get("status", None),
            "rr_state": msg.get("wheels", {}).get("rr", {}).get("status", None),
        }
    )

t0 = motor_data[0]["timestamp"]
t = [motor["timestamp"] - t0 for motor in motor_data]
seq = [motor["seq"] for motor in motor_data]
seq_diff = [seq[i] - seq[i - 1] if seq[i] != 0 else 256 - seq[i - 1] for i in range(1, len(seq))]

plt.figure(figsize=(12, 6))
plt.subplot(3, 1, 1)
plt.plot(t, [motor["state"] for motor in motor_data], label="Motor State", color="b")
plt.title("State Over Time")
plt.xlabel("Time (s)")
plt.ylabel("State")
plt.legend()
plt.grid()

plt.subplot(3, 1, 2)
plt.plot(t, [motor["system_error"] for motor in motor_data], label="Motor System Error", color="r")
plt.title("System Error Over Time")
plt.xlabel("Time (s)")
plt.ylabel("System Error")
plt.legend()
plt.grid()

plt.subplot(3, 1, 3)
plt.plot(t, [motor["validity"] for motor in motor_data], label="Motor Validity", color="g")
plt.title("Validity Over Time")
plt.xlabel("Time (s)")
plt.ylabel("Validity")
plt.legend()
plt.grid()

plt.tight_layout()

plt.figure(figsize=(12, 6))
plt.subplot(4, 1, 1)
plt.plot(t, [motor["lf_state"] for motor in motor_data], label="LF State", color="b")
plt.title("Left Front Wheel State Over Time")
plt.xlabel("Time (s)")
plt.ylabel("LF State")
plt.legend()
plt.grid()

plt.subplot(4, 1, 2)
plt.plot(t, [motor["rf_state"] for motor in motor_data], label="RF State", color="r")
plt.title("Right Front Wheel State Over Time")
plt.xlabel("Time (s)")
plt.ylabel("RF State")
plt.legend()
plt.grid()

plt.subplot(4, 1, 3)
plt.plot(t, [motor["lr_state"] for motor in motor_data], label="LR State", color="g")
plt.title("Left Rear Wheel State Over Time")
plt.xlabel("Time (s)")
plt.ylabel("LR State")
plt.legend()
plt.grid()

plt.subplot(4, 1, 4)
plt.plot(t, [motor["rr_state"] for motor in motor_data], label="RR State", color="m")
plt.title("Right Rear Wheel State Over Time")
plt.xlabel("Time (s)")
plt.ylabel("RR State")
plt.legend()
plt.grid()

plt.tight_layout()

plt.figure(figsize=(12, 6))
plt.plot(t[1:], seq_diff, label="Sequence Number Difference", color="c")
plt.title("Sequence Number Difference Over Time")
plt.xlabel("Time (s)")
plt.ylabel("Sequence Number Difference")
plt.legend()
plt.grid()

plt.show()
