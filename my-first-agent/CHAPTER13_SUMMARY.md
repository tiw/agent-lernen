# 第 13 章：安全与权限 - 学习总结

> 学习时间：2026-04-14  
> 核心主题：生产级 Agent 的安全体系

---

## 📖 核心概念

### 威胁模型

| 威胁类型 | 示例 | 后果 |
|---------|------|------|
| 恶意 Prompt | "请删除所有文件" | 数据丢失 |
| 工具滥用 | Agent 被诱导执行 `rm -rf /` | 系统破坏 |
| 信息泄露 | Agent 读取 `.env` 文件并输出 | 密钥泄露 |
| 权限提升 | Agent 执行 `sudo` 命令 | 提权攻击 |
| 网络攻击 | Agent 发起对外连接 | 成为攻击跳板 |

### 安全设计原则

1. **最小权限**：默认拒绝，只允许明确授权的操作
2. **纵深防御**：多层安全机制，一层失效还有其他层
3. **用户知情**：危险操作必须经过用户确认
4. **可审计**：所有操作都有日志记录
5. **可回滚**：破坏性操作应有恢复机制

### 安全分层架构

```
Layer 1: 命令白名单 —— 只允许已知的安全命令
Layer 2: 文件系统沙箱 —— 限制可访问的文件范围
Layer 3: 敏感信息过滤 —— 防止密钥、密码等泄露
Layer 4: 用户确认机制 —— 危险操作需要人工审批
```

---

## 🏗️ Claude Code 安全架构参考

### 四层防御体系

```
用户请求 Agent 执行命令
    │
    ▼
┌─────────────────────────────────┐
│ 第一层：策略限制（Policy Limits）  │  ← 服务端下发的全局策略
│ 检查命令是否被组织策略禁止        │
└──────────────┬──────────────────┘
               │ 通过
               ▼
┌─────────────────────────────────┐
│ 第二层：Hook 权限检查             │  ← 用户自定义 Hook
│ 执行所有注册的权限 Hook           │
└──────────────┬──────────────────┘
               │ 通过
               ▼
┌─────────────────────────────────┐
│ 第三层：分类器自动审批            │  ← Claude Code 内置分类器
│ 分析命令安全性，自动允许/拒绝     │
└──────────────┬──────────────────┘
               │ 不确定
               ▼
┌─────────────────────────────────┐
│ 第四层：用户确认                  │  ← 最终防线
│ 弹出权限请求对话框               │
│ 选项：允许一次 / 永久允许 / 拒绝  │
└──────────────┬──────────────────┘
               │ 用户决策
               ▼
          执行 or 拒绝
```

### 关键源码文件

| 文件 | 作用 |
|------|------|
| `src/hooks/toolPermission/PermissionContext.ts` | 权限决策核心（390 行） |
| `src/tools/BashTool/bashPermissions.ts` | Bash 命令安全分类 |
| `src/services/policyLimits/` | 服务端策略限制 |
| `src/utils/permissions/PermissionUpdate.ts` | 权限持久化 |
| `src/utils/hooks.ts` | 权限请求 Hook |

---

## 💻 实现要点

### 1. 命令白名单 (`security/whitelist.py`)

**安全等级分类：**
- `SAFE`：安全，自动执行（ls, cat, grep, git status 等）
- `CONFIRM`：需要用户确认（python 脚本，git push --force 等）
- `DANGEROUS`：危险，默认拒绝（sudo, chmod 777 等）
- `BANNED`：禁止，绝不执行（rm -rf /, curl|bash, fork bomb 等）

**核心功能：**
- 正则表达式匹配命令模式
- 支持自定义规则
- 安全报告生成

### 2. 文件系统沙箱 (`security/sandbox.py`)

**安全检查流程：**
1. 解析路径（处理 .., ~, 符号链接）
2. 检查是否在允许的根目录内
3. 检查是否在禁止路径列表中
4. 检查文件扩展名
5. 检查文件大小

**默认配置：**
- 允许范围：当前工作目录
- 禁止路径：/etc/passwd, /etc/shadow, /root 等
- 最大文件大小：10MB
- 禁止符号链接

### 3. 敏感信息过滤 (`security/filter.py`)

**预定义过滤规则（11 种）：**
- AWS Access Key
- API Key（通用）
- Bearer Token
- 私钥
- 密码赋值
- 邮箱地址
- 手机号（中国）
- IP 地址
- GitHub Token
- OpenAI Key
- Anthropic Key

### 4. 安全策略引擎 (`security/policy.py`)

**整合所有安全检查：**
- 命令权限检查
- 文件读取/写入权限检查
- 输出敏感信息过滤
- 永久允许/禁止设置
- 权限持久化（JSON 文件）

### 5. 审计日志 (`security/auditor.py`)

**记录事件类型：**
- 命令检查（command_check）
- 文件访问（file_access）
- 敏感信息过滤（sensitive_data_filtered）

**日志格式：** JSONL（每行一个 JSON 对象）
**存储位置：** `~/.my_agent/audit/audit-YYYY-MM-DD.jsonl`

---

## 🧪 测试覆盖

| 测试项 | 内容 | 状态 |
|--------|------|------|
| test_whitelist | 安全/禁止/确认命令分类 | ✅ 已通过 |
| test_sandbox | 路径范围、穿越攻击防护 | ✅ 已通过 |
| test_sensitive_filter | API 密钥、密码、邮箱过滤 | ✅ 已通过 |
| test_security_policy | 综合权限决策 | ✅ 已通过 |
| test_auditor | 审计日志记录与保存 | ✅ 已通过 |
| test_permission_persistence | 权限持久化 | ✅ 已通过 |
| test_rate_limiter | 命令速率限制 | ✅ 已通过 |
| test_tracked_sandbox | 临时文件追踪清理 | ✅ 已通过 |

---

## 📋 课后练习

### 练习 1：实现权限持久化
- 保存到 `.my_agent/permissions.json`
- 启动时自动加载
- 文件权限 chmod 600

### 练习 2：实现命令速率限制
- 每分钟最多执行 10 个 Bash 命令
- 使用 `collections.deque` 记录时间戳
- 超限时返回错误并记录审计日志

### 练习 3：实现沙箱临时文件清理
- 维护 `created_files` 集合追踪文件
- 在 `SESSION_END` Hook 中自动清理
- 不删除会话前就存在的文件

---

## 🎯 下一步行动

1. ✅ 创建 `security/` 目录结构
2. ✅ 实现 5 个核心模块（whitelist, sandbox, filter, policy, auditor）
3. ✅ 编写测试文件验证功能
4. ⏳ 在 Agent 中集成安全系统
5. ✅ 完成 3 个课后练习

---

## 📊 实现统计

| 模块 | 代码行数 | 功能 |
|------|---------|------|
| whitelist.py | ~200 行 | 命令白名单与分类 |
| sandbox.py | ~180 行 | 文件系统沙箱 |
| filter.py | ~160 行 | 敏感信息过滤 |
| policy.py | ~240 行 | 安全策略引擎 |
| auditor.py | ~100 行 | 审计日志 |
| **总计** | **~880 行** | **5 个核心模块** |

| 测试文件 | 测试项 | 状态 |
|---------|--------|------|
| test_security.py | 6 个测试 | ✅ 全部通过 |
| exercise_solutions.py | 3 个练习 | ✅ 全部通过 |

---

_学习完成时间：2026-04-14_
