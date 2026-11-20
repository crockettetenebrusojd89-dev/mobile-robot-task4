#!/usr/bin/env bash
# 每个任务四仿真终端均执行 source sim_env.sh。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '请执行 source sim_env.sh。\n' >&2
  exit 1
fi
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh" || return 1
TASK4_TURTLEBOT_SETUP="${TASK4_TURTLEBOT_SETUP:-/home/hao/turtlebot4_ws/install/setup.bash}"
if [[ ! -r "$TASK4_TURTLEBOT_SETUP" ]]; then
  printf '未找到 TurtleBot4 环境：%s\n' "$TASK4_TURTLEBOT_SETUP" >&2
  return 1
fi
source "$TASK4_TURTLEBOT_SETUP" || return 1
python3 "$TASK4_WS/scripts/prepare_sim_overlay.py" || return 1
export AMENT_PREFIX_PATH="$TASK4_WS/.compat${AMENT_PREFIX_PATH:+:$AMENT_PREFIX_PATH}"
# 这些设置只影响当前终端及其子进程，将课程仿真与实物发现配置区分开。
unset ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
unset RMW_FASTRTPS_USE_QOS_FROM_XML ROS_SUPER_CLIENT IGN_IP
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID="${TASK4_ROS_DOMAIN_ID:-44}"
export ROS_LOCALHOST_ONLY=1
export IGN_PARTITION="${TASK4_IGN_PARTITION:-task4_hao}"
if [[ -r "$TASK4_WS/install/local_setup.bash" ]]; then
  source "$TASK4_WS/install/local_setup.bash" || return 1
fi
