# 绝影Lite3 电力巡检演示系统

> 职业高校竞赛用抽水蓄能电站机器狗移动巡检演示系统

---

## 📋 项目概述

| 项目 | 内容 |
|------|------|
| **项目名称** | 广西电力职院机器狗电力巡检国赛 |
| **硬件平台** | 云深处绝影Lite3专业版 + 数尔安防双光谱云台 |
| **演示目标** | 混凝土裂缝检测（≥0.1mm）、温度监测（双级告警） |
| **演示时长** | 约 12 分钟 |
| **技术方案** | [完整实施方案 V3.1](docs/technical/techspec.pdf) |

---

## 🏗️ 系统架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   绝影Lite3     │────▶│   双光谱云台    │────▶│   监测平台      │
│   (Jetson NX)   │     │   (数尔安防)    │     │   (第三方)      │
│                 │     │                 │     │                 │
│ • 12自由度      │     │ • 8MP可见光     │     │ • RTSP视频流    │
│ • 21 TOPS算力   │     │ • 640×512红外   │     │ • 数据接收      │
│ • WiFi单链路    │     │ • 三轴增稳      │     │ • 轨迹回放      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 📁 文档导航

### 技术方案
- [技术实施方案 V3.1](docs/technical/techspec.pdf) - 完整技术文档（40页）
- [云台控制协议](docs/technical/ptz-protocol.md) - 数尔WEB2.0协议速查

### 竞赛相关
- [竞赛任务书](docs/competition/brief.md) - 需求与范围
- [演示场景设计](docs/competition/scenarios.md) - 12分钟流程脚本
- [评分标准](docs/competition/scoring.md) - 详细评分细则

### 项目信息
- [物料清单](docs/project/bom.md) - 硬件采购与加工跟踪
- [团队分工](docs/project/team.md) - 成员职责

---

## 🚀 快速开始

### 环境准备
```bash
# 1. 克隆仓库
git clone https://github.com/CosmicVortex/lite3-power-inspection.git
cd lite3-power-inspection

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置参数
cp config/inspection_config.yaml.example config/inspection_config.yaml
# 编辑配置文件，设置IP地址等参数

# 4. 运行测试
python -m pytest tests/
```

### 运行演示
```bash
# 仿真模式
python src/main.py --mode=simulate

# 实机模式
python src/main.py --mode=real
```

---

## 📊 开发进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1: 基础框架 | ✅ 完成 | 仓库架构、文档体系 |
| Phase 2: 上装集成 | 🔄 进行中 | 支架设计、相机安装 |
| Phase 3: 算法开发 | ⏳ 待开始 | YOLOv8+U-Net训练 |
| Phase 4: 通信对接 | ⏳ 待开始 | WebSocket网关开发 |
| Phase 5: 联调测试 | ⏳ 待开始 | 沙盘环境测试 |

---

## 🔗 相关链接

- [项目详细方案（飞书）](https://gonghanginfo.feishu.cn/docx/ArWjdagoSo4GjQxkUZBcgCSunNg)
- [云深处科技官网](https://www.deeprobotics.cn)
- [绝影Lite3 GitHub](https://github.com/cloudsers/joy-ai-kit)

---

## 📄 License

MIT License
