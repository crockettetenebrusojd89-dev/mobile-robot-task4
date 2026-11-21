#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/sim_env.sh"
cd "$TASK4_WS"

if [[ -n "${TASK4_WORLD:-}" ]]; then
  if [[ ! "$TASK4_WORLD" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    printf 'TASK4_WORLD 应为场景名，例如 task4_smoke。\n' >&2
    exit 2
  fi
  world_file="$TASK4_WS/worlds/$TASK4_WORLD.sdf"
  if [[ ! -r "$world_file" ]]; then
    printf '项目场景不存在：%s\n' "$world_file" >&2
    exit 2
  fi
fi

exec 9>"$TASK4_WS/results/.simulation.lock"
if ! flock -n 9; then
  printf '任务四仿真入口已在运行，请先在原终端停止。\n' >&2
  exit 1
fi
if [[ "${TASK4_USE_NVIDIA:-1}" == 1 ]] && command -v nvidia-smi >/dev/null 2>&1; then
  export __NV_PRIME_RENDER_OFFLOAD=1
  export __GLX_VENDOR_LIBRARY_NAME=nvidia
fi
if [[ -n "${TASK4_WORLD:-}" ]]; then
  spawn_args=()
  if [[ "$TASK4_WORLD" == task4_home ]]; then
    spawn_args=(x:=1.1 y:=3.0)
  fi
  exec ros2 launch "$TASK4_WS/launch/task4_sim.launch.py" world_file:="$world_file" \
    "${spawn_args[@]}" "$@"
fi
exec ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
  world:=maze model:=lite rviz:=false "$@"
