# AI Systems Research MOC

*上级目录: [[Research 总览 MOC]]*

---

## Harness Engineering 研究

基于控制论和可扩展性维度的 Agent 系统架构分析。

### 核心报告

| 报告 | 主要维度 | 核心特点 |
|------|----------|----------|
| [[Claude Code Harness Engineering Analysis]] | **Temporal** (时间可扩展性) | 验证代理模式、权限规则系统、三角色分离 |
| [[oh-my-codex Harness Engineering Analysis]] | **Spatial** (空间可扩展性) | 阶段编排、角色约束、$ralph 持久化 |
| [[Hermes Agent Harness Engineering Analysis]] | **Temporal** (时间可扩展性) | 上下文压缩、多平台网关、模型感知 |
| [[OpenClaw Harness Engineering Analysis]] | **Interaction** (交互可扩展性) | Gateway 架构、子代理注册表、ACP 集成 |

### 对比维度

```
                    Temporal (时间)
                         │
                         │
        Hermes ◄─────────┼─────────► Claude Code
        (Context)        │         (Verification)
                         │
    Interaction ◄────────┼────────► Spatial
    (多平台)              │         (并行协调)
                         │
        OpenClaw ◄───────┴───────► oh-my-codex
        (Gateway)            (Team Mode)
```

### 关键模式速查

| 模式 | 最佳实现 | 适用场景 |
|------|----------|----------|
| **三角色分离** | Claude Code | 需要严格验证的任务 |
| **阶段编排** | oh-my-codex | 复杂多步骤工作流 |
| **上下文压缩** | Hermes | 长会话管理 |
| **多平台网关** | OpenClaw | 跨平台部署 |
| **子代理控制** | OpenClaw | 大规模代理编排 |

### 研究方法论

基于 **Harness Engineering Unified Framework**:

1. **4D 可扩展性模型**
   - Temporal: 时间维度（长期一致性）
   - Spatial: 空间维度（并行协调）
   - Interaction: 交互维度（人机协作）
   - Knowledge: 知识维度（信息熵管理）

2. **递归规划架构**
   - Planner → Generator → Evaluator 分离
   - 状态隔离机制
   - 自评失真预防

3. **控制论映射**
   - 反馈系统
   - 控制机制
   - 通信基础设施
   - 熵管理

---

## 其他 AI 系统研究

*待补充...*