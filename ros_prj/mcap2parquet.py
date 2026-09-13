import rosbag2_py

from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

import cv2
from cv_bridge import CvBridge

bag_path = "/home/cu/rosbag_2026-09-12_2/"

reader = rosbag2_py.SequentialReader()

storage_options = rosbag2_py.StorageOptions(uri=bag_path, storage_id="mcap")
converter_options = rosbag2_py.ConverterOptions(
    input_serialization_format="cdr", output_serialization_format="cdr"
)

reader.open(storage_options, converter_options)

topics = reader.get_all_topics_and_types()

for topic in topics:
    print(topic.name, topic.type, topic.serialization_format)


gyro_data = []
accel_data = []
image_data = []

bridge = CvBridge()

while reader.has_next():
    topic, data, timestamp = reader.read_next()

    if topic == "/camera/fisheye1/image_raw":
        msg_type = get_message("sensor_msgs/msg/Image")
        msg = deserialize_message(data, msg_type)
        img = bridge.imgmsg_to_cv2(msg)
        image_data.append(
            {
                "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
                "sensor_time": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                "image": img,
            }
        )
        continue
    # if topic == "/camera/gyro/sample":
    #     msg_type = get_message("sensor_msgs/msg/Imu")
    #     msg = deserialize_message(data, msg_type)
    #     gyro_data.append(
    #         {
    #             "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
    #             "sensor_time": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
    #             "angular_velocity": {
    #                 "x": msg.angular_velocity.x,
    #                 "y": msg.angular_velocity.y,
    #                 "z": msg.angular_velocity.z,
    #             },
    #         }
    #     )
    #     continue
    # if topic == "/camera/accel/sample":
    #     msg_type = get_message("sensor_msgs/msg/Imu")
    #     msg = deserialize_message(data, msg_type)
    #     accel_data.append(
    #         {
    #             "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
    #             "sensor_time": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
    #             "linear_acceleration": {
    #                 "x": msg.linear_acceleration.x,
    #                 "y": msg.linear_acceleration.y,
    #                 "z": msg.linear_acceleration.z,
    #             },
    #         }
    #     )
    #     continue

import pandas as pd

# df = pd.DataFrame(gyro_data)
# df.to_parquet("gyro_data_2.parquet", engine="pyarrow", index=False)

# df = pd.DataFrame(accel_data)
# df.to_parquet("accel_data_2.parquet", engine="pyarrow", index=False)