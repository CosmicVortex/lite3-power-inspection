# 数尔 WEB2.0 云台控制协议参考

> 来源：绝影Lite3电力巡检演示项目技术实施方案V3.1

## 协议概览

| 项目 | 值 |
|------|-----|
| 默认IP | 192.168.1.108 |
| 默认账号 | admin / 123456 |
| API前缀 | /merlin |
| 鉴权方式 | HTTP Basic Auth + Session 头 |
| 心跳间隔 | 10s |
| Session有效期 | 30s |

## 核心接口清单

| 命令字 | 方法 | URL示例 | 关键参数 |
|--------|------|---------|----------|
| 登录 | GET | `/merlin/Login.cgi?Type=WEB&Expires=30` | Basic Auth，返回Session |
| 心跳 | GET | `/merlin/Heartbeat.cgi` | Session头，10s间隔 |
| 角度控制 | POST | `/merlin/SetPtzangle.cgi` | `{"Angle":{"yaw":45,"pitch":-30,"roll":0}}` |
| 状态获取 | GET | `/merlin/GetFlyStateInfo.cgi` | 返回 zoom/yaw/pitch/roll |
| 变倍控制 | GET | `/merlin/PtzCtrl.cgi?operation=10&speed=5` | operation 0-12, speed 1-8 |
| 直接变倍 | GET | `/merlin/ZoomCtrl.cgi?zoom=10&channelno=0` | zoom 1-10 |
| 方向控制 | POST | `/merlin/SetPtzDirection.cgi?channel=0` | `{"Direction":{"ptz_opt":"left","speed":5}}` |
| 激光测距开关 | POST | `/merlin/SetLaserRanging.cgi?channel=0` | `{"Laser_ranging":{"Enable":1}}` |
| 激光距离获取 | POST | `/merlin/GetLaserDistance.cgi?channel=0` | 返回 Distance（米） |
| 设备状态 | GET | `/merlin/GetDeviceState.cgi` | 返回 CPU/MEM/存储 |
| 焦距获取 | GET | `/merlin/GetFocusInfo.cgi?channel=0` | 返回 Elf（实际焦距=Elf/1000 mm） |

## 角度与变倍范围

| 参数 | 范围 |
|------|------|
| 航向角 yaw | -280° ~ 280° |
| 俯仰角 pitch | -115° ~ 40°（控制）/ -105° ~ 40°（反馈） |
| 横滚角 roll | 不支持，默认 0 |
| 变倍倍率 | 1 ~ 10（光学）+ 16× 数字（混合最大 80×） |
| 方向速度 | 1 ~ 20 |

## MerlinSession 封装示例

```python
from ptz_client import MerlinSession

# 初始化云台会话
ptz = MerlinSession(
    base_url="http://192.168.1.108",
    username="admin",
    password="123456",
    heartbeat_interval=10.0
)

# 登录并启动心跳
ptz.login()
ptz.start_heartbeat()

# 角度控制（对准沙盘裂缝模块）
ptz.set_ptz_angle(yaw=45, pitch=-30, roll=0)

# 变倍控制（广角巡检 → 望远精细检测）
ptz.zoom_ctrl(zoom=1)   # 广角巡检
# ... 发现疑似缺陷后 ...
ptz.zoom_ctrl(zoom=10)  # 10倍变焦精细检测

# 获取当前云台状态
state = ptz.get_fly_state_info()
# 返回: {"CamerInfo":{"zoom":10}, "FlyInfo":{"pitch":-30,"roll":0,"yaw":45}}
```

## RTSP 视频流地址

| 流 | 地址 | 用途 |
|----|------|------|
| 可见光主码流 | `rtsp://192.168.1.108:554/id=1&type=0` | 裂缝检测 + 高清预览（最高4K） |
| 可见光辅码流 | `rtsp://192.168.1.108:554/id=1&type=1` | 低带宽预览 |
| 热成像码流 | `rtsp://192.168.1.108:554/id=2&type=0` | 温度监测 + 热成像预览 |

## RTSP 预览验证

```python
from ptz_preview_rtsp import preview_rtsp

# 预览可见光主码流
preview_rtsp("rtsp://192.168.1.108:554/id=1&type=0", transport="tcp", low_latency=True)

# 预览热成像码流
preview_rtsp("rtsp://192.168.1.108:554/id=2&type=0", transport="tcp", low_latency=True)
```
