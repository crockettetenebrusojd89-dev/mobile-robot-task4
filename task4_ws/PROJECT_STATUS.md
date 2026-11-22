# 当前项目状态

更新日期：2026-11-22。

## 当前阶段

M0、M1 已完成。2026-11-21 通过 T1.4 总体验收，范围为 ROS 2 Humble / TurtleBot4 Lite / Fortress 的 maze 仿真。已核对时钟和雷达安装 TF、运动链路、静态方块在中央和靠近左边缘的 RGB-D 对齐。当前由用户单人推进，最新证据、复现与下一项见 [交接文档](docs/交接文档.md)。

M2 已完成地图制作、重载定位和三房间标定。T2.6 的 NavFn A* 与一次厨房入口导航由 Codex 实测通过。用户 RViz 复现和房间叠图确认待记录。 [导航复现](docs/交接文档.md#t26-nav2-与-a-导航) · [地图说明](maps/README.md)

教师教程一链接的 AWS 小屋仓库确实提供配套示例地图，教程二的 RViz 截图与该地图的元数据和轮廓吻合。当前 `task4_home` 使用项目自建的布局。 [教程地图来源核对](maps/README.md#教程里的地图来源)

地图实测对比中，Nav2 成功加载 AWS 栅格，临时修正鞋架惯量后 Gazebo Fortress 读到 AWS 小屋 87 个模型。AWS 机器人定位验证待做。用户首轮重影地图与 RViz 崩溃证据已归档，第二轮使用项目自建场景通过 T2.3。 [首次重影排查](docs/交接文档.md#首次地图重影后的重建)

截至 2026-11-10 的知识差距评估见 docs/学习现状与算法实施安排.md：当前在基础数据解释和第一段算法阅读，建图导航、检测/地图定位、去重计数、搜索语音与结果验证尚未系统展开。评估不以课次数折算完成百分比，也不增加知识掌握或功能验收记录。

## 已准备

- 已创建独立目录、说明文档、开发约定、VS Code 工作区文件、ROS 2 Python 包骨架和构建脚本。
- 已整理任务要求、阶段检查点、模块接口草案、分工建议和学习清单。
- 已复制 4 份原始文件（任务书、教程压缩包、报告模板、通知截图），逐一核对 SHA-256，并解出 3 份 PDF 教程。来源与校验值见 materials/manifest.json。
- Python、Shell、JSON、XML 和 YAML 语法及解析检查通过。
- `bash build.sh` 构建通过：1 个包完成。日志见 results/environment/build-2026-11-07.log。
- `ros2 run task4_bringup workspace_info` 返回成功，已安装的两份配置文件可发现。输出见 results/environment/workspace-info-2026-11-07.json。
- 基础环境检查返回 baseline_ready=true；完整清单见 results/environment/2026-11-07.json。
- 已新增项目 skill `.agents/skills/task4-delivery/`，用于任务四开发、排错、学习与验收；项目总目录与工作区 AGENTS.md 均提供显式入口。来源与结构检查见本页 2026-11-10 skill 记录。
- 已复核 [开发与验收路线](docs/任务四开发与验收路线.md)，并补充 [技术原理、GitHub 选型与备选方案](docs/技术路线.md)。本机静态核对了 TB4 世界资源路径覆盖、雷达静态 TF 声明、NavFn 默认参数和 Humble Action 等待行为。项目运行证据仍见现有 M1 记录。

原生 colcon 在当前受限执行环境中发生 Python 包安装前等待；普通 setup.py 命令可正常执行。项目内 scripts/colcon_entry.py 为 Linux/Python 3.10 构建进程选择 SafeChildWatcher 后构建成功，未修改系统 colcon 文件。

## 环境现状

- 已检查：Ubuntu 22.04.5、Python 3.10.12、ROS 2 Humble；ros2、colcon 和 ign 命令存在。
- 当前终端可发现 rclpy、OpenCV、NumPy 和 PyYAML；未发现 ultralytics。
- `/opt/ros/humble/share` 下可见 Nav2、SLAM Toolbox 和 RViz2；未见 TurtleBot3 Gazebo 和 gazebo_ros 包目录。
- 已存在 `/home/hao/turtlebot4_ws/install/setup.bash`，本工作区不会自动叠加它。
- 包是否可发现不代表节点、图形界面或推理功能已经验证。

## 待决定

- 首步开发验证采用现有 TurtleBot4 Lite/Fortress；最终课程型号要求仍须核实。
- 检测器版本、目标类别和语音服务。当前仿真 RGB-D 配准和基础 TF 已分别实测。
- 当前用户单人推进，A/B/C 用于划分工作模块；课程分组与贡献表按实际情况填写。

## GitHub

项目根目录已绑定私有 GitHub 仓库为 `origin`，本地 `main` 跟踪 `origin/main`。首个 T1.1 检查点 `c563d39` 已推送并核对。 [任务四 GitHub 仓库](https://github.com/crockettetenebrusojd89-dev/mobile-robot-task4)

## 下一步

下一项为 T2.7，复用同一个导航入口验证三处房间入口和拒绝或失败、取消、超时等 Action 终态。用户可先在 RViz 复现厨房入口。 [T2.7 任务卡](docs/任务四开发与验收路线.md#t27-导航-action-验收接受成功失败取消)

## 2026-11-22 T2.6 Nav2 和厨房入口实测

- 验证人 Codex。使用项目 `task4_home`、用户实扫 `task4_home_v1` 和 AMCL。项目参数以本机 TurtleBot4 默认文件为来源，只启用 `GridBased.use_astar`。构建、安装比对和运行时查询均通过。NavFn 插件为 `nav2_navfn_planner/NavfnPlanner`，规划、控制、行为树三个节点均为 `active [3]`。
- `/navigate_to_pose` 接受厨房入口 `(3.2322, 1.6655, -0.4482)` 并返回 `SUCCEEDED (4)`。Gazebo 轨迹确实穿过厨房门。停车时地图 TF 位置误差 0.245 m、航向误差 0.083 rad，符合控制器配置的 0.25 m 和 0.25 rad 容差。
- 本机证据在 `results/m2_map_nav/2026-11-22_t2_6_verified/`。常规出坞超时后取消，验收在新隔离仿真中临时移开测试充电座。用户 RViz、常规出坞、其他入口和失败处理待复现或验收。 [验收与复现](docs/交接文档.md#t26-nav2-与-a-导航)

## 2026-11-22 T2.5 房间标定

- Codex 为用户地图标定三个房间、三个入口和七个观察点。房间轮廓按 T2.3 配准映射到 `map`，用实际地图边界裁剪。卧室床后的一角位于地图图像范围外。地图配置和图像哈希均进入房间配置。
- 离线检查确认边界互不重叠，10 个点均在对应房间自由栅格内，并从不穿过障碍或未知区的同一连通区域可达。净空下界最小 0.390 m。每个观察点配置 6 个相隔 60° 的朝向。
- 检查报告、叠图和视线估计在 `results/m2_map_nav/2026-11-22_t2_5.3DzDEK/`。用户目视确认、导航到点和实际检测待记录。 [房间配置](src/task4_bringup/config/rooms.yaml)

## 2026-11-22 T2.4 地图加载与定位

- Codex 在新启动的 `task4_home` 仿真核对 map_server 和 AMCL 均为 active。修正地图的自由区阈值，逐格确认 14,767 个未知格仍为未知。Humble 定位入口从工作区使用相对地图路径，绕开中文绝对路径转义。
- 以 T2.3 已配准的 Gazebo 位姿作为离线参考，初始和运动后 AMCL 平面偏差约 1.1 和 1.3 厘米。旋转再低速直行后，Gazebo 与 AMCL 分别记录 1.013 和 1.000 米位移。实测激光到最近地图障碍格的中位距离前后均约 2 厘米。
- 本机证据为 `results/m2_map_nav/2026-11-22_t2_4_udp.775bcx0o/summary.json` 与同目录叠图及命令日志。低速测试临时挪开了隔离仿真的充电座，常规出坞复测、用户 RViz 截图及理解反馈待记录。

## 2026-11-21 T2.3 用户键盘建图通过

- 用户驾驶并提交 RViz 截图，Codex 保存实际 `/map`。与场景对齐后的 0.05 m 抽样中，三间房离墙及家具边均超过 0.18 m 的样本全部可通行。以 0.225 m 为半径按障碍和未知格膨胀后，两扇门和三间房的检查点同属一个可通行区域。床、柜及沙发后的遮挡区域保留为未知。
- 基础地图保存为 194 × 159 格、0.05 m/格。独立域 155 的 Nav2 map_server 进入 active 并发布相同尺寸与原点，已退出。截图、几何复核和 map_server 日志在 `results/m2_map_nav/2026-11-21_t2_3_map_review.ZRcSwE/`。未执行 AMCL 或导航。 [地图文件](maps/task4_home_v1.yaml) · [校验与位姿记录](maps/manifest.json)

## 2026-11-21 T2.2 三房间场景

- Codex 在本机 Gazebo Fortress / TurtleBot4 Lite 验证。8 × 6 m 布局加载客厅、厨房、卧室，两个门洞净宽各 1.20 m。按 0.175 m 底盘半径另留 0.10 m，离线碰撞几何检查确认三房间连通。仿真机器人保持静止采样，驾驶验收留给 T2.3。
- Gazebo 查询的五把椅子和评估真值位置一致，房间分布为 3 / 2 / 0。机器人相机保存 3 组 320 × 240 RGB-D 帧，首帧可见椅子。每帧激光在客厅西墙上有 249 个连续回波符合 3 cm 位置容差，时钟检查得到 217 组配对。
- 本机汇总为 `results/m2_scene/2026-11-21_t2_2.54gU3o/summary.json`，同目录保存俯视图和原始采样。椅子使用自制简模，识别效果待 T3.1 实测。 [启动与真值复现](worlds/README.md#任务四三房间场景)
- T2.3 前置试跑收到 0.05 m 分辨率的初始 `/map` 和 `map → base_link`。出坞、键盘驾驶及三房间地图由用户实际操作验收。 [键盘建图交接](docs/交接文档.md#t23-键盘建图)

## 2026-11-21 T2.1 自定义场景入口

- 新增项目启动文件和最小 SDF。启动文件合并本项目与安装包的资源路径，沿用 TurtleBot4 机器人、充电座及传感器桥接。首次自定义世界试验中的桥接使用了仓库世界的默认名称，修正为从 SDF 读取实际世界名，复测收到真实传感器数据。
- `task4_smoke` 运行时可见机器人、充电座及测试墙。收到 320×240 RGB、深度和 CameraInfo；`/scan` 与唯一 `/clock_bridge` 实测通过，雷达在底盘前向量到墙面约 2.430 m。默认入口回归仍加载 maze，实际收到 LaserScan。
- 本机证据为 `results/m2_scene/2026-11-21_t2_1_retry.tPeRk5/summary.json` 和同目录相机帧。核对老师提供的压缩包及 PDF 附件清单后，确认当前资料中只有教程，课程地图按任务书由本组键盘遥控建图生成。

## 2026-11-21 T1.4 M1 验收汇总

- 核对 T1.1 的原始时钟配对和当前模型文件校验值，重新计算 T1.2 三次运动快照并核实 TF 时间戳，回放 T1.3 的 10 组实测帧并复核输出。核对话题、frame 和深度编码、单位后，将 `frames_topics.yaml` 的 `verified` 设为 true。
- 本机验收汇总为 `results/m1_sensor_check/2026-11-21_t1_4.8nqety/summary.json`，同目录保留原报告的校验值、复核日志和 RGB-D 回放结果。工程实测来自 2026-11-08 至 11-21，本次为复核和配置固化。地图、`map→odom`、导航及物品定位留待后续阶段验证。

## 2026-11-21 T1.3 RGB-D 对齐

- Codex 在隔离的 TB4 Lite/Fortress maze 仿真中临时放置紫色方块。方块底部离地 0.10 m，轮廓与地面分开，仍穿过雷达扫描平面。机器人保持静止，中央和靠近左边缘各采 5 帧。
- 10 帧的 RGB、32FC1 深度、CameraInfo 时间戳逐帧相同。两组测得最佳轮廓偏移均为 (0, 0) 像素，原始轮廓距离中位数均为 0 像素。中央一组把相机和雷达测量都换算到底盘前向 X，分别为 1.50179 m 与 1.50040 m，相差约 1.39 mm。
- 将 `rgb_depth_aligned` 设为 true，并记录本轮 [采集与检查流程](docs/任务四开发与验收路线.md#t13-rgb深度几何对齐)。本机证据为 `results/m1_sensor_check/2026-11-21_t1_3_raised.dET159/summary.json`、帧数据和叠图。当前整体 `verified` 留待 T1.4 汇总。这些结论限于本轮仿真和两处测试位置，用户复现待记录。

## 2026-11-20 T1.2 运动链路与安装 TF

- Gazebo 中 `/undock` 返回 `SUCCEEDED`，`/dock_status` 确认离座。向隔离域内的 `/cmd_vel` 发送 0.10 m/s 约 2 仿真秒，测得沿车头方向前进 0.19950 m。再以 0.50 rad/s 转约 3.14 仿真秒，测得原地左转 89.47°。两次动作结束均发送零速度并采到止动状态。
- 车头方向 ±10° 的有效回波换到底盘坐标后，前向中位距离从 4.65408 m 降到 4.45431 m。三组采样时刻的 `odom→base_link` 与 `/odom` 一致，`odom→雷达` 在 scan 时间戳可查。雷达和相机相对底盘的安装变换在三组中一致。
- [采样脚本](scripts/check_motion_tf.py) 实际运行三次，比较通过十项条件。本机证据为 `results/m1_sensor_check/2026-11-20_t1_2.guqTUD/motion/summary.json` 与同目录三组 JSON，上一级保留出坞、速度指令、启动和关闭记录。用户复现待记录。

## 2026-11-20 T1.1 雷达 TF 与时钟

- 使用项目入口启动两次 TB4 Lite/Fortress maze。探针一次订阅 `/scan`、`/clock`，使用实际 scan frame 查 `base_link` 安装 TF。两次分别取得 190/182 组有效配对，最大仿真时间差为 0.138/0.123 秒，各有 8 次一致的 TF。量值与安装模型一致。
- 复测的底盘、关节及机器人状态节点均启用仿真时间。综合证据保存在本机 `results/m1_sensor_check/2026-11-20_t1_1_repeat.Xz5GZn/summary.json`，可复现入口见 [交接文档](docs/交接文档.md)。本轮运行证据由 Codex 采集。
- 已填入实测 base/scan frame，`frames_topics.yaml` 的总验收标志仍为 false。T1.2 的运动与 T1.3 的配准将单独验收。

## 技术路线与首步准备证据

- 已制定模块方案、开发检查点、目标日期和评估方法，见 docs/技术路线.md。
- 已核对本机 turtlebot4_simulator 版本 0ea4a60，检查时源码工作树无修改；桥接文件包含 RGB、深度、CameraInfo 和 scan。
- 新增 sim_env.sh、start_sim.sh 及项目内 .compat 生成脚本。仿真使用独立通信域与 Ignition partition，项目内使用 Ogre2 传感器配置和原始底盘控制参数。
- `bash start_sim.sh --show-args` 通过，输出保存在 results/m1_sensor_check/launch-arguments.txt。这只验证启动文件解析，不代表仿真运行通过。
- Shell/Python 语法、本地覆盖文件 XML/YAML、系统源文件校验、底盘 odom TF 默认值、图像查看器入口及 topic echo 参数检查通过。
- 上述 11 月 7 日准备工作未启动实际 GUI 或验收传感器；11 月 8 日新增相机数据证据如下。激光、TF、稳定频率及几何对齐仍待检查，frames_topics.yaml 的 verified 保持 false。

## 2026-11-08 相机数据与学习检查

- 用户截图：results/m1_sensor_check/user-rgb-view-2026-11-08.png；来源与 SHA-256 独立记录，不能由截图推定深度和 TF 通过。
- 实际执行只读采样，RGB、深度、CameraInfo 各收到 3 条消息，状态为 DATA_RECEIVED。证据为 results/m1_sensor_check/agent-rgbd-report-2026-11-08.json 和同目录 agent-rgbd-run-2026-11-08.log。
- RGB 为 320×240、rgb8；深度为 320×240、32FC1；frame_id 均为 oakd_rgb_camera_optical_frame。按 REP 118 解释深度为米。
- 本次采样有效深度比例约 72.3%，中心 5×5 区域有效深度中位数约 3.04 米。数值随视角和场景变化，不能视为目标识别或地图位置。
- CameraInfo：fx≈221.765、fy≈221.765、cx=160、cy=120；本次畸变参数为零，K 与 P 对应内参一致。
- 新增学习进度与第一课笔记；提供只读 check_rgbd.py。以构造数据检查了无效值、32FC1、16UC1 毫米换算、字节序、行填充及损坏输入处理，另与实际采样分别记录。
- 本次同尺寸、同 frame_id 和采样时间戳相等不替代 RGB/深度几何对齐验证。完整 M1 尚未通过。

## 2026-11-08 用户复现与学习反馈

- 已读取用户生成的 results/m1_sensor_check/rgbd_report.json，状态为 DATA_RECEIVED；各项接收检查通过。为保留证据，归档为 user-rgbd-report-2026-11-08.json，并保存用户终端截图及来源校验。
- 第一题已理解 RGB 与深度语义不同；进一步澄清 Z 深度与到相机中心的直线距离。
- 第二题将像素数值 2.5 与字节混淆，已补充说明：32FC1 的每个像素占 4 字节；当前深度流中的 2.5 按规范表示 2.5 米。理解情况后续继续巩固。
- 第三题已理解深度不能直接当地图坐标。新增第二课，以相机到 base_link 的 TF 作为下一项操作。
- 本轮未运行 TF 查询，不宣称基础 TF 连通性或完整 M1 通过。

## 2026-11-09 独立项目目录

- 项目总目录：/home/hao/Documents/ChatGPT/综合设计大项目。当前 ROS 工作区：/home/hao/Documents/ChatGPT/综合设计大项目/task4_ws。
- 已迁入源代码、教师资料、学习笔记、配置、截图和实验结果。
- 原位置 /home/hao/Documents/ChatGPT/自主移动机器人/work/task4_ws 仅保留指向新工作区的兼容链接。
- 原 build/install/log/.compat 已保存在项目内 migration_archive；新位置重新生成构建和覆盖文件。
- 新位置的包构建、workspace_info 和仿真启动参数解析检查通过，证据在 results/migration/2026-11-09/。未启动新的仿真或发布运动命令。
- 实验一、二、三仍位于原自主移动机器人目录；本次只整理任务四。
- 学习进度保持第二课操作 A 待运行，未将目录迁移作为 TF 或 M1 验收证据。

## 2026-11-09 目录改名后的路径修复与第二课

- 检查发现当前项目总目录名为“自主移动机器人综合设计大项目”；活动文档、旧工作区兼容链接已同步至 /home/hao/Documents/ChatGPT/自主移动机器人综合设计大项目/task4_ws。前文迁移路径保留作历史记录。
- 将改名前生成的 build/install/log/.compat 归档在 migration_archive/generated_before_folder_rename_2026-11-09/ 后重新生成。构建、包入口及仿真启动参数解析通过，证据见 results/path_repair/2026-11-09/。
- 源码、脚本、教师资料校验一致；第二课补充坐标轴和安装平移示例。未运行 TF 采样或启动新仿真；操作 A 仍待用户执行。

## 2026-11-09 相机安装 TF 用户证据

- 证据及来源校验：results/m1_sensor_check/user-camera-tf-2026-11-09.png 和 .source.json；依据此前操作 A 上下文解释坐标系配对，截图本身未显示输入命令。
- Translation=[-0.037,0,0.186] 米；旋转四元数与截图矩阵相符。相机原点相对 base_link 后移约 3.7 厘米、上移约 18.6 厘米；不是相对地面的高度。
- 用户两项回答正确；相机 Z 轴朝底盘前方、X 轴朝右、Y 轴朝下的解释已补入笔记。旋转理解继续巩固。
- 截图不替代运动不变性、/clock、动态 TF 或几何对齐验收。本轮仅记录证据和更新笔记，未自行运行 ROS 查询或运动命令。
- 下一步为第二课操作 B，完整 M1 仍未通过。

## 2026-11-09 里程计用户证据

- 两张用户截图及 SHA-256 转录在 results/m1_sensor_check/user-odom-evidence-2026-11-09.json。/odom 与 TF 的参考/被描述坐标系分别为 odom/base_link。
- 用户正确判断 position 的坐标系与对象。位置估计近零，TF 在约 438—442 秒取得更新；不同截图时间不同，不作为同步精度检查。twist 未完整显示，不记录实际速度通过。
- 本机控制配置为差速控制器、open_loop=false、enable_odom_tf=true；仅核对静态配置，未查询实时话题发布者。
- 新增 odom 补充笔记，当前先处理用户概念疑问，完整 M1 及运动验证仍未通过。

## 2026-11-09 odom 与 map 概念澄清

- 根据用户疑问扩充第二课补充笔记：固定局部参考不保证全局对齐；漂移是估计误差累积；map 与 odom 主要区别在全局约束和连续性。
- 用距离比例误差、朝向误差及 map→odom=-0.3 米的假设例子解释，均非本机实测。查阅 REP 105 与 Humble 差速控制器文档。
- 无新增 ROS 查询、运动、建图或定位验证；完整 M1 状态保持未通过。

## 2026-11-09 学习现状与算法实施节奏

- 用户询问下一步、知识掌握情况与算法何时实施。已依据实际截图和回答评估：能按说明运行并解释部分输出，尚无用户自主编写业务节点或运行 SLAM/Nav2/检测/去重模块的证据。
- 新增 docs/学习现状与算法实施安排.md、docs/学习笔记/02C_激光雷达与LaserScan.md；把算法分为激光处理、SLAM、AMCL/A*、检测、反投影/TF、关联计数和任务状态机，按依赖逐步实现。
- 核对 LaserScan 官方定义、Topics 教程、SLAM Toolbox README、Nav2 Humble 示例参数及本机雷达模型/桥接；本机静态配置不当作 /scan 实测。
- 当前只安排读取消息元信息与 hz，完整激光、时间、运动和 M1 仍未验收。

## 2026-11-09 LaserScan 用户接收证据

- 截图和来源校验在 results/m1_sensor_check/user-laserscan-2026-11-09.png 与 .source.json。实际 frame=turtlebot4/rplidar_link/rplidar，数组长度 640，角度覆盖约一周、步长约 0.563°，量程约 0.164—12 米。
- hz 可见平均值约 57.096—58.430 Hz，最后 57.757 Hz；仅作为当前订阅者的短时间接收证据。scan_time/time_increment 为 0，不从中推定真实采样周期或运动补偿条件。
- ranges 与 intensities 数值被隐藏，尚不确定有效回波数、最近距离或强度意义；完整 frame 与底盘 TF 尚未验证。
- 用户明确表示不理解输出，02C 已增加入门解释；当前没有自主写数据节点或算法掌握的新证据。

## 2026-11-09 首个激光数据处理节点

- 用户已正确解释同墙多角度采样。新增 scan_reader、scan_math 与 C2 讲义，注册 ROS 入口并声明 rclpy/sensor_msgs 依赖。
- 节点使用传感器 QoS，只读 /scan，按原数组索引过滤非有限/量程外数值，寻找最近有效回波并在原 frame 中计算平面坐标；无有效值不输出假零距离。
- 5 项数学检查、colcon 构建、安装导入与入口发现通过，证据在 results/lesson02_scan_reader/2026-11-09/。
- 助手 8 秒只读检查收到数据=True、观察到有效回波=True；运行日志保留 frame/时间/统计，未发布运动命令。用户尚未运行示例。
- 示例不进行雷达到底盘变换、地图定位或障碍物身份识别，不推定完整激光/TF/M1 验收通过。

## 2026-11-09 首个节点用户复现证据

- 用户截图与 SHA-256 记录在 results/lesson02_scan_reader/2026-11-09/user-scan-reader-2026-11-09.png 和 .source.json。6 组可见摘要均为 640/640/0，最近距离显示 1.000 米、序号 0、雷达角度 -180°。
- 用户量程过滤解释正确，新增非有限值补充及订阅四参数讲解；自主编程与参数修改尚未验证。当前练习由用户修改 report_interval_sec=2.0，助手没有修改源码。
- 本轮无新 ROS 采样、运动或算法代码变更；雷达到底盘 TF、时间与完整 M1 仍待验收。

## 2026-11-09 Python 基础缺口与教学调整

- 用户说明 Python 基础较弱，追问 self 的作用域、方法调用和 ROS 通信概念。新增 02C2 补充笔记并调整活动学习入口。
- 用户明确选择跳过修改/运行练习，此项保持未验证并标记主动跳过；既有 C2 运行成功与量程过滤理解证据保留。
- 本轮仅文档和教学状态更新，源码未改、未启动仿真、未执行 ROS 节点或控制。完整 M1 及独立编程能力仍不宣称通过。

## 2026-11-10 回调与距离筛选阅读课

- 用户正确复述 self.create_subscription(...) 是方法调用、括号内是参数；继承来源和回调引用已解释。不由此推定完整面向对象知识已掌握。
- 新增 02C3 讲义，用明确标注的假设数组讲 msg.ranges、原序号、for/enumerate、有限值和量程过滤、continue、计数与最近值。当前等待口头手算反馈。
- 已核对普通 Python 示例输出与语法、项目相对链接；scan_reader.py 与 scan_math.py 保持不变，显示处理间隔仍为 1.0。未运行 ROS、重建包或发布控制命令，完整 M1 状态不变。

## 2026-11-10 手算反馈与保存方式教学

- 用户给出正确的有效数/最近值/原序号，并正确识别打印与收集结果的区别；新增 02C3 第 8 节，解释 append、原序号配对、本次局部列表、最新帧对象属性和文件保存。
- 核对 Python 3.10 官方列表说明及现有 scan_math.py；用普通 Python 构造消息核对讲解例子得到 [(0, 3.0), (2, 1.2)]，原数组保持不变。讲义语法和链接已检查。
- 项目当前函数仍只记录统计和最近样本并返回字典；两个源码校验一致。本次仅教学文档与进度更新，完整 M1 状态不变。

## 2026-11-10 最近有效回波算法阅读准备

- 新增 02C4 并更新学习入口，细读现有最小值循环，不改变任务算法或验收状态。用户当前只确认前一题基本筛选手算和打印/收集的区别，新的更新规则理解尚待反馈。
- 已检查讲义 Python 语法、完整假设例子输出 2 1.2 2、与项目更新片段一致及相对链接。两个源码 SHA-256 保持不变。
- 本轮没有 ROS 采样、包重建或控制命令，完整 M1 状态不变。

## 2026-11-10 角度与雷达平面坐标教学

- 新增 02C5 和可调整角度/距离的教学示意，解释已有坐标计算；不因继续学习而认定上节等距题已通过。雷达 frame 与底盘/map 分别说明，实际安装对齐仍待 TF 验证。
- 检查假设例子输出 45.0 与 1.414 1.414、三个基准方向、Python 语法和相对链接；宽/窄屏截图已查看，4 组交互坐标检查通过。教学验证记录在 results/lesson02_polar/2026-11-10/，不作为机器人运行证据。
- 两个源码文件校验未变；本次没有 ROS 运行、包重建或运动命令，完整 M1 状态不变。

## 2026-11-10 项目任务确认与专用 skill

- 已读取项目总目录和工作区 AGENTS.md、当前状态、学习进度、任务要求、技术路线和架构草案。确认任务四为语音指定房间/物品后的导航搜索、地图定位、去重编号、数量输出与标注地图保存；任务书型号差异继续列为待核实。
- 新增 `docs/项目任务与Skill说明.md` 与 `.agents/skills/task4-delivery/`。skill 包含阶段验收、ROS 2 集成排错、感知定位/持久计数、GitHub 来源四份参考，以及 UI 元数据和来源 JSON；两份 AGENTS.md 与 README 已加入入口。
- 实际阅读 Superpowers 的 2 份 skill、robotics-agent-skills 的 3 份 skill，并核查 Nav2/SLAM Toolbox Humble 和 yolo_ros 两种实现的参考文件。10 份主要参考记录固定提交与收到正文的 SHA-256；本次仅归纳方法，未引入第三方源码或模型。
- 已核对 Humble NavFn 示例 `use_astar=false`、导航目标拒绝/最终结果、地图保存与 pose graph 的区别、yolo_ros 默认深度除数和当前米制深度的适配。当前 main 为 C++/MIT，所查 Python 分支声明 GPL-3，不能混用接口或许可证标识。
- `quick_validate.py` 返回 `Skill is valid!`；本地链接、YAML/JSON、来源格式和两处入口检查通过；31 份既有源码、脚本、配置和教师资料 SHA-256 与本轮基线一致。检查证据见 [verification.json](results/skill_setup/2026-11-10/verification.json)。
- 本轮仅新增 skill 和文档，没有运行 ROS、构建包、安装组件或发布控制命令。M1、当前角度/frame 学习检查点及跳过/待反馈练习状态保持不变；下一步仍按实际依赖完成雷达 TF、时间和运动验证，再推进 SLAM。
