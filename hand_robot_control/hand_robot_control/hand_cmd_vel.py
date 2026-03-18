#!/usr/bin/env python3
import rclpy
import csv
import os
from rclpy.node import Node
from geometry_msgs.msg import Twist
import socket
import time

class UdpToCmdVel(Node):
    def __init__(self):
        super().__init__('udp_to_cmd_vel')

        self.log_path = os.path.expanduser("~/latency_log.csv")
        self.csv_file = open(self.log_path, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["recv_time", "cmd", "speed", "latency_ms"])
        self.get_logger().info(f"Logging to {self.log_path}")

        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # UDP server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 5005))
        self.sock.setblocking(False)

        # Speeds
        self.lin = 2.0 #1.5 #0.25
        self.ang = 3.0 #2.5 #0.8

        # Store last command
        self.current_cmd = "STOP"
        self.current_speed = 0.0

        #latencies
        self.latencies = []
        self.last_report_time = time.time()

        # Timer 10 Hz publishing
        self.timer = self.create_timer(0.05, self.publish_loop)

        # Separate timer for reading UDP (fast)
        self.create_timer(0.01, self.udp_loop)

        self.get_logger().info("UDP->/cmd_vel running at 10 Hz")

    def udp_loop(self):
        try:
            data, addr = self.sock.recvfrom(1024)
            msg_str = data.decode("utf-8", errors="ignore").strip()
            parts = msg_str.split(",")

            # First part = command
            self.current_cmd = parts[0].upper()

            # Second part = speed (if exists)
            if len(parts) > 1:
                try:
                    self.current_speed = float(parts[1])
                except:
                    self.current_speed = 0.0
            else:
                self.current_speed = 0.0

            # Latency calculation
            if len(parts) > 2:
                try:
                    sent_time = float(parts[2])
                    receive_time = time.time()
                    latency = abs(receive_time - sent_time)
                    self.latencies.append(latency)

                    # log to CSV
                    self.csv_writer.writerow([
                        receive_time,
                        self.current_cmd,
                        self.current_speed,
                        latency*1000.0

                    ])
                    self.csv_file.flush()
                    
                except:
                    pass
            # cmd = data.decode("utf-8", errors="ignore").strip().upper()
            # self.current_cmd = cmd
        except BlockingIOError:
            pass

    def publish_loop(self):
        msg = Twist()

        if self.current_cmd == "FORWARD":
            msg.linear.x = self.lin * self.current_speed

        elif self.current_cmd == "BACKWARD":
            msg.linear.x = -self.lin * self.current_speed

        elif self.current_cmd == "LEFT":
            msg.linear.x = self.lin* self.current_speed
            msg.angular.z = self.ang* self.current_speed

        elif self.current_cmd == "RIGHT":
            msg.linear.x = self.lin* self.current_speed
            msg.angular.z = -self.ang* self.current_speed
        else:
            msg.linear.x = 0.0
            msg.angular.z = 0.0

        # STOP = zero twist automatically

        current_time = time.time()
        if current_time - self.last_report_time > 5.0 and self.latencies:
            avg = sum(self.latencies)/len(self.latencies)
            min_l = min(self.latencies)
            max_l = max(self.latencies)

            self.get_logger().info(
                f"Latency avg = {avg*1000:.2f}ms "
                f"min = {min_l*1000:.2f}ms "
                f"max = {max_l*1000:.2f}ms "
                f"samples = {len(self.latencies)}"
            )

            self.latencies.clear()
            self.last_report_time = current_time

        self.pub.publish(msg)

def main():
    rclpy.init()
    node = UdpToCmdVel()
    rclpy.spin(node)
    node.csv_file.close()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()