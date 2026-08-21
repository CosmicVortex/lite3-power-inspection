# UDP数据接收说明

**版本**: V1.7  
**日期**: 2025-09-21  
**编制人**: 陈伟

---

## 一、UDP通信架构

### 1.1 数据流向

```
┌─────────────────────────────────────────────────────────────────────┐
│                        运动主机 (RK3588)                             │
│                                                                     │
│  发送频率              指令码          数据类型                      │
│  ───────────────────────────────────────────────                    │
│  50 Hz                 0x0901         RobotStateUpload（状态）       │
│  100 Hz                0x0902         RobotJointAngle（关节角度）    │
│  100 Hz                0x0903         RobotJointVel（关节速度）      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ UDP 43893 → 43894
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      感知主机 (Jetson NX)                            │
│                                                                     │
│  UDPMotionController                                               │
│  ├── 发送: 心跳(0x21040001)、控制指令                               │
│  └── 接收: 机器人状态、关节数据                                      │
│           ↓                                                        │
│  RealBodyData                                                      │
│  ├── update_from_udp()  // 从UDP接收真实数据                         │
│  └── get_system_status()  // 获取状态字典                            │
│           ↓                                                        │
│  WebSocketGateway                                                  │
│  └── 发送到监测平台 (ws://<IP>:8765/ws)                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        监测平台 (笔记本)                              │
│                                                                     │
│  WebSocket Server (端口8765)                                        │
│  ├── 接收 system_status 消息                                        │
│  ├── 接收 inspection_result 消息                                    │
│  ├── 接收 temperature_alert 消息                                    │
│  └── 接收 video_frame 消息                                          │
│                                                                     │
│  HTTP Server (端口8000)                                             │
│  └── Web界面实时监控                                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 UDP配置

| 参数 | 值 | 说明 |
|------|-----|------|
| 发送端口 | 43893 | 感知主机→运动主机 |
| 接收端口 | 43894 | 运动主机→感知主机 |
| 目标IP | 192.168.1.103 | 运动主机地址 |
| 心跳间隔 | 0.4秒 (2.5Hz) | 发送频率 |

---

## 二、数据格式解析

### 2.1 RobotStateUpload (0x0901)

**发送频率**: 50 Hz  
**数据大小**: ~170字节

```cpp
struct RobotStateUpload {
    int robot_basic_state;           // 基本运动状态 (0-7)
    int robot_gait_state;            // 当前步态
    int robot_policy_state;          // AI步态状态
    double rpy[3];                   // IMU欧拉角 {roll, pitch, yaw}
    double rpy_vel[3];               // IMU角速度
    double xyz_acc[3];               // IMU加速度
    double pos_world[3];             // 世界坐标 {x, y, yaw}
    double vel_world[3];             // 世界速度
    double vel_body[3];              // 身体速度
    unsigned touch_down_and_stair_trot; // 占位
    bool is_charging;                // 充电状态
    unsigned error_state;            // 占位
    int robot_motion_state;          // 动作状态
    double battery_level;            // 电量 (0-1)
    int task_state;                  // 占位
    bool is_robot_need_move;         // 需要移动保持平衡
    bool zero_position_flag;         // 回零标志
    bool is_after_first_start;       // 首次启动标志
    bool is_voice_ctrl_enable;       // 语音控制使能
    double ultrasound[2];            // 超声波 {前, 后}
};
```

**解析代码** (`src/gateway/udp_controller.py`):

```python
def _parse_robot_state(self, data: bytes):
    offset = 0
    # 解析各字段...
    self.robot_state.battery_level = struct.unpack_from('<d', data, offset)[0] * 100
    self.robot_state.pos_world = struct.unpack_from('<ddd', data, offset)
    # ...
```

### 2.2 RobotJointAngle (0x0902)

**发送频率**: 100 Hz  
**数据大小**: 96字节 (12个double)

```cpp
struct RobotJointAngle {
    double q[12];  // 关节角度 {左hip, 左knee, 左ankle, 右hip, ..., 右front ankle}
};
```

### 2.3 RobotJointVel (0x0903)

**发送频率**: 100 Hz  
**数据大小**: 96字节 (12个double)

```cpp
struct RobotJointVel {
    double dq[12];  // 关节角速度
};
```

---

## 三、部署配置

### 3.1 运动主机配置（必须）

在运动主机上修改UDP发送目标地址：

```bash
# SSH登录运动主机
ssh ysc@192.168.1.103

# 修改UDP发送目标为感知主机IP
# 路径参考: /jy_exe/data/config/motion_config.yaml
# 修改: udp_send_addr: 192.168.1.103
# 修改: udp_send_port: 43894
```

### 3.2 感知主机配置

```yaml
# config/inspection_config.yaml
communication:
  udp:
    motion_ip: "192.168.1.103"
    motion_port: 43893
    receive_port: 43894  # 接收端口
    
  websocket:
    server_url: "ws://<笔记本IP>:8765/ws"
```

### 3.3 启动命令

```bash
# 1. 安装依赖
./scripts/offline_install.sh sensors

# 2. 启动演示（自动接收UDP数据）
python3 src/app/main.py --mode simulation --ws-url ws://<笔记本IP>:8765/ws
```

---

## 四、验证步骤

### 4.1 测试UDP连接

```bash
# 测试运动主机连接
python3 src/gateway/udp_controller.py

# 预期输出:
# 连接成功
# 等待运动主机数据...
# 收到数据 (包数: 50):
#   电量: 95.2%
#   位置: [0.5, 0.5, 0.0]
```

### 4.2 验证数据流

1. 启动监测平台: `./scripts/start_monitor.sh`
2. 启动感知主机: `python3 src/app/main.py --mode simulation --ws-url ws://<IP>:8765/ws`
3. 观察监测平台Web界面，确认实时显示：
   - 电池电量（动态变化）
   - 位置坐标（随运动变化）
   - IMU角度（随姿态变化）
   - 超声波距离

---

## 五、故障排查

| 现象 | 可能原因 | 解决方案 |
|------|----------|----------|
| 收不到UDP数据 | 运动主机未配置发送地址 | 检查运动主机config |
| 数据包丢失 | 网络不稳定 | 检查WiFi信号 |
| 数据解析错误 | 字节序不匹配 | 确认小端序 `<` |
| 端口冲突 | 43894被占用 | `netstat -tlnp \| grep 43894` |

---

*文档版本: V1.7 | 最后更新: 2025-09-21*
