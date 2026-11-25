#!/usr/bin/env python3
"""
INFYNEX Full Simulation Launch File
Brings up:
1. ros_gz_bridge (bridging clock and camera topics with bridge_config.yaml)
2. flight_state_publisher (NED to ENU odometry & battery state)
3. waypoint_controller (W1-W9 trajectory control + manual override listener)
4. stream_gateway (frame timestamping and optical streaming)
Enforces use_sim_time:=True across all nodes.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    bridge_config = '/workspace/simulation/gazebo/bridge_config.yaml'
    mission_scenario = '/workspace/simulation/scenarios/mission_facade_scan.yaml'

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )

    # 1. ROS-Gazebo Bridge Node
    bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{
            'use_sim_time': True,
            'config_file': bridge_config
        }],
        output='screen'
    )

    # 2. Flight State Publisher Node (NED to ENU transform)
    flight_state_node = Node(
        package='infynex_mission',
        executable='flight_state_publisher.py',
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # 3. Waypoint Controller Node (W1-W9 circumferential inspection)
    waypoint_node = Node(
        package='infynex_mission',
        executable='waypoint_controller.py',
        parameters=[{
            'use_sim_time': True,
            'mission_file': mission_scenario
        }],
        output='screen'
    )

    # 4. Stream Gateway Node (Camera streaming over infynex_5g_ran)
    stream_gateway_node = Node(
        package='infynex_camera',
        executable='stream_gateway.py',
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    return LaunchDescription([
        use_sim_time_arg,
        bridge_node,
        flight_state_node,
        waypoint_node,
        stream_gateway_node
    ])
