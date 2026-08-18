# 云台控制协议参考

> 数尔安防双光谱云台 WEB2.0 协议

## 协议概览

| 项目 | 值 |
|------|-----|
| 默认IP | 192.168.1.108 |
| 默认账号 | admin / 123456 |
| API前缀 | /merlin |
| 鉴权方式 | HTTP Basic Auth + Session 头 |
| 心跳间隔 | 10s |
| Session有效期 | 30s |

## 核心接口

| 命令字 | 方法 | URL示例 | 关键参数 |
|--------|------|---------|----------|
| 登录 | GET | `/merlin/Login.cgi?Type=WEB&Expires=30` | Basic Auth，返回Session |
| 心跳 | GET | `/merlin/Heartbeat.cgi` | Session头，10s间隔 |
| 角度控制 | POST | `/merlin/SetPtzangle.cgi` | `{"Angle":{"yaw":45,"pitch":-30}}` |
| 状态获取 | GET | `/merlin/GetFlyStateInfo.cgi` | 返回 zoom/yaw/pitch/roll |
| 直接变倍 | GET | `/merlin/ZoomCtrl.cgi?zoom=10` | zoom 1-10 |
| 方向控制 | POST | `/merlin/SetPtzDirection.cgi` | `{"Direction":{"ptz_opt":"left"}}` |

## 角度范围

| 参数 | 范围 |
|------|------|
| 航向角 yaw | -280° ~ 280° |
| 俯仰角 pitch | -115° ~ 40° |
| 横滚角 roll | 不支持 |
| 变倍倍率 | 1 ~ 10（光学）+ 16× 数字 |

## RTSP 视频流地址

| 流 | 地址 | 用途 |
|----|------|------|
| 可见光主码流 | `rtsp://192.168.1.108:554/id=1&type=0` | 裂缝检测 + 高清预览 |
| 可见光辅码流 | `rtsp://192.168.1.108:554/id=1&type=1` | 低带宽预览 |
| 热成像码流 | `rtsp://192.168.1.108:554/id=2&type=0` | 温度监测 |

## Python 封装示例

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

# 角度控制
ptz.set_ptz_angle(yaw=45, pitch=-30, roll=0)

# 变倍控制（广角→精细检测）
ptz.zoom_ctrl(zoom=1)   # 广角巡检
ptz.zoom_ctrl(zoom=10)  # 10倍变焦精细检测

# 获取云台状态
state = ptz.get_fly_state_info()
```

## 网络配置

```
设备              IP              备注
─────────────────────────────────────────────
Lite3 机器狗      192.168.1.120   静态，WiFi接入
双光谱云台        192.168.1.108   静态，出厂默认
监测平台          192.168.1.200   第三方提供
赛场路由器        192.168.1.1     DHCP关闭
```
