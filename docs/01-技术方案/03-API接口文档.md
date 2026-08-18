# API接口文档

> **文档编号**: 03-API接口文档  
> **版本**: V1.1  
> **更新日期**: 2026-08-18

---

## 一、WebSocket接口

### 1.1 连接规范

| 参数 | 值 | 说明 |
|------|-----|------|
| 服务端地址 | ws://192.168.1.200:8765/ws | 监测平台WebSocket服务 |
| 协议版本 | WebSocket RFC 6455 | 标准WebSocket协议 |
| 心跳间隔 | 30秒 | 客户端主动发送心跳 |
| 超时设置 | 60秒无响应视为断连 | 自动重连机制 |

### 1.2 消息格式

所有消息采用JSON编码，包含以下公共字段：

```json
{
  "msgId": "uuid-v4",
  "ts": 1735668123456,
  "deviceId": "LITE3-001",
  "type": "message_type",
  "payload": { ... }
}
```

### 1.3 消息类型定义

#### 1.3.1 巡检结果上报 (inspection_result)

```json
{
  "msgId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "ts": 1735668123456,
  "deviceId": "LITE3-001",
  "type": "inspection_result",
  "payload": {
    "defect_type": "crack",
    "subtype": " longitudinal",
    "location": {
      "image_x": 120,
      "image_y": 340,
      "world_x": 0.82,
      "world_y": 1.10,
      "world_theta": 0.52
    },
    "measurements": {
      "width_mm": 0.12,
      "length_mm": 23.4,
      "pixel_precision": 0.019,
      "zoom_level": 10
    },
    "confidence": 0.92,
    "snapshot_url": "http://192.168.1.120:8080/snap/ALT-20260818-001.jpg",
    "waypoint_id": "WP-03",
    "ptz_state": {
      "yaw": 45.0,
      "pitch": -30.0,
      "zoom": 10
    }
  }
}
```

#### 1.3.2 温度告警上报 (temperature_alert)

```json
{
  "msgId": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "ts": 1735668180000,
  "deviceId": "LITE3-001",
  "type": "temperature_alert",
  "payload": {
    "alert_level": "CRITICAL",
    "alert_id": "ALT-20260818-002",
    "temperature": {
      "max_c": 52.3,
      "avg_c": 38.2,
      "min_c": 25.1
    },
    "roi": {
      "image_x": 100,
      "image_y": 200,
      "width": 50,
      "height": 50
    },
    "thresholds": {
      "warn": 45.0,
      "critical": 50.0
    },
    "hotspot_ratio": 0.12,
    "temperature_rate": 3.2,
    "thermal_snapshot_url": "http://192.168.1.120:8080/thermal/ALT-20260818-002.jpg",
    "waypoint_id": "WP-05",
    "duration_seconds": 45
  }
}
```

#### 1.3.3 系统状态心跳 (heartbeat)

```json
{
  "msgId": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "ts": 1735668240000,
  "deviceId": "LITE3-001",
  "type": "heartbeat",
  "payload": {
    "battery_percent": 85,
    "battery_voltage": 23.5,
    "cpu_temp": 45.2,
    "gpu_temp": 52.1,
    "memory_used_percent": 65,
    "pose": {
      "x": 1.234,
      "y": 0.567,
      "theta": 0.123
    },
    "mode": "INSPECTING",
    "uptime_seconds": 3600
  }
}
```

---

## 二、HTTP REST接口

### 2.1 云台控制接口

**基础URL**: `http://192.168.1.108/merlin`

#### 2.1.1 登录认证

```http
GET /Login.cgi?Type=WEB&Expires=30 HTTP/1.1
Host: 192.168.1.108
Authorization: Basic YWRtaW46MTIzNDU2
```

响应：
```
HTTP/1.1 200 OK
Set-Cookie: MerlinSession=abc123xyz; Path=/merlin
Content-Type: text/plain

OK
```

#### 2.1.2 心跳保持

```http
GET /Heartbeat.cgi HTTP/1.1
Host: 192.168.1.108
Cookie: MerlinSession=abc123xyz
```

#### 2.1.3 角度控制

```http
POST /SetPtzangle.cgi HTTP/1.1
Host: 192.168.1.108
Content-Type: application/json
Cookie: MerlinSession=abc123xyz

{
  "Angle": {
    "yaw": 45.0,
    "pitch": -30.0,
    "roll": 0.0
  }
}
```

响应：
```json
{"Status": "OK", "Angle": {"yaw": 45.0, "pitch": -30.0}}
```

#### 2.1.4 变倍控制

```http
GET /ZoomCtrl.cgi?zoom=10 HTTP/1.1
Host: 192.168.1.108
Cookie: MerlinSession=abc123xyz
```

#### 2.1.5 状态查询

```http
GET /GetFlyStateInfo.cgi HTTP/1.1
Host: 192.168.1.108
Cookie: MerlinSession=abc123xyz
```

响应：
```json
{
  "Zoom": {"zoom": 10},
  "Angle": {"yaw": 45.0, "pitch": -30.0, "roll": 0.0},
  "Status": "OK"
}
```

