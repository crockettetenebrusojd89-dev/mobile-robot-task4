#!/usr/bin/env bash
# 使用 source env.sh 将本工作区加入当前终端。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '请执行 source env.sh，使环境设置保留在当前终端。\n' >&2
  exit 1
fi
export TASK4_WS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -r /opt/ros/humble/setup.bash ]]; then
  printf '未找到 /opt/ros/humble/setup.bash，请先核实 ROS 2 环境。\n' >&2
  return 1
fi
source /opt/ros/humble/setup.bash || return 1
export ROS_LOG_DIR="$TASK4_WS/results/ros_logs"
mkdir -p "$ROS_LOG_DIR" || return 1
if [[ -r "$TASK4_WS/install/local_setup.bash" ]]; then
  source "$TASK4_WS/install/local_setup.bash" || return 1
fi
