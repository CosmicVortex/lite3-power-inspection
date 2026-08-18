# API接口文档

> **文档编号**: 02-API接口文档  
> **版本**: V1.0  
> **更新日期**: 2026-08-18

---

## 一、WebSocket接口

### 1.1 连接信息

| 项目 | 值 |
|------|-----|
| 地址 | ws://192.168.1.200:8765/ws |
| 协议 | WebSocket |
| 编码 | UTF-8 JSON |

### 1.2 消息类型

#### 1.2.1 巡检结果上报

```json
{
  "type": "inspection_result",
  "timestamp": "2026-08-18T10:30:00Z",
  "data": {
    "defect_type": "crack",
    "location": {"x": 120, "y": 340},
    "width_mm": 0.15,
    "length_mm": 45.2,
    "confidence": 0.92,
    "image_url": "http://192.168.1.120:8080/snap/001.jpg",
    "waypoint_id": "WP-03"
  }
}
```

#### 1.2.2 温度告警上报

```json
{
  "type": "temperature_alert",
  "timestamp": "2026-08-18T10:30:00Z",
  "data": {
    "level": "CRITICAL",
    "temperature_c": 52.3,
    "roi": {"x": 100, "y": 200, "w": 50, "h": 50},
    "thermal_image_url": "http://192.168.1.120:8080/thermal/001.jpg",
    "waypoint_id": "WP-05"
  }
}
```

#### 1.2.3 系统状态心跳

```json
{
  "type": "heartbeat",
  "timestamp": "2026-08-18T10:30:00Z",
  "data": {
    "battery_percent": 85,
    "cpu_temp": 45.2,
    "gps": {"lat": 28.228, "lon": 112.938},
    "mode": "INSPECTING"
  }
}
```

---

## 二、HTTP REST接口

### 2.1 云台控制接口

基础URL: `http://192.168.1.108/merlin`

#### 2.1.1 登录

```
GET /Login.cgi?Type=WEB&Expires=30
Authorization: Basic YWRtaW46MTIzNDU2
```

响应:
```
Set-Cookie: MerlinSession=abc123xyz; Path=/merlin
```

#### 2.1.2 心跳

```
GET /Heartbeat.cgi
Cookie: MerlinSession=abc123xyz
```

#### 2.1.3 角度控制

```
POST /SetPtzangle.cgi
Content-Type: application/json
Cookie: MerlinSession=abc123xyz

{
  "Angle": {
    "yaw": 45,
    "pitch": -30,
    "roll": 0
  }
}
```

#### 2.1.4 变倍控制

```
GET /ZoomCtrl.cgi?zoom=10
Cookie: MerlinSession=abc123xyz
```

#### 2.1.5 状态查询

```
GET /GetFlyStateInfo.cgi
Cookie: MerlinSession=abc123xyz
```

响应:
```json
{
  "Zoom": {"zoom": 10},
  "Angle": {"yaw": 45.0, "pitch": -30.0},
  "Status": "OK"
}
```

### 2.2 快照获取接口

```
GET http://192.168.1.120:8080/snap/{alert_id}.jpg
GET http://192.168.1.120:8080/thermal/{alert_id}.jpg
```

---

## 三、UDP指令集

### 3.1 指令格式

简单指令: `[xxxx yyyy zzzz]` (12字节)
- xxxx: 指令码 (uint32_t, 小端序)
- yyyy: 指令值 (uint32_t)
- zzzz: 指令类型 (uint32_t, 0=简单, 1=复杂)

复杂指令: `[xxxx yyyy zzzz data...]`
- data: 数据内容 (最长256字节)

### 3.2 控制指令

| 指令名称 | 指令码 | 说明 |
|----------|--------|------|
| 心跳 | 0x21040001 | 确认连接，频率≥2Hz |
| 起立/趴下 | 0x21010202 | 状态切换 |
| 软急停 | 0x21020C0E | 紧急停止 |
| 回零 | 0x21010C05 | 初始化关节 |
| 进入AI | 0x21010528 | 进入AI状态 |
| 退出AI | 0x2101052B | 退出AI状态 |

### 3.3 速度指令

```
指令码: 0x0103
数据格式: [vx, vy, vw] (每个32位浮点数，小端序)
vx: 前后速度 (m/s, 范围-1.0~1.0)
vy: 左右速度 (m/s, 范围-1.0~1.0)
vw: 旋转速度 (rad/s, 范围-1.0~1.0)
```

### 3.4 关节角度指令

```
指令码: 0x0104
数据格式: [q1, q2, q3, ..., q12] (12个32位浮点数)
qi: 第i个关节的目标角度 (弧度)
```

---

## 四、错误码定义

| 错误码 | 含义 | 处理建议 |
|--------|------|----------|
| 0 | 成功 | - |
| 1001 | 连接超时 | 检查网络 |
| 1002 | Session过期 | 重新登录 |
| 1003 | 指令无效 | 检查指令格式 |
| 1004 | 参数越界 | 检查参数范围 |
| 2001 | 相机离线 | 检查云台连接 |
| 2002 | 视频流断开 | 重连RTSP |
| 3001 | 内存不足 | 释放缓存 |
| 3002 | 模型加载失败 | 检查模型路径 |

---

*文档版本: V1.0 | 更新日期: 2026-08-18*