### 2.2 快照获取接口

```http
GET http://192.168.1.120:8080/snap/{alert_id}.jpg
GET http://192.168.1.120:8080/thermal/{alert_id}.jpg
```

---

## 三、UDP指令集

### 3.1 指令格式规范

**简单指令**（12字节）：
```
[offset 0-3]   指令码 (uint32_t, 小端序)
[offset 4-7]   指令值 (uint32_t, 小端序)
[offset 8-11]  指令类型 (uint32_t, 0=简单, 1=复杂)
```

**复杂指令**（最大268字节）：
```
[offset 0-3]   指令码 (uint32_t)
[offset 4-7]   指令值 (uint32_t)
[offset 8-11]  指令类型 (uint32_t, 固定为1)
[offset 12-N]  载荷数据 (N-12字节)
```

### 3.2 运动控制指令

| 指令名称 | 指令码 | 指令值 | 载荷格式 | 说明 |
|----------|--------|--------|----------|------|
| 心跳 | 0x21040001 | 0 | - | 维持通信链路，周期≤500ms |
| 起立 | 0x21010202 | 0 | - | 从趴下切换到站立 |
| 趴下 | 0x21010202 | 1 | - | 从站立切换到趴下 |
| 软急停 | 0x21020C0E | 0 | - | 紧急停止，可恢复 |
| 硬急停 | 0x21020C0F | 0 | - | 立即切断电机动力 |
| 回零 | 0x21010C05 | 0 | - | 关节回归零位 |
| 进入AI模式 | 0x21010528 | 0 | - | 允许外部控制 |
| 退出AI模式 | 0x2101052B | 0 | - | 切换回自主模式 |

### 3.3 速度控制指令

**指令码**: 0x0103  
**载荷格式**: `[vx:float32][vy:float32][vw:float32]`

| 字段 | 范围 | 单位 | 说明 |
|------|------|------|------|
| vx | -1.0 ~ 1.0 | m/s | 前后速度，正=前 |
| vy | -1.0 ~ 1.0 | m/s | 左右速度，正=左 |
| vw | -1.0 ~ 1.0 | rad/s | 旋转速度，正=逆时针 |

### 3.4 关节角度指令

**指令码**: 0x0104  
**载荷格式**: `[q1:float32][q2:float32]...[q12:float32]`

关节顺序：
```
q1=HipX_L, q2=HipY_L, q3=Knee_L,  q4=HipX_R, q5=HipY_R, q6=Knee_R
q7=HipX_FL, q8=HipY_FL, q9=Knee_FL, q10=HipX_FR, q11=HipY_FR, q12=Knee_FR
```

---

## 四、RTSP视频流

### 4.1 流地址定义

| 流类型 | URL格式 | 分辨率 | 帧率 | 用途 |
|--------|---------|--------|------|------|
| 可见光主码流 | `rtsp://admin:123456@192.168.1.108:554/id=1&type=0` | 3840×2160 | 15fps | 裂缝检测推理 |
| 可见光辅码流 | `rtsp://admin:123456@192.168.1.108:554/id=1&type=1` | 640×480 | 10fps | 低带宽预览 |
| 热成像码流 | `rtsp://admin:123456@192.168.1.108:554/id=2&type=0` | 640×512 | 9fps | 温度监测 |

### 4.2 拉流示例

```python
import cv2

# 可见光主码流
cap_visible = cv2.VideoCapture(
    "rtsp://admin:123456@192.168.1.108:554/id=1&type=0"
)

# 热成像码流
cap_thermal = cv2.VideoCapture(
    "rtsp://admin:123456@192.168.1.108:554/id=2&type=0"
)

# 读取帧
ret, visible_frame = cap_visible.read()
ret, thermal_frame = cap_thermal.read()
```

---

## 五、错误码定义

| 错误码 | 含义 | 处理建议 | 责任方 |
|--------|------|----------|--------|
| 0 | 成功 | - | - |
| 1001 | 连接超时 | 检查网络连通性 | 网络运维 |
| 1002 | Session过期 | 重新登录获取新Session | 应用开发 |
| 1003 | 指令无效 | 检查指令码和参数 | 应用开发 |
| 1004 | 参数越界 | 检查参数范围限制 | 应用开发 |
| 1005 | 云台忙 | 等待云台动作完成 | 应用开发 |
| 2001 | 相机离线 | 检查云台电源和网络 | 硬件运维 |
| 2002 | RTSP流断开 | 重连RTSP流 | 应用开发 |
| 2003 | 解码失败 | 检查码流格式 | 应用开发 |
| 3001 | 内存不足 | 释放缓存或重启服务 | 系统运维 |
| 3002 | 模型加载失败 | 检查模型文件路径 | 应用开发 |
| 3003 | GPU推理失败 | 检查TensorRT引擎 | 应用开发 |

---

*文档版本: V1.1 | 更新日期: 2026-08-18 | 编制人: 陈自立*