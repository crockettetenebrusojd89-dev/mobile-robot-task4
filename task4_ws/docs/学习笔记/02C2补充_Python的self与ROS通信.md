# 从 Python 的 self 到 ROS 2 节点与订阅

日期：2026-11-09。用户明确选择跳过 1.0→2.0 的实际修改/运行练习，并说明 Python 基础较弱。本轮只阅读和解释代码，不要求启动仿真、改参数或执行命令；跳过练习不记录为完成或失败。

## 先从普通 Python 看起

函数是一段可以通过名字调用的代码。括号里放入参数，调用时执行函数体：

```python
def add(a, b):
    return a + b

answer = add(2, 3)
```

这里 add 是函数，add(2,3) 是调用函数，返回的 5 保存到 answer。下面出现的“方法”，可以先理解为与某个对象关联的函数。

## 类、对象和 self

类可以先理解成一类对象的定义，规定这些对象有哪些数据和操作。根据类创建出来的具体实例叫对象。以下是纯 Python 教学例子，不启动 ROS，也不会创建实际机器人：

```python
class Robot:
    def __init__(self, name):
        self.name = name

    def show_name(self):
        print(self.name)

a = Robot("小车A")
b = Robot("小车B")

a.show_name()  # 输出 小车A
b.show_name()  # 输出 小车B
```

Robot 是类；a 和 b 指向根据该类创建的两个对象。__init__ 是创建实例时执行的初始化方法，这里把传进来的 name 保存在该对象的 name 属性里。

调用 a.show_name() 时，Python 会把 a 对应的对象传给 show_name 的第一个参数。在方法内部，这个参数按惯例命名为 self。因此，这次 self 指向 a；调用 b.show_name() 时，self 则指向 b。

对于这里的普通实例方法，a.show_name() 可以对应理解为 Robot.show_name(a)。你没有在前一种写法的括号中手动填写 self，是因为 Python 已经通过 a.show_name 绑定了当前对象。

### 点号和括号分别在做什么

| 写法 | 含义 |
| --- | --- |
| a.name | 读取 a 对象的 name 属性 |
| self.name | 在方法里读取当前对象的 name 属性 |
| self.name = name | 把右侧参数 name 的值保存到当前对象的 name 属性 |
| a.show_name | 取出绑定到 a 的方法，暂不执行 |
| a.show_name() | 调用该方法，立即执行 |
| self.show_name() | 在方法内部调用当前对象的 show_name 方法 |

点号是访问对象属性/方法的一般语法。self 只是一个按惯例选用的参数名，不是 ROS 特有语法，也不是 Python 关键字。只有在当前作用域里 self 这个名字已定义时，才可以访问 self.xxx；本例通过方法的第一个参数定义它。

不是所有函数都必须写 self。普通函数、其他种类的方法各有用法；本轮只讨论本项目使用的普通实例方法。

## 为什么你的对象能调用 create_subscription

项目代码有：

```python
from rclpy.node import Node

class ScanReader(Node):
    ...
```

ScanReader(Node) 表示 ScanReader 继承 Node：在 Node 提供的基础功能上扩展自己的逻辑。Node 是 ROS 2 Python 库中的类，已经提供创建发布者、订阅者等方法。create_subscription 就在 Node 中定义，因此不需要在 scan_reader.py 中重新写一遍。

在 ScanReader 的实例方法里，self 指向当前 ScanReader 对象，所以可以调用继承来的 self.create_subscription(...)。它是一次“方法调用”；self 本身不是函数。

同理，self.on_scan 是当前对象上的、由我们定义的处理方法。一个来自基类 Node，一个由项目自己的 ScanReader 类提供。

## 节点、话题、消息、发布与订阅

可以把 ROS 系统看作多个分工的软件功能单元协作。当前只用下面这些词：

| 概念 | 简明含义 | 当前项目中的对应 |
| --- | --- | --- |
| 节点 node | 参与 ROS 通信的计算/功能单元 | task4_scan_reader，负责处理激光消息 |
| 话题 topic | 有名字的数据通信通道 | /scan |
| 消息 message | 一次传递的一份结构化数据 | 一条包含角度、量程、ranges 等字段的扫描 |
| 消息类型 | 这类消息的字段与结构约定 | LaserScan |
| 发布 publish | 向某个话题发送消息 | 仿真端向 /scan 发送扫描消息 |
| 订阅 subscribe | 创建接收某话题消息的关系与接收端 | scan_reader 接收 /scan |

节点是软件概念。一个进程可以有多个节点，节点也可以通过 ROS 与其他进程或机器上的节点通信；本项目的该示例只创建一个节点对象。

话题可以先用“广播频道”帮助理解：发布者发送数据，订阅者按同一个话题名、兼容的消息类型与通信设置接收。多个订阅者可以同时接收同一话题的数据，例如 echo、hz 和我们自己的 reader；通常不会因为 reader 收到一次消息就使其他订阅者拿不到它。

