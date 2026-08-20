# 绝影Lite3项目 - DOCX转换指南

## 快速开始

### 1. 安装依赖

```bash
# 方式一：使用setup脚本（推荐）
bash scripts/setup_docx_conversion.sh

# 方式二：手动安装
sudo apt-get install pandoc
uv pip install python-docx
```

### 2. 转换文档

```bash
# 批量转换所有技术文档
python3 scripts/convert_docs_to_docx.py
```

### 3. 查看结果

```bash
ls -lh deliverables/docx/
```

### 4. 创建交付包

```bash
python3 scripts/create_delivery_package.py
```

---

## 文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `templates/commercial.docx` | 商业级DOCX模板 |
| `deliverables/docx/` | 转换后的DOCX文件 |
| `scripts/setup_docx_conversion.sh` | 环境准备脚本 |
| `scripts/convert_docs_to_docx.py` | 批量转换脚本 |
| `scripts/create_delivery_package.py` | 交付包创建脚本 |

---

## 转换配置

### 页面设置

- 边距：上2.5cm，下2.5cm，左3cm，右3cm
- 字体：正文宋体12pt，标题黑体
- 行距：1.5倍

### 元数据

- 作者：陈伟
- 日期：自动生成
- 关键词：电力巡检、机器狗、裂缝检测、温度监测

---

## 兼容性处理

### 已处理的问题

| 问题类型 | 处理方式 |
|----------|----------|
| Mermaid图表 | 保持原样，需手动转换 |
| ASCII艺术图 | 转换为文字描述 |
| HTML标签 | 自动移除或替换 |
| Emoji表情 | 转换为文字描述 |

### 注意事项

1. **Mermaid图表**：当前转换为文字描述，未来可集成mermaid-cli
2. **图片引用**：请确保图片路径正确
3. **表格样式**：转换后可能需要手动调整

---

## 故障排查

### 问题：pandoc未找到

```bash
sudo apt-get install pandoc
```

### 问题：python-docx导入错误

```bash
uv pip install python-docx
```

### 问题：转换失败

检查Markdown语法：
```bash
pandoc docs/01-技术方案/01-系统架构设计.md --debug
```

---

## 商业级文档标准

### 格式要求

- [ ] 页面边距符合标准
- [ ] 正文字体为宋体12pt
- [ ] 标题字体为黑体
- [ ] 行间距1.5倍
- [ ] 自动生成目录
- [ ] 页眉页脚完整

### 内容要求

- [ ] 版本号统一（V1.7）
- [ ] 编制日期统一（2025-09-16）
- [ ] 图表编号连续
- [ ] 参考文献完整
- [ ] 无错别字和语法错误

---

*文档版本：V1.7*
*更新日期：2025-09-16*
