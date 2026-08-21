# 绝影Lite3 电力巡检系统

<div align="center">

![绝影Lite3机器狗](docs/assets/03-绝影Lite3机器狗.jpg)

**广西电力职业技术学院 · 2026年全国职业院校技能大赛项目**

基于云深处绝影Lite3专业版机器狗二次开发的智能电力巡检解决方案

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#license)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-1.7-brightgreen.svg)](#版本信息)
[![Status](https://img.shields.io/badge/Status-Deployment_Ready-success.svg)](#快速开始)

</div>

---

## 一、项目概述

### 1.1 项目背景

本项目面向**2026年全国职业院校技能大赛**——机器狗电力巡检赛项，基于云深处科技绝影Lite3专业版机器狗平台进行二次开发，应用于抽水蓄能电站（沙盘模型）的智能电力巡检演示。系统通过集成双光谱云台相机、深度学习算法和实时通信协议，实现对电站设备的自动化巡检能力，包括裂缝检测、温度监测及机器狗状态实时监控。

![抽水蓄能电站沙盘模型](docs/assets/02-抽水蓄能电站沙盘模型.jpg)

### 1.2 核心目标

| 目标类型 | 具体指标 | 完成状态 |
|----------|----------|----------|
| 裂缝检测 | 自动识别 ≥0.1mm 混凝土裂缝，测量误差 <0.02mm | ✅ 已完成 |
| 温度监测 | 双级告警（45℃预警 / 50℃告警），测温精度 ±1℃ | ✅ 已完成 |
| 演示流程 | 完整12分钟标准化演示流程 | ✅ 已完成 |
| 平台对接 | WebSocket实时数据上报，HTTP REST接口 | ✅ 已完成 |
| 环境适配 | 支持模拟/混合/真实三级模式切换 | ✅ 已完成 |

### 1.3 系统功能概述

本系统采用**感知主机 + 独立监测平台**的双部署架构，主要功能包括：

#### 1.3.1 裂缝检测功能

通过云台可见光相机采集图像，利用YOLOv8 + U-Net深度学习模型进行裂缝识别，实现对混凝土表面裂缝的自动检测与量化分析。系统可测量裂缝宽度与长度，并支持断网缓存与数据补传。

#### 1.3.2 温度监测与告警

基于双光谱云台相机的热成像功能，实时监测目标温度并执行双级阈值告警：
- **预警阈值**：45℃（现场使用白灯模拟低温状态）
- **告警阈值**：50℃（现场使用红灯模拟高温状态）

系统同时支持升温速率监测，可识别异常温升趋势。

#### 1.3.3 机器狗状态监测

实时采集并上报机器狗本体状态数据，包括：
- 电池电量（动态放电模型）
- 位置坐标与关节角度（运动学模型）
- CPU/GPU温度（随负载变化）
- IMU姿态数据（Roll/Pitch/Yaw）
- 超声波障碍物距离

#### 1.3.4 视频流转发

支持可见光与热成像双路视频流的实时转发，通过RTSP协议采集图像，经WebSocket推送至监测平台（15fps JPEG压缩）。

#### 1.3.5 运动控制

监测平台提供键盘手柄控制功能，通过WebSocket发送运动指令至感知主机：
- 前进/后退/左移/右移（WASD/方向键）
- 左转/右转（Q/E）
- 起立/趴下（Space）
- 紧急停止（ESC）

#### 1.3.6 数据上报与存储

所有巡检数据通过WebSocket实时上报至第三方监测平台（可部署于本地电脑或云端），同时本地SQLite缓存保障断网续传能力。

---

## 二、快速开始

### 2.1 系统要求

#### 感知主机（Jetson NX）配置

| 项目 | 实际值 |
|------|--------|
| 操作系统 | Ubuntu 20.04 LTS |
| Python版本 | 3.8+ |
| GPU环境 | NVIDIA Jetson NX + CUDA |
| SSH账户 | ysc@192.168.1.103 |
| SSH密码 | `'`（英文单引号）|

#### 监测平台（笔记本）配置

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10+ / macOS / Linux |
| Python版本 | 3.8+ |
| 网络连接 | WiFi内网 |

### 2.2 感知主机部署

```bash
# 1. SSH登录感知主机
ssh ysc@192.168.1.103
# 密码: '（英文单引号）

# 2. 解压部署包
cd ~ && mkdir -p lite3-power-inspection && cd lite3-power-inspection
unzip -q ~/lite3-power-inspection.zip

# 3. 安装依赖（离线模式）
./scripts/offline_install.sh sensors

# 4. 配置WebSocket地址
sed -i 's|ws://MONITOR_HOST:8765/ws|ws://<笔记本IP>:8765/ws|' config/inspection_config.yaml

# 5. 运行演示
python3 scripts/run_demo.py --mode simulation
```

### 2.3 监测平台部署（Windows）

```cmd
:: 1. 解压便携包到任意目录
:: 2. 双击运行
start_monitor.bat
:: 3. 访问 http://localhost:8000
```

### 2.4 启动顺序

```
1. 先启动监测平台（笔记本）→ start_monitor.bat
2. 再启动感知主机巡检程序 → python3 scripts/run_demo.py
3. 验证连接 → http://localhost:8000
```

---

## 三、系统架构

### 3.1 系统架构图

![系统架构图](docs/assets/04-系统架构图.png)

### 3.2 双部署架构说明

| 部署位置 | 服务组件 | IP地址 | 端口 |
|---------|----------|--------|------|
| **感知主机** (Jetson NX) | 巡检程序、AI推理、数据采集 | 192.168.1.103 | 43893/8765 |
| **监测平台** (笔记本) | FastAPI服务、Web界面 | localhost | 8000/8765 |

### 3.3 核心参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 感知主机IP | 192.168.1.103 | Jetson NX |
| 运动主机IP | 192.168.1.103 | RK3588（共享IP）|
| 云台相机IP | 192.168.1.108 | 静态配置 |
| UDP控制端口 | 43893 | 运动指令 |
| UDP数据端口 | 43894 | 状态上报 |
| WebSocket端口 | 8765 | 数据通信 |
| HTTP服务端口 | 8000 | 监测平台 |
| RTSP端口 | 554 | 视频流 |
| 心跳周期 | ≤500ms | UDP心跳 |
| 告警阈值 | 45℃/50℃ | 预警/告警 |

### 3.4 演示模式

| 模式 | AI识别 | 本体数据 | 适用场景 |
|------|--------|----------|----------|
| `simulation` | 模拟数据 | 物理模型 | 无模型环境演示 |
| `real` | 真实推理 | 物理模型 | 有模型环境演示 |
| `hybrid` | 混合模式 | 物理模型 | 部分真实演示 |

**核心特性**:
- **本体数据真实性保障**: 电池状态、位置坐标、关节角度始终基于物理模型生成
- **视频流转发**: RTSP → WebSocket → 监测平台（15fps JPEG压缩）

```bash
# 运行演示
python3 scripts/run_demo.py --mode simulation
python3 scripts/run_demo.py --mode real
python3 scripts/run_demo.py --mode hybrid

# 指定WebSocket地址
python3 scripts/run_demo.py --ws-url ws://<笔记本IP>:8765/ws
```

---

## 四、数据流向与软件流程

### 4.1 数据流图

![数据流图](docs/assets/05-数据流图.png)

**数据流向说明**:

```
云台相机 ──RTSP──► 感知主机 ──WebSocket──► 监测平台（Web界面）
                  │                      ↓
                  │              SQLite本地缓存（断网续传）
                  │
运动主机 ──UDP──► 感知主机 ──物理模型──► WebSocket──► 监测平台
```

### 4.2 软件流程图

![软件流程图](docs/assets/06-软件流程图.png)

**流程说明**:

1. **初始化阶段**：加载配置文件，建立WebSocket连接，启动UDP监听
2. **数据采集阶段**：打开RTSP视频流，初始化相机参数
3. **巡检执行阶段**：根据演示模式（simulation/real/hybrid）执行检测逻辑
4. **数据处理阶段**：裂缝检测（YOLOv8+U-Net）、温度监测（双级阈值）
5. **数据上报阶段**：通过WebSocket发送巡检结果至监测平台
6. **控制响应阶段**：接收运动控制指令，更新机器狗状态

---

## 五、技术实现

### 5.1 UDP数据接收

感知主机通过UDP从运动主机接收真实本体数据：

| 数据 | 频率 | 指令码 | 说明 |
|------|------|--------|------|
| RobotState | 50Hz | 0x0901 | 电池、位置、IMU等 |
| JointAngle | 100Hz | 0x0902 | 12个关节角度 |
| JointVel | 100Hz | 0x0903 | 12个关节角速度 |

**关键代码**: `src/gateway/udp_controller.py`

### 5.2 核心模块

| 模块 | 路径 | 功能 |
|------|------|------|
| UDPMotionController | src/gateway/udp_controller.py | UDP运动控制、状态接收 |
| WebSocketGateway | src/gateway/websocket_client.py | WebSocket数据上报 |
| PtzController | src/gateway/ptz_controller.py | 云台HTTP控制 |
| TemperatureMonitor | src/perception/temperature_monitor.py | 双级告警温度监测 |
| SimulationDataGenerator | src/services/simulation_generator.py | 模拟数据生成 |
| RealBodyData | src/services/real_body_data.py | 物理模型本体数据 |
| MonitorServer | monitor_platform/server.py | 监测平台FastAPI服务 |

---

## 六、WebSocket消息格式

### 6.1 公共字段

```json
{
  "msgId": "uuid",
  "ts": 1735668123456,
  "deviceId": "LITE3-001",
  "type": "system_status",
  "payload": {}
}
```

### 6.2 消息类型

| 类型 | 说明 | 触发条件 |
|------|------|----------|
| `system_status` | 系统状态 | 每5秒定时上报 |
| `inspection_result` | 巡检结果 | 检测到缺陷时 |
| `temperature_alert` | 温度告警 | 超过阈值时 |
| `crack_alert` | 裂缝告警 | 检测到≥0.1mm裂缝 |
| `heartbeat` | 心跳包 | 每30秒 |

详细消息格式见 [02-接口协议与数据规范.md](docs/01-技术方案/02-接口协议与数据规范.md)

---

## 七、配置文件

### 7.1 主要配置项

```yaml
# config/inspection_config.yaml
network:
  robot_motion:
    ip: "192.168.1.103"    # 运动主机IP
    port: 43893             # UDP端口
  ptz:
    base_url: "http://192.168.1.108"
  websocket:
    server_url: "ws://MONITOR_HOST:8765/ws"  # 部署时替换为笔记本IP
  monitor:
    http_port: 8000
    ws_port: 8765

camera:
  streams:
    visible_light_main: "rtsp://admin:123456@192.168.1.108:554/id=1&type=0"
    thermal: "rtsp://admin:123456@192.168.1.108:554/id=2&type=0"

perception:
  temperature:
    warn_threshold: 45.0
    critical_threshold: 50.0
```

---

## 八、故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| WebSocket连接失败 | 未修改MONITOR_HOST | `sed -i 's|MONITOR_HOST|<IP>|' config/inspection_config.yaml` |
| 监测平台无数据 | 感知主机未启动 | 检查run_demo.py是否在运行 |
| 端口被占用 | 其他服务占用 | `netstat -ano | findstr :8765` 终止进程 |
| UDP收不到数据 | 运动主机未配置发送地址 | 检查运动主机UDP配置 |

---

## 九、文档索引

| 文档 | 说明 |
|------|------|
| [01-系统架构与代码规范](docs/01-技术方案/01-系统架构与代码规范.md) | 架构设计、代码规范 |
| [02-接口协议与数据规范](docs/01-技术方案/02-接口协议与数据规范.md) | WebSocket/UDP协议详解 |
| [03-部署运维与故障排查](docs/01-技术方案/03-部署运维与故障排查.md) | 部署流程、故障处理 |
| [04-测试验收标准](docs/01-技术方案/04-测试验收标准.md) | 测试用例、验收标准 |
| [05-项目标准化说明](docs/01-技术方案/05-项目标准化说明.md) | 项目结构、打包规范 |
| [参考资料](docs/00-参考资料/) | 官方手册、协议文档 |

---

## 十、GitHub仓库

- **项目地址**: https://github.com/CosmicVortex/lite3-power-inspection
- **部署包下载**: OpenClaw Launch download API

---

*项目版本: V1.7 | 编制日期: 2025-09-16 | 编制人: 陈伟*
