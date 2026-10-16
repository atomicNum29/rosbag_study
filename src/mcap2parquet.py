import rosbag2_py

from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

import cv2
from cv_bridge import CvBridge

date_code = "2026-10-15_1"
bag_path = f"rosbag_data/rosbag_{date_code}"


def save_to_parquet(data, filename):
    import pandas as pd

    df = pd.DataFrame(data)
    df.to_parquet(filename, engine="pyarrow", index=False)


def create_reader(bag_path) -> rosbag2_py.SequentialReader:
    reader = rosbag2_py.SequentialReader()

    storage_options = rosbag2_py.StorageOptions(uri=bag_path, storage_id="mcap")
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr", output_serialization_format="cdr"
    )

    reader.open(storage_options, converter_options)
    return reader


def main():
    reader = create_reader(bag_path)

    topics = reader.get_all_topics_and_types()

    for topic in topics:
        print(topic.name, topic.type, topic.serialization_format)

    gyro_data = []
    accel_data = []
    pose_data = []
    # image_data = []
    # motor_data = []

    bridge = CvBridge()

    while reader.has_next():
        topic, data, timestamp = reader.read_next()

        # if topic == "/motor_bridge_node/status":
        #     msg_type = get_message("std_msgs/msg/String")
        #     msg = deserialize_message(data, msg_type)
        #     motor_data.append(
        #         {
        #             "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
        #             "message": msg.data,
        #         }
        #     )

        # if topic == "/camera/fisheye1/image_raw":
        #     msg_type = get_message("sensor_msgs/msg/Image")
        #     msg = deserialize_message(data, msg_type)
        #     img = bridge.imgmsg_to_cv2(msg)
        #     image_data.append(
        #         {
        #             "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
        #             "sensor_time": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
        #             "image": img,
        #         }
        #     )
        #     continue
        if topic == "/camera/gyro/sample":
            msg_type = get_message("sensor_msgs/msg/Imu")
            msg = deserialize_message(data, msg_type)
            gyro_data.append(
                {
                    "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
                    "sensor_time": msg.header.stamp.sec
                    + msg.header.stamp.nanosec * 1e-9,
                    "angular_velocity": {
                        "x": msg.angular_velocity.x,
                        "y": msg.angular_velocity.y,
                        "z": msg.angular_velocity.z,
                    },
                }
            )
            continue
        if topic == "/camera/accel/sample":
            msg_type = get_message("sensor_msgs/msg/Imu")
            msg = deserialize_message(data, msg_type)
            accel_data.append(
                {
                    "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
                    "sensor_time": msg.header.stamp.sec
                    + msg.header.stamp.nanosec * 1e-9,
                    "linear_acceleration": {
                        "x": msg.linear_acceleration.x,
                        "y": msg.linear_acceleration.y,
                        "z": msg.linear_acceleration.z,
                    },
                }
            )
            continue
        if topic == "/camera/pose/sample":
            msg_type = get_message("nav_msgs/msg/Odometry")
            msg = deserialize_message(data, msg_type)
            pose_data.append(
                {
                    "timestamp": timestamp * 1e-9,  # Convert nanoseconds to seconds
                    "sensor_time": msg.header.stamp.sec
                    + msg.header.stamp.nanosec * 1e-9,
                    "pose": {
                        "position": {
                            "x": msg.pose.pose.position.x,
                            "y": msg.pose.pose.position.y,
                            "z": msg.pose.pose.position.z,
                        },
                        "orientation": {
                            "x": msg.pose.pose.orientation.x,
                            "y": msg.pose.pose.orientation.y,
                            "z": msg.pose.pose.orientation.z,
                            "w": msg.pose.pose.orientation.w,
                        },
                        "covariance": msg.pose.covariance,
                    },
                    "twist": {
                        "linear": {
                            "x": msg.twist.twist.linear.x,
                            "y": msg.twist.twist.linear.y,
                            "z": msg.twist.twist.linear.z,
                        },
                        "angular": {
                            "x": msg.twist.twist.angular.x,
                            "y": msg.twist.twist.angular.y,
                            "z": msg.twist.twist.angular.z,
                        },
                        "covariance": msg.twist.covariance,
                    },
                }
            )
            continue

    save_to_parquet(gyro_data, f"rosbag_data/gyro_data_{date_code}.parquet")
    save_to_parquet(accel_data, f"rosbag_data/accel_data_{date_code}.parquet")
    save_to_parquet(pose_data, f"rosbag_data/pose_data_{date_code}.parquet")
    # save_to_parquet(motor_data, f"rosbag_data/motor_data_{date_code}.parquet")


if __name__ == "__main__":
    main()
