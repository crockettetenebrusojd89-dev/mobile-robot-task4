# 项目任务与 Skill 说明

2026-11-10 核对。项目任务是《自主移动机器人导论》综合设计任务四：**物体搜寻与计数机器人**。要求来源与待核实事项见 [任务要求与验收](任务要求与验收.md)，技术实现顺序以 [技术路线](技术路线.md) 为准。

## 最终要完成什么

1. 用键盘操作机器人扫描环境，构建、保存地图，并为客厅、厨房、卧室命名。
2. 从语音中识别房间和物品，解析并发送任务信息。
3. 自主导航到指定房间，执行旋转或多个观察点的搜索。
4. 识别目标，记录地图坐标，为每件物品编号并标注；重复看见同一物品时不重复计数。
5. 遍历搜索后打印总数，保存带编号的结果地图；导航失败、感知缺失、取消和搜索未完成有明确结果。
6. 以实际实验准备展示 PPT 和电子报告，明确三人分工与个人贡献。

其中去重、失败状态和证据保存是支撑正确完成任务的工程设计，具体教师原文与工程建议在要求文档中分别列出。语音输出播报可另作扩展，当前明确要求的是语音输入、打印总数和地图保存。

任务书与现有平台存在 TurtleBot2 / TurtleBot3 / TurtleBot4 型号差异；当前使用 TurtleBot4 Lite/Fortress 做开发验证，最终课程认可仍须核实。首版不加入扫地、自动回充或开放世界通用搜寻。

## 现在完成到哪里

本次核对时 M0 已完成，M1 部分传感器数据与用户复现有证据；雷达安装 TF、独立仿真时间、运动变化和图像几何对齐等尚未全部验收。建图导航、检测定位、去重计数和完整语音任务尚未验收。最新状态始终读取 [PROJECT_STATUS.md](../PROJECT_STATUS.md)，本页不是持续更新的状态副本。

当前学习仍接续 [学习进度](学习进度.md) 中的角度与雷达平面坐标；新增 skill 不改变用户已跳过或待反馈的练习状态。

## 项目内新增的 skill

入口：[task4-delivery/SKILL.md](../.agents/skills/task4-delivery/SKILL.md)。项目总目录和工作区两份 AGENTS.md 均已加入显式读取入口，不依赖启动位置恰好自动发现嵌套技能目录。没有向全局技能目录安装文件。

| 内容 | 作用 |
| --- | --- |
| SKILL.md | 读取项目状态、选择本轮任务、增量实现、验证和维护工作记录 |
| references/milestones.md | M0—M6 的依赖、交付物、通过证据和代表性失败场景 |
| references/ros2-integration.md | 项目环境、QoS、时间、TF、SLAM 保存、Nav2 状态与排错 |
| references/counting-and-results.md | 深度定位、跨视角去重、一对一关联、搜索结束与地图保存 |
| references/github-sources.md、sources.json | GitHub 借鉴取舍、固定提交、原始参考文件的校验值与许可证范围 |
| agents/openai.yaml | skill 的名称、简介和默认调用提示 |

可以直接提出任务，例如：

```text
使用 $task4-delivery，根据项目状态安排下一项传感器检查，并解释相关代码。
使用 $task4-delivery，调试话题可发现但订阅没有消息的问题。
使用 $task4-delivery，实现静态物体的跨视角去重，验证重访与相邻目标。
使用 $task4-delivery，按当前阶段检查完整任务还缺哪些验收证据。
```

如果当前界面尚未列出新 skill，直接要求“读取 task4_ws/.agents/skills/task4-delivery/SKILL.md 并按它执行”即可使用文件中的流程。

## GitHub 借鉴范围

已阅读 Superpowers 的完成验证/根因排查 skill、robotics-agent-skills 的 ROS 2/感知/测试 skill，以及 Nav2、SLAM Toolbox 和 yolo_ros 的相关源码或说明。选择依据是与当前问题直接相关、有实际流程或代码可核查，Nav2/SLAM 优先对应 Humble。

详细链接、版本和取舍见 [GitHub 来源与取舍](../.agents/skills/task4-delivery/references/github-sources.md)。这些资料被整理为本项目的中文流程，没有运行上游安装脚本、安装检测器或替换机器人配置。本次验证范围是 skill 与文档结构，不是机器人功能通过。
