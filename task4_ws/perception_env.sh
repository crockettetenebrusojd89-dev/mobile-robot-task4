#!/usr/bin/env bash
# Source only in the terminal that runs perception.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '请执行 source perception_env.sh。\n' >&2
  exit 1
fi
task4_perception_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
task4_perception_site="$task4_perception_root/.venv/lib/python3.10/site-packages"
if [[ ! -d "$task4_perception_site" ]]; then
  printf '未找到感知虚拟环境，请先按 T3.1 交接文档安装。\n' >&2
  unset task4_perception_root task4_perception_site
  return 1
fi
if ! mkdir -p "$task4_perception_root/.venv/ultralytics" "$task4_perception_root/.venv/matplotlib"; then
  unset task4_perception_root task4_perception_site
  return 1
fi
export PYTHONPATH="$task4_perception_site${PYTHONPATH:+:$PYTHONPATH}"
export YOLO_CONFIG_DIR="$task4_perception_root/.venv/ultralytics"
export MPLCONFIGDIR="$task4_perception_root/.venv/matplotlib"
export YOLO_AUTOINSTALL=false
unset task4_perception_root task4_perception_site
