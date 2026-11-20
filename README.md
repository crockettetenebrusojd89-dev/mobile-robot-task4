# 综合设计大项目

本目录专门保存任务四“物体搜寻与计数机器人”的资料、代码、学习笔记和实验结果。

当前工作区是 [task4_ws](task4_ws/README.md)。从 [交接文档](task4_ws/docs/交接文档.md) 查看最新实测、复现入口和下一步，从 [学习进度](task4_ws/docs/学习进度.md) 接续课程。

```bash
cd task4_ws
source sim_env.sh
```

- task4_ws：当前开发和运行的 ROS 2 工作区。
- task4_ws/materials：教师原始资料与教程。
- task4_ws/docs：技术路线、学习笔记和验收要求。
- task4_ws/results：截图、采样报告、日志和迁移检查。
- migration_archive：迁移前的构建产物，保留作回退参考，已设 COLCON_IGNORE。

VS Code 可打开本目录的“综合设计大项目.code-workspace”。共享 ROS 安装及 TurtleBot4 底层依赖继续从系统和 /home/hao/turtlebot4_ws 读取。旧任务四路径保留兼容链接；新操作统一使用上面的工作区路径。
