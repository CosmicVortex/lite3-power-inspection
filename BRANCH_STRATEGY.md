# Git 分支策略

## 分支命名规范

```
feature/<模块>-<功能>    # 新功能开发
bugfix/<问题描述>        # Bug修复
hotfix/<紧急修复>        # 紧急修复
docs/<文档类型>          # 文档更新
release/v<版本号>        # 发布分支
```

## 工作流

```
main (生产) ← release/v* ← feature/*
                    ↑
              hotfix/*
```

1. **main**: 稳定可运行的版本，用于竞赛演示
2. **develop**: 日常开发分支（可选，当前单开发者可省略）
3. **feature/***: 功能开发，完成后合并到main
4. **hotfix/***: 紧急修复，直接从main创建

## 提交规范 (Conventional Commits)

```
<type>(<scope>): <subject>

feat(motion): 添加巡检路径规划算法
fix(perception): 修复仪表识别误检问题
docs(readme): 更新项目结构说明
test(inspection): 增加异常检测单元测试
```

类型说明：
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档变更
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具链变更
