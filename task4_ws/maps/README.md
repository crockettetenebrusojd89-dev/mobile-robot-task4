# 地图

当前使用用户在 `task4_home` 仿真中键盘驾驶生成的 194 × 159 格栅格，每格 0.05 m。[地图 YAML](task4_home_v1.yaml) 与 [PGM 图像](task4_home_v1.pgm) 已保存并通过独立 Nav2 map_server 加载。AMCL 和运动定位待 T2.4 验收，随后在 T2.5 用地图坐标命名客厅、厨房和卧室。 [来源、校验值与位姿清单](manifest.json)

## 教程里的地图来源

教师发的 `设计教程.zip` 包含三个 PDF。教程一第 17—18 页展示 TurtleBot3 示例环境的建图过程，第 31—32 页演示保存 `my_home_map`，第 32—35 页给出 `my_house.world` 的示例代码，第 37—38 页链接 AWS 小屋的现成仿真场景 `small_house.world`。压缩包和 PDF 附件均未随附可直接加载的地图文件。

教程链接的 AWS 小屋仓库在 `ros1` 和 `ros2` 分支均提供 `maps/turtlebot3_waffle_pi/map.pgm` 与 `map.yaml`。已核对地图为 500 × 500 格、每格 0.05 m、原点为 (−12.5, −12.5, 0)，与教程二第 6 页加载 `small_house_map.yaml` 的 RViz 截图信息和房屋轮廓吻合。教程三第 36 页沿用该 YAML 文件名。 [AWS 小屋场景](https://github.com/aws-robotics/aws-robomaker-small-house-world/blob/ros2/worlds/small_house.world) · [AWS 地图文件](https://github.com/aws-robotics/aws-robomaker-small-house-world/tree/ros2/maps/turtlebot3_waffle_pi)

本项目 T2.2 实测使用项目自建的 `task4_home.sdf`，其布局与 AWS 小屋不同。导航地图需与启动的场景对应，任务书也要求键盘遥控扫描并保存地图。TurtleBot4 自带的 `maze`、`depot`、`warehouse` 同样是与各自场景配套的示例。

`worlds/` 的 SDF 定义 Gazebo 里地面、墙和家具的位置。`maps/` 的地图来自机器人扫描，会保存哪些格子可通行、被占用或尚未观测。 [任务书要求](../docs/任务要求与验收.md) · [仿真场景](../worlds/README.md)

## 两套地图的实测对比

| 对比项 | AWS 小屋 | task4_home |
| --- | --- | --- |
| 栅格 | 仓库提供 500 × 500 格，每格 0.05 m | 对比时静止起点快照为 152 × 118 格，每格 0.05 m |
| 本地验证 | Nav2 地图服务器加载成功。修正临时副本里的鞋架惯量标签后，Fortress 实际列出 87 个模型 | TurtleBot4 Lite 与雷达已实测。对比时在正确的 ROS 域获取了起点地图 |
| 当前待办 | 若选 AWS 场景，需校验初始位姿、激光与地图重合，重新标定房间与目标 | 基础地图已生成并重载，待 AMCL 定位和房间标定 |

只为节省建图时间时，继续已经接通传感器的 `task4_home`。如果小组明确共用教程户型，可按 AWS 成套场景和配套地图进行机器人集成。课程的键盘建图步骤适用于两套场景。对比图和运行证据保存在本机 `results/m2_scene/2026-11-21_map_comparison.KAVQ5A/`。
