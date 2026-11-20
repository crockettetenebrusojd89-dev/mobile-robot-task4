# GitHub 来源与取舍

查阅日期：2026-11-10（Asia/Shanghai）。本 skill 是结合项目要求重新编写的中文工作流程；没有复制第三方 skill 全文、运行安装脚本、引入源码/模型或修改全局技能配置。

选取依据：能直接支撑项目当前或后续问题；有可检查的 skill、源码或配置；与本项目版本匹配。社区关注度仅作辅助，不代替兼容性和实测。本次实际阅读了 5 份上游 SKILL.md，以及下列工程参考。

精确提交、参考文件 URL 和收到正文的 SHA-256 见 [sources.json](sources.json)。哈希只用于识别本次阅读的正文，不表示本机已安装相同版本，也不表示已验收其功能。

## 已采用的参考

| 上游与固定版本 | 已阅读的位置 | 借鉴到本项目的内容 |
| --- | --- | --- |
| [obra/superpowers](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7)，main `22f0b463` | [verification-before-completion](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/verification-before-completion/SKILL.md)、[systematic-debugging](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/SKILL.md) | 完成结论与实际检查对应；从失败边界复现、比对并验证单一假设。用于 skill 主流程和 ROS 排错表 |
| [arpitg1304/robotics-agent-skills](https://github.com/arpitg1304/robotics-agent-skills/tree/f9bc5467ff9ee3d23f1a1b0b29a649843bb6ad11)，main `f9bc5467` | [ros2](https://github.com/arpitg1304/robotics-agent-skills/blob/f9bc5467ff9ee3d23f1a1b0b29a649843bb6ad11/skills/ros2/SKILL.md)、[robot-perception](https://github.com/arpitg1304/robotics-agent-skills/blob/f9bc5467ff9ee3d23f1a1b0b29a649843bb6ad11/skills/robot-perception/SKILL.md)、[robotics-testing](https://github.com/arpitg1304/robotics-agent-skills/blob/f9bc5467ff9ee3d23f1a1b0b29a649843bb6ad11/skills/robotics-testing/SKILL.md) | QoS 与回调边界、有界队列与采集时间、纯算法/ROS 集成/仿真分层验证；按本项目规模精简 |
| [ros-navigation/navigation2](https://github.com/ros-navigation/navigation2/tree/3c3db59d6969d8ecee8e68468693d006397f4a0c)，humble `3c3db59d` | [Simple Commander](https://github.com/ros-navigation/navigation2/blob/3c3db59d6969d8ecee8e68468693d006397f4a0c/nav2_simple_commander/nav2_simple_commander/robot_navigator.py)、[默认参数](https://github.com/ros-navigation/navigation2/blob/3c3db59d6969d8ecee8e68468693d006397f4a0c/nav2_bringup/params/nav2_params.yaml) | 目标接受、最终状态、取消和 lifecycle；上游 NavFn 的 `use_astar: false` 需要与项目拟用 A* 区分 |
| [SteveMacenski/slam_toolbox](https://github.com/SteveMacenski/slam_toolbox/tree/dccc5d1fd2b5007098f4050e681d20da37ef183f)，humble `dccc5d1f` | [README 的 TF、地图保存和序列化说明](https://github.com/SteveMacenski/slam_toolbox/blob/dccc5d1fd2b5007098f4050e681d20da37ef183f/README.md) | 建图依赖与观测时间；用于 AMCL 的图像/YAML 和用于继续建图的 pose graph 分开验收 |
| [mgonzs13/yolo_ros](https://github.com/mgonzs13/yolo_ros)，main `94d2dd50` / yolo_ros `f7d3e94d` | [当前 C++ README](https://github.com/mgonzs13/yolo_ros/blob/94d2dd500cb26027ee9c019f4d3a02029ac615cc/README.md)、[Python 分支 README](https://github.com/mgonzs13/yolo_ros/blob/f7d3e94d2de95dec13a1cbfdb1cd702fb7d8eeac/README.md) | 检测/跟踪/深度三维定位分层、目标 frame 与深度单位配置；作为感知参考，不代替跨视角持久计数 |

## 针对本项目的取舍

- Superpowers 提供方法参考；不整包导入其强制流程、全量测试或子代理要求。检查规模按本次变更确定，纯文档修改不运行整机仿真。
- robotics-agent-skills 涵盖多个 ROS 发行版和大量设备；这里只保留当前 Python/Humble 所需方法。设备示例中的本地采集时钟不能直接充当 ROS TF 查询时间，ROS 观测沿用消息时间。
- Nav2 与 SLAM Toolbox 固定 Humble 参考，避免把 Rolling/Jazzy 的接口和插件写法套入当前环境。查阅的上游提交与本机安装版本仍应分别记录。
- yolo_ros 当前 main 是 C++/ONNX 管线，旧 `yolo_ros` 分支为 Python 包（查阅 package.xml 为 3.4.0）。两者参数、依赖和许可证不能混用。当前主分支是否适合本机尚未构建验证，不在本轮替换技术路线。
- 两份 yolo_ros 说明均出现默认深度换算除数 1000；当前相机已采样的 `32FC1` 流按米解释，需要明确适配，不能盲用默认值。
- 上游示例的 tracker ID 不解决任务级去重。房间边界、多视角坐标一致性、一对一关联和搜索完成条件按本项目架构实现并验收。

## 许可证与后续引入

以下仅记录查阅到的声明，不构成整个依赖树的许可审核：

- Superpowers：仓库 API 标识 MIT；robotics-agent-skills：Apache-2.0。借鉴方式是方法归纳，没有复制其完整指令或代码。
- Nav2：已核对 [nav2_simple_commander/package.xml](https://github.com/ros-navigation/navigation2/blob/3c3db59d6969d8ecee8e68468693d006397f4a0c/nav2_simple_commander/package.xml) 声明 Apache-2.0。仓库 API 整体为 NOASSERTION，不能由一个包推断全部文件。
- SLAM Toolbox：已读取 [LICENSE](https://github.com/SteveMacenski/slam_toolbox/blob/dccc5d1fd2b5007098f4050e681d20da37ef183f/LICENSE)，为 LGPL 2.1。
- yolo_ros：当前 C++ README 声明 MIT，模型权重另行许可；Python 分支的 [LICENSE](https://github.com/mgonzs13/yolo_ros/blob/f7d3e94d2de95dec13a1cbfdb1cd702fb7d8eeac/LICENSE) 为 GPL 3，[package.xml](https://github.com/mgonzs13/yolo_ros/blob/f7d3e94d2de95dec13a1cbfdb1cd702fb7d8eeac/yolo_ros/package.xml) 声明 GPL-3。

实际引入任何源码或模型时，再检查目标提交的文件和依赖许可，保存来源/版本/下载文件 SHA-256，保留必要的版权与许可文本。当前 sources.json 是参考来源清单，不是未来运行环境的依赖锁文件。
