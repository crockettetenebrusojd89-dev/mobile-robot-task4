# 仿真场景

保存项目的 Gazebo 场景定义，SDF 文件描述机器人要进入的环境。

## 第一个项目场景

[task4_smoke.sdf](task4_smoke.sdf) 包含地面、灯光和一道墙。项目启动时由原有 TurtleBot4 入口生成机器人和充电座。在 `task4_ws` 目录执行：

```bash
TASK4_WORLD=task4_smoke bash start_sim.sh
```

Gazebo 的场景名为 `task4_smoke`，墙的模型名为 `check_wall`。想认识一个 SDF 参数，可以找到这面墙的 `<pose>2.5 0 0.6 0 0 0</pose>`。前 3 项是墙中心的 X、Y、Z 位置，单位为米。末 3 项为朝向，单位为弧度。本轮墙中心 X 为 2.5 m，厚度 0.14 m，雷达沿底盘前向量到墙面约 2.43 m。

直接执行 `bash start_sim.sh` 会继续打开原来的示例迷宫。项目场景通过验收后，将在 T2.2 放置三房间墙壁、门洞和家具。后续由用户键盘遥控，让 SLAM 从实际扫描生成 [课程地图](../maps/README.md)。

[RGB-D 测试方块](fixtures/rgbd_alignment_box.sdf) 是原创的 0.4 × 0.4 × 0.6 m 紫色静态方块。T1.3 将它临时放入 maze，用来比较彩色轮廓、深度轮廓和雷达距离。
