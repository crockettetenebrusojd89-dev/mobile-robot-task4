"""Run a project SDF with the installed TurtleBot4 Fortress spawn stack."""

import os
from pathlib import Path
import shlex
from xml.etree import ElementTree

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.actions import SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def simulation(context):
    world = Path(LaunchConfiguration("world_file").perform(context))
    if not world.is_absolute() or world.suffix != ".sdf" or not world.is_file():
        raise ValueError(f"world_file must point to an existing absolute SDF path: {world}")
    worlds = ElementTree.parse(world).getroot().findall("world")
    if len(worlds) != 1 or not worlds[0].get("name"):
        raise ValueError(f"Expected one named world in {world}")
    world_name = worlds[0].attrib["name"]

    project = Path(__file__).resolve().parents[1]
    turtlebot_share = Path(get_package_share_directory("turtlebot4_ignition_bringup"))
    create_share = Path(get_package_share_directory("irobot_create_ignition_bringup"))
    gazebo_share = Path(get_package_share_directory("ros_gz_sim"))
    model = LaunchConfiguration("model").perform(context)
    resources = [
        str(project / "worlds"),
        str(project / "models"),
        str(world.parent),
        str(turtlebot_share / "worlds"),
        str(create_share / "worlds"),
        str(Path(get_package_share_directory("turtlebot4_description")).parent.resolve()),
        str(Path(get_package_share_directory("irobot_create_description")).parent.resolve()),
    ]
    gui_plugins = [
        str(Path(get_package_share_directory(package)) / "lib")
        for package in ("turtlebot4_ignition_gui_plugins", "irobot_create_ignition_plugins")
    ]
    existing_resources = os.environ.get("IGN_GAZEBO_RESOURCE_PATH", "").split(os.pathsep)
    resource_path = os.pathsep.join(dict.fromkeys(filter(None, resources + existing_resources)))
    gui_plugin_path = os.pathsep.join(filter(None, [
        *gui_plugins, os.environ.get("IGN_GUI_PLUGIN_PATH", ""),
    ]))

    gui_config = turtlebot_share / "gui" / model / "gui.config"
    gazebo_args = shlex.join(["-r", "-v", "4", "--gui-config", str(gui_config), str(world)])
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(gazebo_share / "launch" / "gz_sim.launch.py")),
        launch_arguments={"gz_args": gazebo_args, "gz_version": "6",
                          "on_exit_shutdown": "true"}.items(),
    )
    clock_bridge = Node(
        package="ros_gz_bridge", executable="parameter_bridge", name="clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock"], output="screen",
    )
    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(turtlebot_share / "launch" / "turtlebot4_spawn.launch.py")),
        # The nested sensor bridge uses /world/<name>/... even when Gazebo can spawn by discovery.
        launch_arguments={**{
            name: LaunchConfiguration(name)
            for name in ("model", "namespace", "rviz", "x", "y", "z", "yaw")
        }, "world": world_name}.items(),
    )

    # Keep the environment upstream's Fortress launcher normally sets, with project paths first.
    return [
        SetEnvironmentVariable("IGN_GAZEBO_RESOURCE_PATH", resource_path),
        SetEnvironmentVariable("IGN_GUI_PLUGIN_PATH", gui_plugin_path),
        gazebo, clock_bridge, spawn,
    ]


def generate_launch_description():
    arguments = [
        DeclareLaunchArgument("world_file", description="Absolute path to the project world SDF"),
        DeclareLaunchArgument("model", default_value="lite", choices=["lite", "standard"]),
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("rviz", default_value="false", choices=["true", "false"]),
        *[DeclareLaunchArgument(name, default_value="0.0") for name in ("x", "y", "z", "yaw")],
    ]
    return LaunchDescription([*arguments, OpaqueFunction(function=simulation)])
