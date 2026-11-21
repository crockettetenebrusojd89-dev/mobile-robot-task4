# 仿真场景

保存项目的 Gazebo 场景定义，SDF 文件描述机器人要进入的环境。

## 任务四三房间场景

在 `task4_ws` 启动 [task4_home.sdf](task4_home.sdf)。

```bash
TASK4_WORLD=task4_home bash start_sim.sh
```

场景外框为 8 × 6 m。西侧是客厅，东北是厨房，东南是卧室。客厅各有一处宽 1.20 m 的门洞通往另外两间房。仿真从客厅 `(x=1.1, y=3.0)` 附近启动，车头朝东，出坞后可绕到客厅东西向通道。

| 房间 | 家具 | 目标椅子 |
| --- | --- | ---: |
| 客厅 | 沙发 | 3 |
| 厨房 | 操作台、桌子 | 2 |
| 卧室 | 床、柜子 | 0 |

椅子用 [项目自制模型](../models/task4_chair/model.sdf)，待 T3.1 验证外观和识别效果。[场景真值](task4_home.truth.yaml) 记录 SDF 中每把椅子的模型原点。它使用 Gazebo 的 `world` 坐标，仅供离线评估。SLAM 根据机器人收到的激光和里程计生成自己的 `map` 坐标与 [栅格地图](../maps/README.md)。

仿真保持运行，在另一个终端进入 `task4_ws` 可复现采样与真值检查。

```bash
source sim_env.sh
mkdir -p results/m2_scene
out=$(mktemp -d results/m2_scene/t2_2_repro.XXXXXX)
ign model --list
SDF_PATH="$PWD/models" ign sdf -k worlds/task4_home.sdf
python3 scripts/capture_rgbd_frames.py --count 3 --with-lidar --out "$out/frames"
python3 scripts/check_scan_clock.py --out "$out"
python3 scripts/extract_world_truth.py worlds/task4_home.sdf --out "$out/truth.yaml"
cmp worlds/task4_home.truth.yaml "$out/truth.yaml"
```

目标名称使用 `chair_`、`bottle_` 或 `cup_` 前缀。提取器接受世界顶层目标中直接给出的六项米/弧度位姿。用新输出路径运行，以保留已有结果。 [键盘建图交接](../docs/交接文档.md#t23-键盘建图)

## 第一个项目场景

[task4_smoke.sdf](task4_smoke.sdf) 包含地面、灯光和一道墙。项目启动时由原有 TurtleBot4 入口生成机器人和充电座。在 `task4_ws` 目录执行：

```bash
TASK4_WORLD=task4_smoke bash start_sim.sh
```

Gazebo 的场景名为 `task4_smoke`，墙的模型名为 `check_wall`。想认识一个 SDF 参数，可以找到这面墙的 `<pose>2.5 0 0.6 0 0 0</pose>`。前 3 项是墙中心的 X、Y、Z 位置，单位为米。末 3 项为朝向，单位为弧度。本轮墙中心 X 为 2.5 m，厚度 0.14 m，雷达沿底盘前向量到墙面约 2.43 m。

直接执行 `bash start_sim.sh` 会打开原来的示例迷宫。

[RGB-D 测试方块](fixtures/rgbd_alignment_box.sdf) 是原创的 0.4 × 0.4 × 0.6 m 紫色静态方块。T1.3 将它临时放入 maze，用来比较彩色轮廓、深度轮廓和雷达距离。
