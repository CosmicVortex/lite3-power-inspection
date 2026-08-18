# 配置系统

## 配置文件说明

### robot_config.yaml
机器狗基础配置，包含连接参数、运动限制等。

```yaml
# 机器狗连接配置
robot:
  host: "192.168.1.100"  # 运动主机IP
  port: 43893            # UDP端口
  heartbeat_interval: 0.1  # 心跳间隔(秒)

# 运动参数
motion:
  max_velocity: 1.0      # 最大速度(m/s)
  max_angle: 30.0        # 最大转向角度(度)
  step_height: 0.15      # 步高(m)

# 安全参数
safety:
  emergency_stop: true   # 启用急停
  collision_threshold: 0.5  # 碰撞检测阈值
```

### inspection_scenarios.yaml
巡检场景配置，定义检查点、任务类型等。

```yaml
# 巡检场景
inspection:
  name: "变电站A区巡检"
  checkpoints:
    - id: CP01
      position: [2.5, 3.0, 0.0]
      type: "meter_reading"
      target: "高压开关柜"
    - id: CP02
      position: [5.0, 2.0, 0.0]
      type: "thermal_check"
      target: "变压器"
    - id: CP03
      position: [3.0, 5.0, 0.0]
      type: "indicator_check"
      target: "配电柜"

  # 任务顺序
  task_sequence:
    - CP01
    - CP02
    - CP03
    - CP01  # 循环巡检
```

### competition_params.yaml
竞赛参数配置，调整评分相关参数。

```yaml
# 竞赛参数
competition:
  max_time: 300          # 最大时间(秒)
  score_weights:
    completeness: 30
    accuracy: 25
    stability: 15
    timeliness: 15
    innovation: 10
    documentation: 5

  # 性能要求
  requirements:
    min_accuracy: 0.95   # 最低识别准确率
    max_response_time: 5 # 最大响应时间(秒)
```

## 使用说明

1. 复制示例配置
```bash
cp config/robot_config.yaml.example config/robot_config.yaml
cp config/inspection_scenarios.yaml.example config/inspection_scenarios.yaml
```

2. 根据实际情况修改配置

3. 运行时指定配置文件
```bash
python src/main.py --config config/inspection_scenarios.yaml
```
