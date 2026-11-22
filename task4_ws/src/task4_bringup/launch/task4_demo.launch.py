"""Start Task 4 perception and search after simulation and Nav2 are ready."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params = LaunchConfiguration("params_file")
    return LaunchDescription([
        DeclareLaunchArgument(
            "params_file",
            default_value=PathJoinSubstitution([FindPackageShare("task4_bringup"), "config", "task4_params.yaml"]),
        ),
        Node(package="task4_bringup", executable="object_locator", parameters=[params], output="screen"),
        Node(package="task4_bringup", executable="search_manager", parameters=[params], output="screen"),
    ])