话题不是保存历史消息的普通文件；需要历史记录时要另外采用相应记录/通信机制。本轮先理解实时传递即可。

```text
仿真端发布者
    │ 发布 LaserScan 消息
    ▼
/scan 话题
    │ 被 task4_scan_reader 中的订阅者接收
    ▼
on_scan(msg) 处理这一条消息
```

图是通信关系的简化示意。ROS 实际的发现和传输由通信系统负责，/scan 不表示额外运行了一个同名“服务器程序”。

## 把这句话逐项读出来

```python
self.scan_subscription = self.create_subscription(
    LaserScan,
    "/scan",
    self.on_scan,
    qos_profile_sensor_data
)
```

左侧 self.scan_subscription 把创建好的订阅对象保存为当前节点的属性，供后续管理；它本身不等于距离数组。右侧调用 create_subscription 方法，四个参数按位置传入：

1. LaserScan：期待接收哪种类型的消息。
2. "/scan"：从哪个话题接收。
3. self.on_scan：消息到来后交给哪个处理方法。
4. qos_profile_sensor_data：采用传感器数据通信策略；当前先知道它是接收设置，QoS 细节以后结合问题展开。

整句可以读成：“为当前节点创建一个订阅，接收 /scan 上的 LaserScan 消息，用 on_scan 处理，采用给定的传感器通信设置，并把订阅对象保存起来。”

这里的代码层次是：对象 self → 方法 create_subscription → 传入四个参数 → 返回订阅对象。查看库源码时方法定义还列有 self 参数，调用时它由 Python 绑定，不需要再放进这四个参数里。

## 为什么 self.on_scan 后面没有括号

比较这两个表达式：

```python
handler = a.show_name  # 取出方法并保存，当前不执行
handler()              # 现在才调用，输出 小车A
```

创建订阅时同样传入 self.on_scan 这个已经绑定到当前对象的方法，让 ROS 后续调用。若写 self.on_scan()，会变成当场调用；本项目还会因为没有提供 msg 参数而报错。

回调的一个简化示例为：

```python
def on_scan(self, msg):
    print(len(msg.ranges))
```

msg 是本次收到的一条扫描消息，msg.ranges 是其中的距离数组。ROS 调用这个已绑定的方法时传入 msg；Python 的方法绑定负责 self。上面的例子只为解释语法，实际项目回调还有间隔控制、数据检查和统计。

项目中的 rclpy.spin(node) 让程序持续处理可执行的消息回调等事件。创建订阅时登记处理方法，消息到达并被执行器调度后，才执行对应处理代码。

## 结合项目再对照几个名字

| 名字 | 角色 |
| --- | --- |
| Node | ROS 2 库提供的基础类 |
| ScanReader | 项目定义的 Python 类 |
| node = ScanReader() | 创建当前示例使用的节点对象 |
| task4_scan_reader | 该对象在 ROS 图中的节点名 |
| /scan | 话题名 |
| LaserScan | 消息类型 |
| on_scan | 消息处理方法的名字 |

类名、节点名、话题名和函数名承担不同角色，不能只根据“都是名字”把它们当成同一种东西。

## 本轮学习边界

1. 运行示例的事实已经由用户截图确认，继续保留。
2. 1.0→2.0 的自主修改/运行练习按用户意愿跳过，不要求补交，也不标记通过。
3. 当前先理解对象、self、方法调用、节点、话题和订阅。阅读之后再按用户反馈处理尚不清楚的一环；本轮没有新的运行任务。
4. 后续结合现有代码学习条件判断、循环、索引和函数返回值，再讲数据算法。对 Python 的补充服务于项目，不预设用户已经掌握完整面向对象编程。

## 参考

- [Python 3.10 类与实例方法教程](https://docs.python.org/zh-cn/3.10/tutorial/classes.html)
- [ROS 2 Humble 节点概念](https://raw.githubusercontent.com/ros2/ros2_documentation/humble/source/Concepts/Basic/About-Nodes.rst)
- [ROS 2 Humble 话题与发布订阅](https://raw.githubusercontent.com/ros2/ros2_documentation/humble/source/Concepts/Basic/About-Topics.rst)
- [rclpy Node 源码，含 create_subscription](https://raw.githubusercontent.com/ros2/rclpy/humble/rclpy/rclpy/node.py)
- 项目对照文件：src/task4_bringup/task4_bringup/scan_reader.py。

## 2026-11-10 接续学习

用户已正确复述方法调用和参数关系。下一步阅读 [02C3 回调与激光数据筛选](02C3_回调与激光数据筛选.md)，从 msg.ranges 进入循环与条件判断；本轮不要求实际运行。
