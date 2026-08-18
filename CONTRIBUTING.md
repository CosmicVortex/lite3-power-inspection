# Git 工作流规范

## 分支策略

```
main (生产) ← develop (开发) ← feature/* (功能)
```

### 分支命名
- `main` - 生产分支，仅接受 merge
- `develop` - 开发分支，日常开发在此进行
- `feature/<功能>` - 新功能开发分支
- `hotfix/<问题>` - 紧急修复分支

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>

type: feat, fix, docs, style, refactor, test, chore
scope: 模块名称（可选）
subject: 简要描述变更
```

### 示例
```
feat(motion): 添加A*路径规划算法
fix(ptz): 修复云台角度偏移问题
docs: 更新技术实施方案V3.1
```

## 工作流程

```
1. 从 develop 创建功能分支
2. 在功能分支上进行开发
3. 提交 commit，遵循提交规范
4. 推送分支到远程
5. 创建 Pull Request 到 develop
6. 代码审查通过后合并
7. 定期从 develop 同步到功能分支
```
