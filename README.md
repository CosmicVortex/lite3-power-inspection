# 绝影Lite3 电力巡检系统

<div align="center">

![绝影Lite3机器狗](docs/assets/03-绝影Lite3机器狗.jpg)

**广西电力职业技术学院 · 2026年全国职业院校技能大赛项目**

基于云深处绝影Lite3专业版四足机器人与数尔安防双光谱云台相机的智能电力巡检解决方案

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#license)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-1.7-brightgreen.svg)](#版本信息)
[![Status](https://img.shields.io/badge/Status-Deployment_Ready-success.svg)](#快速开始)

</div>

---

## 一、项目概述

### 1.1 项目背景

本项目面向**2026年全国职业院校技能大赛**——机器狗电力巡检赛项，基于云深处科技绝影Lite3专业版四足机器人平台，集成数尔安防SR-UPA810T609双光谱云台相机，实现抽水蓄能电站沙盘模型的自动化电力巡检演示。

### 1.2 核心目标

| 目标类型 | 具体指标 | 完成状态 |
|----------|----------|----------|
| 裂缝检测 | 自动识别 ≥0.1mm 混凝土裂缝，测量误差 <0.02mm | ✅ 已完成 |
| 温度监测 | 双级告警（45℃预警 / 50℃告警），测温精度 ±1℃ | ✅ 已完成 |
| 演示流程 | 完整12分钟标准化演示流程 | ✅ 已完成 |
| 平台对接 | WebSocket实时数据上报，HTTP REST接口 | ✅ 已完成 |
| 环境适配 | 支持模拟/混合/真实三级模式切换 | ✅ 已完成 |

### 1.3 团队成员

| 成员 | 角色 | 主要职责 |
|------|------|----------|
| 王荣吉 | 环境工程师 | 现场测试环境搭建（地垫、踏板、台阶、模拟水泥面） |
| 李章平 | 硬件工程师 | 环境搭建、云台硬件集成、支架设计 |
| 陈伟 | 演示工程师 | 机器狗操作、演示执行、软件集成 |
| 陈自立 | 算法工程师 | 裂缝检测算法、温度监测算法、软件联调 |

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

### 3.1 双部署架构

| 部署位置 | 服务 | IP地址 | 端口 |
|---------|------|--------|------|
| **感知主机** (Jetson NX) | 巡检程序、AI推理、数据采集 | 192.168.1.103 | 43893/8765 |
| **监测平台** (笔记本) | FastAPI服务、Web界面 | localhost | 8000/8765 |

### 3.2 核心参数

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

### 3.3 演示模式

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

## 四、技术实现

### 4.1 UDP数据接收

感知主机通过UDP从运动主机接收真实本体数据：

| 数据 | 频率 | 指令码 | 说明 |
|------|------|--------|------|
| RobotState | 50Hz | 0x0901 | 电池、位置、IMU等 |
| JointAngle | 100Hz | 0x0902 | 12个关节角度 |
| JointVel | 100Hz | 0x0903 | 12个关节角速度 |

**关键代码**: `src/gateway/udp_controller.py`

### 4.2 核心模块

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

## 五、WebSocket消息格式

### 5.1 公共字段

```json
{
  "msgId": "uuid",
  "ts": 1735668123456,
  "deviceId": "LITE3-001",
  "type": "system_status",
  "payload": {}
}
```

### 5.2 消息类型

| 类型 | 说明 | 触发条件 |
|------|------|----------|
| `system_status` | 系统状态 | 每5秒定时上报 |
| `inspection_result` | 巡检结果 | 检测到缺陷时 |
| `temperature_alert` | 温度告警 | 超过阈值时 |
| `crack_alert` | 裂缝告警 | 检测到≥0.1mm裂缝 |
| `heartbeat` | 心跳包 | 每30秒 |

详细消息格式见 [02-接口协议与数据规范.md](docs/01-技术方案/02-接口协议与数据规范.md)

---

## 六、配置文件

### 6.1 主要配置项

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

## 七、故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| WebSocket连接失败 | 未修改MONITOR_HOST | `sed -i 's|MONITOR_HOST|<IP>|' config/inspection_config.yaml` |
| 监测平台无数据 | 感知主机未启动 | 检查run_demo.py是否在运行 |
| 端口被占用 | 其他服务占用 | `netstat -ano | findstr :8765` 终止进程 |
| UDP收不到数据 | 运动主机未配置发送地址 | 检查运动主机UDP配置 |

---

## 八、文档索引

| 文档 | 说明 |
|------|------|
| [01-系统架构与代码规范](docs/01-技术方案/01-系统架构与代码规范.md) | 架构设计、代码规范 |
| [02-接口协议与数据规范](docs/01-技术方案/02-接口协议与数据规范.md) | WebSocket/UDP协议详解 |
| [03-部署运维与故障排查](docs/01-技术方案/03-部署运维与故障排查.md) | 部署流程、故障处理 |
| [04-测试验收标准](docs/01-技术方案/04-测试验收标准.md) | 测试用例、验收标准 |
| [05-项目标准化说明](docs/01-技术方案/05-项目标准化说明.md) | 项目结构、打包规范 |
| [参考资料](docs/00-参考资料/) | 官方手册、协议文档 |

---

## 九、GitHub仓库

- **项目地址**: https://github.com/CosmicVortex/lite3-power-inspection
- **部署包下载**: OpenClaw Launch download API

---

*项目版本: V1.7 | 编制日期: 2025-09-16 | 编制人: 陈伟*
