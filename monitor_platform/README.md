# 监测平台增强版使用说明

## 新增功能

### 1. 机器狗状态显示

实时显示以下状态信息：

| 指标 | 说明 | 颜色标识 |
|------|------|----------|
| 电量 | 电池剩余电量（%） | <20%红色，<50%橙色 |
| CPU温度 | 处理器温度（℃） | >60℃红色，>50℃橙色 |
| GPU负载 | 图形处理器使用率（%） | 蓝色进度条 |
| 内存使用 | 内存占用率（%） | 紫色进度条 |
| 运行状态 | idle/moving/inspecting | 文字显示 |
| 当前位置 | 世界坐标(x, y) | 米为单位 |
| 巡检进度 | 当前航点/总航点数 | 圆点进度条 |

### 2. 运动控制

控制面板提供以下运动控制功能：

| 按钮 | 功能 | UDP指令 |
|------|------|---------|
| ↑ 前 | 向前移动 | CMD_VELOCITY (vy=-0.5) |
| ↓ 后 | 向后移动 | CMD_VELOCITY (vy=0.5) |
| ← 左 | 向左移动 | CMD_VELOCITY (vx=-0.5) |
| 右 → | 向右移动 | CMD_VELOCITY (vx=0.5) |
| ↰ 左转 | 逆时针旋转 | CMD_VELOCITY (vw=-0.5) |
| ↱ 右转 | 顺时针旋转 | CMD_VELOCITY (vw=0.5) |
| ⬆ 起立 | 机器狗起立 | CMD_STAND_UP |
| ⬇ 趴下 | 机器狗趴下 | CMD_STAND_DOWN |
| 🛑 急停 | 紧急停止 | CMD_EMERGENCY_STOP |

**注意**: 运动控制需要机器狗处于可控制状态，且网络连接正常。

### 3. 演示数据增强

点击"发送巡检数据"按钮将生成：
- 随机裂缝检测结果（宽度0.1-1.0mm，置信度0.7-0.98）
- 随机温度数据（25-55℃，含WARN/CRITICAL状态）
- 随机航点位置（WP001-WP005）
- 随机云台角度和变焦倍数

点击"更新状态"按钮将模拟：
- 电量变化（60-95%）
- CPU温度变化（35-55℃）
- GPU负载变化（20-80%）
- 航点推进

## API接口

### WebSocket消息类型

| 类型 | 方向 | 说明 |
|------|------|------|
| inspection_result | 机器狗→平台 | 巡检结果上报 |
| temperature_alert | 机器狗→平台 | 温度告警上报 |
| crack_alert | 机器狗→平台 | 裂缝告警上报 |
| system_status | 机器狗→平台 | 系统状态上报 |
| heartbeat | 机器狗→平台 | 心跳包 |
| robot_status | 平台→浏览器 | 机器狗状态广播 |
| inspection_result | 平台→浏览器 | 巡检结果广播 |
| temperature_alert | 平台→浏览器 | 温度告警广播 |
| crack_alert | 平台→浏览器 | 裂缝告警广播 |

### HTTP接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/status | GET | 系统统计 |
| /api/robot/status | GET | 机器狗状态 |
| /api/inspections | GET | 巡检记录列表 |
| /api/alerts | GET | 告警列表 |
| /api/alert/ack | POST | 确认告警 |
| /api/demo/send | POST | 发送演示数据 |
| /api/demo/send_status | POST | 更新状态数据 |
| /api/control/motion | POST | 运动控制 |
| /api/control/stand_up | POST | 起立控制 |
| /api/control/stand_down | POST | 趴下控制 |
| /api/control/emergency_stop | POST | 急停控制 |

## 故障排查

| 现象 | 可能原因 | 解决方案 |
|------|----------|----------|
| 控制无响应 | UDP连接失败 | 检查机器狗IP和端口 |
| 状态不更新 | 未收到system_status | 检查WebSocket连接 |
| 演示数据异常 | 服务器错误 | 查看终端日志 |

## 版本信息

- 版本: V1.7
- 更新日期: 2025-09-16
- 依赖: websockets, fastapi, uvicorn, pydantic
