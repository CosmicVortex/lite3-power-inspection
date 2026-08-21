# 绝影Lite3监测平台 - 部署说明

## 快速部署

### Windows
双击运行：
```
scripts\deploy_oneclick.bat
```

### Linux/Mac
```bash
chmod +x scripts/deploy_oneclick.sh
./scripts/deploy_oneclick.sh
```

### Python直接运行
```bash
python scripts/deploy_oneclick.py
```

---

## 部署流程

脚本会自动执行以下步骤：

1. **环境检查** - 检查Python版本
2. **前端构建** - 使用pnpm构建Vue3前端（如已安装）
3. **依赖安装** - 自动安装Python依赖
4. **服务启动** - 启动FastAPI后端服务器

---

## 访问地址

部署成功后：

- **Web界面**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8765/ws

---

## 手动部署

如需手动控制部署流程：

### 1. 构建前端（需要Node.js和pnpm）
```bash
cd frontend
pnpm install
pnpm build
```

### 2. 安装Python依赖
```bash
pip install -r requirements.txt
pip install -r monitor_platform/requirements.txt
```

### 3. 启动服务
```bash
python monitor_platform/server.py
```

---

## 依赖要求

### 必须
- Python 3.8+
- pip

### 可选（用于前端构建）
- Node.js 18+
- pnpm 8+

---

## 问题排查

### 前端构建失败
```bash
cd frontend
pnpm approve-builds  # 批准构建脚本
pnpm install --no-frozen-lockfile
pnpm build
```

### Python依赖安装失败
```bash
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

### 端口冲突
修改 `monitor_platform/server.py` 中的端口号：
```python
WS_PORT = 8765  # WebSocket端口
HTTP_PORT = 8000  # HTTP端口
```

---

## 版本信息

- 系统版本: V1.7
- 前端框架: Vue 3.5 + Element Plus 2.13
- 后端框架: FastAPI + WebSocket
- 更新日期: 2025-09-16
