# 贡献指南

## 开发环境准备

1. 克隆仓库
```bash
git clone https://github.com/CosmicVortex/lite3-power-inspection.git
cd lite3-power-inspection
```

2. 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
pip install -r requirements-gpu.txt  # 如需GPU支持
```

4. 运行测试
```bash
pytest tests/ -v
```

## 代码规范

- 遵循 [PEP 8](https://peps.python.org/pep-0008/) 规范
- 使用 [Black](https://black.readthedocs.io/) 格式化代码
- 添加类型注解
- 编写文档字符串

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type类型**：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档变更
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具

**示例**：
```bash
git commit -m "feat(perception): 添加U-Net裂缝分割算法"

git commit -m "fix(gateway): 修复WebSocket断连问题

- 添加自动重连机制
- 增加连接超时配置"
```

## 提交PR流程

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/your-feature`)
3. 提交变更 (`git commit -m 'feat: 添加新功能'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建Pull Request

## 文档规范

- 所有文档使用中文
- 版本号统一为V1.7
- 编制日期格式：YYYY-MM-DD
- DOC编号格式：DOC-XXXX-NNN

## 问题反馈

请通过GitHub Issues反馈问题，包含：
- 问题描述
- 复现步骤
- 预期行为 vs 实际行为
- 环境信息（操作系统、Python版本等）
