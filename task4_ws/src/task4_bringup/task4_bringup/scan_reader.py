"""First learning node: subscribe to scans and log sensor-frame return statistics."""

import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

from task4_bringup.scan_math import summarize_scan


class ScanReader(Node):
    def __init__(self):
        super().__init__("task4_scan_reader")
        self.report_interval_sec = 1.0
        self.last_report_time = -float("inf")
        # LaserScan 是消息类型；on_scan 是收到消息后自动调用的函数。
        self.scan_subscription = self.create_subscription(
            LaserScan, "/scan", self.on_scan, qos_profile_sensor_data
        )
        self.get_logger().info(
            "等待 /scan；每秒最多处理并显示一条扫描。保持项目仿真运行，Ctrl+C 结束。"
        )

    def on_scan(self, msg):
        now = time.monotonic()
        if now - self.last_report_time < self.report_interval_sec:
            return
        self.last_report_time = now
        if not msg.header.frame_id.strip():
            self.get_logger().warning("忽略本帧：frame_id 为空，不能解释回波坐标。")
            return
        try:
            summary = summarize_scan(
                msg.ranges, msg.angle_min, msg.angle_increment,
                msg.range_min, msg.range_max,
            )
        except ValueError as error:
            self.get_logger().warning(f"忽略本帧：{error}")
            return

        stamp = msg.header.stamp
        text = (
            f"SCAN_DATA frame={msg.header.frame_id} "
            f"t={stamp.sec}.{stamp.nanosec:09d}\n"
            f"  总样本={summary['sample_count']} "
            f"有效={summary['valid_count']} 无效={summary['invalid_count']}\n"
        )
        nearest = summary["nearest"]
        if nearest is None:
            text += "  本帧没有有效距离，最近回波未定义。"
        else:
            text += (
                f"  最近有效回波={nearest['distance_m']:.3f} m "
                f"序号={nearest['index']} 雷达角度={nearest['angle_deg']:.1f}°\n"
                f"  雷达平面坐标=({nearest['x_m']:.3f}, {nearest['y_m']:.3f}) m"
            )
        self.get_logger().info(text)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ScanReader()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    main()
