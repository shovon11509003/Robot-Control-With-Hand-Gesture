#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class CmdVelBridge(Node):
    def __init__(self):
        super().__init__("cmdvel_bridge")
        self.pub = self.create_publisher(Twist, "/turtle1/cmd_vel", 10)
        self.sub = self.create_subscription(Twist, "/cmd_vel", self.cb, 10)
        self.get_logger().info("Bridging /cmd_vel -> /turtle1/cmd_vel")

    def cb(self, msg: Twist):
        self.pub.publish(msg)

def main():
    rclpy.init()
    node = CmdVelBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()