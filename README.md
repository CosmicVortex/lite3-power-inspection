# 绝影Lite3 电力巡检演示方案

本项目为广西电力职院机器狗电力巡检国赛项目，基于云深处绝影Lite3专业版机器狗实现电力设施巡检演示。

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/CosmicVortex/lite3-power-inspection.git
cd lite3-power-inspection

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑.env文件，配置IP地址等参数

# 5. 运行演示
python3 src/app/main.py --demo
```

详细指南请参考 [快速开始指南](docs/01-技术方案/04-快速开始指南.md)

## 文档导航

- [系统架构设计](docs/01-技术方案/01-系统架构设计.md)
- [API接口文档](docs/01-技术方案/02-API接口文档.md)
- [开发环境搭建指南](docs/01-技术方案/03-开发环境搭建指南.md)
- [项目实施规划书](docs/03-项目管理/03-项目实施规划书.md)

## 项目结构

```
lite3-power-inspection/
├── docs/                      # 项目文档
│   ├── 00-参考资料/           # 官方手册PDF
│   ├── 01-技术方案/           # 技术文档
│   ├── 03-项目管理/           # 项目管理文档
│   └── assets/                # 图片资源
├── src/                       # 源代码
│   ├── app/                   # 应用层
│   ├── perception/            # 感知层
│   ├── gateway/               # 网关层
│   └── storage/               # 存储层
├── models/                    # 模型文件
├── config/                    # 配置文件
├── data/                      # 数据目录
├── tests/                     # 测试代码
├── requirements.txt           # Python依赖
└── README.md                  # 项目说明
```

## 技术栈

- **硬件**: 绝影Lite3专业版 (Jetson NX + RK3588)
- **算法**: YOLOv8-s + U-Net, TensorRT INT8
- **通信**: WebSocket + UDP + RTSP
- **语言**: Python 3.8+

## 许可

MIT License
