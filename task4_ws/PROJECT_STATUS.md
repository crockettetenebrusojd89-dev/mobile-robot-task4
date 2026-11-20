# 当前项目状态

更新日期：2026-11-20。

## 当前阶段

M0 已完成，M1 部分通过。Codex 两次在静止仿真中验证 T1.1 雷达安装 TF 与仿真时钟。已验证 RGB、深度、CameraInfo 接收，用户此前提交了相机 TF、静止里程计和激光数据，并复现激光订阅/筛选。T1.2 运动链路与 T1.3 图像几何对齐待完成。当前由用户单人推进，最新证据、复现与下一个任务见 [交接文档](docs/交接文档.md)。

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
- 相机几何对齐、基础 TF、检测器版本、目标类别和语音服务。RGB/深度/CameraInfo 话题及 optical frame 已实际采样。
- 当前用户单人推进，A/B/C 用于划分工作模块；课程分组与贡献表按实际情况填写。

## GitHub

项目根目录已绑定私有 GitHub 仓库为 `origin`，本地 `main` 跟踪 `origin/main`。首个 T1.1 检查点 `c563d39` 已推送并核对。 [任务四 GitHub 仓库](https://github.com/crockettetenebrusojd89-dev/mobile-robot-task4)

## 下一步

工程下一项为 T1.2。在项目仿真出坞后低速移动，采集前后里程计、动态 TF、传感器安装变换和 scan。T1.3 与最小世界入口可并行准备；满足基础运动和世界依赖后进入 SLAM。学习沿 [02C5](docs/学习笔记/02C5_距离角度与雷达平面坐标.md) 接续，结合本轮实测 TF 讲解平移与旋转。用户复现和理解反馈分别记录。

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
