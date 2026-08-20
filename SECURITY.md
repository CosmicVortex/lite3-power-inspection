# 安全政策

## 支持版本

| 版本 | 状态 | 支持截止 |
|------|------|----------|
| V1.7 | ✅ 最新 | - |
| V1.6 | ⚠️ 维护中 | 2025-12-31 |

## 报告漏洞

**请勿通过GitHub Issues公开报告安全漏洞。**

请通过以下方式报告：
- GitHub Security Advisory: https://github.com/CosmicVortex/lite3-power-inspection/security/advisories/new
- 邮件: [REDACTED_SK_KEY]

## 安全最佳实践

### 依赖安全
- 定期更新依赖包
- 使用 `pip audit` 检查已知漏洞
- 不要在生产环境使用开发依赖

### 凭证管理
- 敏感信息（密码、密钥）存储在 `.env` 文件中
- 将 `.env` 添加到 `.gitignore`
- 不要硬编码凭证

### 网络安全
- 使用TLS加密通信
- 验证输入数据
- 实施访问控制

## 安全更新

我们会尽快发布安全更新。受影响的用戶应：
1. 立即升级到最新版本
2. 轮换所有相关凭证
3. 检查日志中的异常活动
