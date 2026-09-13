import matplotlib.pyplot as plt
import pandas as pd

# gyro_df = pd.read_parquet("gyro_data.parquet")
# gyro_x = gyro_df["angular_velocity"].apply(lambda x: x["x"])
# gyro_y = gyro_df["angular_velocity"].apply(lambda x: x["y"])
# gyro_z = gyro_df["angular_velocity"].apply(lambda x: x["z"])
# gyro_time = gyro_df["timestamp"]
# gyro_time = gyro_time - gyro_time[0]  # Normalize time to start from 0
# plt.figure(figsize=(12, 6))
# plt.plot(gyro_time, gyro_x, label="Gyro X", color="r")
# plt.plot(gyro_time, gyro_y, label="Gyro Y", color="g")
# plt.plot(gyro_time, gyro_z, label="Gyro Z", color="b")
# plt.title("Gyroscope Angular Velocity Over Time")
# plt.xlabel("Time (s)")
# plt.ylabel("Angular Velocity (rad/s)")
# plt.legend()
# plt.grid()
# plt.savefig("gyro_angular_velocity.png")

accel_df_2 = pd.read_parquet("imu_data/accel_data_2.parquet")
accel_df_3 = pd.read_parquet("imu_data/accel_data_3.parquet")

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

plt.figure(figsize=(12, 6))
plt.subplot(2, 1, 1)
plt.plot(accel_time_2, accel_x_2, label="Accel X", color="r")
plt.plot(accel_time_2, accel_y_2, label="Accel Y", color="g")
plt.plot(accel_time_2, accel_z_2, label="Accel Z", color="b")
plt.title("Accelerometer Linear Acceleration Over Time")
plt.xlabel("Time (s)")
plt.ylabel("Linear Acceleration (m/s²)")
plt.legend()
plt.grid()

plt.subplot(2, 1, 2)
plt.plot(accel_time_3, accel_x_3, label="Accel X", color="r")
plt.plot(accel_time_3, accel_y_3, label="Accel Y", color="g")
plt.plot(accel_time_3, accel_z_3, label="Accel Z", color="b")
plt.title("Accelerometer Linear Acceleration Over Time (Second Dataset)")
plt.xlabel("Time (s)")
plt.ylabel("Linear Acceleration (m/s²)")
plt.legend()
plt.grid()

plt.show()
plt.savefig("accel_linear_acceleration.png")