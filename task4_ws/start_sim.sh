#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/sim_env.sh"
cd "$TASK4_WS"
exec 9>"$TASK4_WS/results/.simulation.lock"
if ! flock -n 9; then
  printf '任务四仿真入口已在运行，请先在原终端停止。\n' >&2
  exit 1
fi
if [[ "${TASK4_USE_NVIDIA:-1}" == 1 ]] && command -v nvidia-smi >/dev/null 2>&1; then
  export __NV_PRIME_RENDER_OFFLOAD=1
  export __GLX_VENDOR_LIBRARY_NAME=nvidia
fi
exec ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
  world:=maze model:=lite rviz:=false "$@"
