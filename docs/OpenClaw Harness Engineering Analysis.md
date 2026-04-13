# Harness Engineering Analysis: OpenClaw

*Research Date: 2026-04-11*  
*Source: `/Users/ting/work/codes/openclaw/`*

---

## Executive Summary

| Aspect | Assessment |
|--------|------------|
| **Primary Dimension** | Interaction Scalability (交互可扩展性) - Multi-platform + scheduled execution |
| **Secondary Dimensions** | Temporal (persistent sessions) + Spatial (subagent delegation) |
| **Recursive Planning** | **Partial Implementation** - Subagent delegation with lifecycle hooks |
| **Self-Evaluation Risk** | **Medium-Low** - Registry-based tracking, parent stream relay for monitoring |
| **Harness Stance** | **Interaction-First Harness** - Gateway-centric multi-platform orchestration |

---

## Control Theory Mapping

### 1. Feedback Systems (反馈系统)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Subagent Registry** | `agents/subagent-registry.ts` | Centralized tracking of spawned subagent runs |
| **Parent Stream Relay** | `agents/acp-spawn-parent-stream.ts` | Real-time output streaming from child to parent |
| **Session Lifecycle Events** | `agents/subagent-spawn.ts` | `emitSessionLifecycleEvent` for session state changes |
| **Cron Run Telemetry** | `cron/types.ts` - `CronRunTelemetry` | Token usage tracking per cron run |
| **Session Store** | `config/sessions.ts` | JSON-based session persistence |
| **Subagent Control** | `agents/subagent-control.ts` | List/kill/steer operations for orchestration |

**Key Insight**: The subagent registry implements **centralized feedback** - all subagent runs are tracked with requester origin, allowing parent sessions to monitor, control, and receive completion notifications.

### 2. Control Mechanisms (控制机制)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Depth Limiting** | `agents/subagent-spawn.ts` | `DEFAULT_SUBAGENT_MAX_SPAWN_DEPTH = 1` (configurable) |
| **Max Children Per Agent** | `agents/subagent-spawn.ts` | Default 5 active children per session |
| **Max Concurrent Subagents** | `config/agent-limits.ts` | Default 8 concurrent subagents |
| **Run Timeout** | `agents/subagent-spawn-plan.ts` | Configurable per-subagent timeout |
| **Sandbox Inheritance** | `agents/subagent-spawn.ts` | Sandboxed sessions cannot spawn unsandboxed children |
| **Agent Allowlist** | `agents/subagent-spawn.ts` | `allowAgents` config controls cross-agent spawning |
| **Tool Context Restrictions** | `agents/subagent-capabilities.ts` | Depth-based capability system |

**Key Insight**: Multi-layered control with **hierarchical depth tracking** (`getSubagentDepthFromSessionStore`) and **capability attenuation** based on delegation depth.

### 3. Communication Infrastructure (通信基础设施)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Gateway Protocol** | `gateway/protocol/` | Typed control-plane and node wire protocol |
| **Session Binding Service** | `infra/outbound/session-binding-service.ts` | Thread/conversation binding for sessions |
| **Multi-Platform Gateway** | `channels/` | Telegram, Discord, Slack, Signal, WhatsApp, etc. |
| **Plugin SDK** | `plugin-sdk/` | Public contract for extensions |
| **Hook System** | `plugins/hooks.ts` | Lifecycle hooks (`subagent_spawning`, `subagent_spawned`, `subagent_ended`) |
| **Cron Delivery** | `cron/delivery.ts` | Multi-platform delivery for scheduled jobs |

**Key Insight**: **Gateway-centric architecture** - all agent communication goes through a central gateway that handles routing, delivery, and session management across platforms.

### 4. Entropy Management (熵管理)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Session Store Cleanup** | `cron/session-reaper.ts` | Automatic cleanup of expired sessions |
| **Subagent Cleanup Modes** | `agents/subagent-spawn.ts` | `"delete"` or `"keep"` session after completion |
| **Attachment Cleanup** | `agents/subagent-attachments.ts` | Automatic temp directory cleanup |
| **Run Log Management** | `cron/run-log.ts` | Cron execution history with rotation |
| **Lightweight Context** | `agents/subagent-spawn.ts` | `lightContext` flag for reduced bootstrap overhead |

---

## Architecture Analysis

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    GATEWAY LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Protocol   │  │   Routing    │  │    Session   │           │
│  │   (typed)    │  │  (channels)  │  │   (bindings) │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │    Cron      │  │   Delivery   │  │    Hooks     │           │
│  │  (schedule)  │  │  (multi-plat)│  │  (lifecycle) │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                   AGENT LAYER                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Subagent     │  │    ACP       │  │   Registry   │           │
│  │  Spawn       │  │   Spawn      │  │  (tracking)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Subagent     │  │   Control    │  │   Tools      │           │
│  │  Depth       │  │ (list/kill)  │  │  (40+ tools) │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                   RUNTIME LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Subagent   │  │     ACP      │  │    Cron      │           │
│  │ (isolated)   │  │ (codex/etc)  │  │  (isolated)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Sandbox    │  │   SQLite     │  │     JSON     │           │
│  │   (Docker)   │  │ (sessions)   │  │   (config)   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Lines of Code | Purpose |
|-----------|---------------|---------|
| `acp-spawn.ts` | 12K+ | ACP (Codex/Claude Code) session spawning |
| `subagent-spawn.ts` | 15K+ | Subagent spawning with lifecycle management |
| `subagent-registry.ts` | 8K+ | Subagent run tracking and orchestration |
| `subagent-control.ts` | 10K+ | List/kill/steer operations |
| `cron/service.ts` | 20K+ | Cron job execution and scheduling |
| `cron/normalize.ts` | 18K+ | Cron job normalization and validation |

---

## Scalability Dimensions Assessment

### Temporal Scalability: ⭐⭐⭐⭐ (Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Persistent Sessions** | Thread-bound subagent sessions | `mode="session"` + `thread=true` |
| **Session Resumption** | `resumeSessionId` for ACP | ACP spawn parameter |
| **Cron Scheduling** | At/every/cron expression support | `cron/types.ts` - `CronSchedule` |
| **Session Reaper** | Automatic cleanup of expired sessions | `cron/session-reaper.ts` |
| **Run Logs** | Cron execution history | `cron/run-log.ts` |

**Key Feature**: **Session persistence through thread binding** - subagents can create persistent sessions bound to messaging threads, enabling long-running workflows.

### Spatial Scalability: ⭐⭐⭐⭐ (Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Subagent Delegation** | `sessions_spawn` tool with depth tracking | `subagent-spawn.ts` |
| **ACP Delegation** | Codex/Claude Code harness spawning | `acp-spawn.ts` |
| **Depth Limiting** | `DEFAULT_SUBAGENT_MAX_SPAWN_DEPTH = 1` | `config/agent-limits.ts` |
| **Max Children** | `maxChildrenPerAgent = 5` default | `subagent-spawn.ts` |
| **Parallel Subagents** | Non-blocking spawn with registry tracking | `subagent-registry.ts` |
| **Cross-Agent Spawning** | `allowAgents` config for agent targeting | `subagent-spawn.ts` |

**Delegation Flow**:
```
Parent Session (depth 0)
    ↓ sessions_spawn
Child Subagent (depth 1) - MAX_DEPTH by default
    ✗ Cannot spawn further (blocked by depth check)
    
OR

Parent Session
    ↓ sessions_spawn runtime="acp"
ACP Session (Codex/Claude Code)
    → Full agent harness with its own planning
```

### Interaction Scalability: ⭐⭐⭐⭐⭐ (Excellent)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Multi-Platform Gateway** | 15+ messaging platforms | `channels/`, bundled plugins |
| **Session Binding** | Thread/conversation binding | `session-binding-service.ts` |
| **Thread-Bound Sessions** | Persistent sessions in threads | `subagent-spawn.ts` - `thread=true` |
| **Cross-Platform Delivery** | Cron can deliver to any platform | `cron/delivery.ts` |
| **Channel Adapters** | Plugin-based channel support | `channels/plugins/` |
| **WebSocket SSE** | Real-time session updates | Gateway protocol |

**Key Feature**: **Platform-agnostic session model** - sessions are abstracted from platforms, allowing seamless migration and cross-platform continuity.

---

## Recursive Planning Architecture

### Current Implementation

```
┌─────────────────────────────────────────────────────────────────┐
│                    PARENT SESSION                                │
│              (Coordinator + Monitor hybrid)                      │
│         Uses: sessions_spawn tool → Registry                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ spawn
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CHILD SUBAGENT                                │
│              (Executor - isolated context)                       │
│     Depth = 1, blocked from further delegation                   │
│     Results auto-announce to parent                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ completion message
                           ▼
              Parent registry receives notification
              
OR (for complex tasks):

┌─────────────────────────────────────────────────────────────────┐
│                    PARENT SESSION                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ sessions_spawn runtime="acp"
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ACP SESSION                                   │
│           (Full Harness - Planner/Executor/Evaluator)            │
│              Codex/Claude Code with their own                    │
│              recursive planning implementation                   │
└─────────────────────────────────────────────────────────────────┘
```

### Subagent Lifecycle Hooks

| Hook | Timing | Purpose |
|------|--------|---------|
| `subagent_spawning` | Before spawn | Thread binding preparation |
| `subagent_spawned` | After spawn | Notification/setup |
| `subagent_ended` | On completion | Cleanup/farewell |

### Control Capabilities

**Parent Can**:
- List all subagents (`subagents` tool - action=list)
- Kill subagents (`subagents` tool - action=kill)
- Steer subagents (`subagents` tool - action=steer) - send guidance messages
- Receive completion messages
- Monitor via parent stream relay (for ACP)

**Child Cannot**:
- Spawn further subagents (depth limit)
- Access parent's session history
- Send messages to arbitrary channels

---

## Self-Evaluation Distortion Prevention

| Risk Factor | Mitigation | Evidence |
|-------------|------------|----------|
| **Self-grading** | Parent monitors child output | Parent stream relay for ACP |
| **No evidence** | Child results auto-announce | `expectsCompletionMessage` flag |
| **Context isolation** | Fresh session for each child | `childSessionKey` with isolated context |
| **Depth limiting** | Hard limit prevents infinite recursion | `maxSpawnDepth` check |
| **Registry tracking** | All runs tracked with metadata | `subagent-registry.ts` |
| **Tool restrictions** | Depth-based capability system | `subagent-capabilities.ts` |

**Comparison with Claude Code / oh-my-codex / Hermes**:

| Aspect | Claude Code | oh-my-codex | Hermes | OpenClaw |
|--------|-------------|-------------|--------|----------|
| Evaluator Role | Independent verification agent | Independent verifier | Parent dual-role | Parent + Registry monitoring |
| Evidence Required | Command output | Command output | Summary | Auto-announce results |
| State Isolation | Process/container | Worktree + role | Context | Session isolation |
| Verdict Format | `VERDICT: PASS/FAIL` | `VERDICT: PASS/FAIL/PARTIAL` | Text summary | Structured registry entries |
| Completion Tracking | Verification agent | Verifier role | Parent judgment | Registry + auto-announce |

**Risk Assessment**: **Medium-Low** - The registry-based tracking and auto-announce system provides good visibility. However, the parent acts as both coordinator and implicit evaluator, which could create some distortion risk.

---

## Core Problems Solved

### 1. Multi-Platform Agent Deployment (交互可扩展性)

**Problem**: How to deploy agents across many messaging platforms with consistent behavior.

**Solution**:
- **Gateway abstraction** - All platforms route through unified gateway
- **Session binding service** - Threads/conversations bound to sessions
- **Plugin SDK** - Clean extension point for new platforms
- **Cron delivery** - Scheduled tasks can reach any platform

### 2. Agent Orchestration at Scale (空间可扩展性)

**Problem**: How to coordinate multiple agents working on related tasks.

**Solution**:
- **Subagent registry** - Centralized tracking of all spawned agents
- **Depth limiting** - Prevents runaway recursion
- **Parent stream relay** - Real-time monitoring of ACP subagents
- **Control operations** - List/kill/steer for runtime orchestration
- **Lifecycle hooks** - Plugin-extensible spawn/completion handling

### 3. Long-Running Persistent Workflows (时间可扩展性)

**Problem**: How to maintain agent state across extended periods.

**Solution**:
- **Thread-bound sessions** - Persistent sessions tied to messaging threads
- **Session resumption** - ACP sessions can be resumed
- **Cron scheduling** - Natural language scheduled execution
- **Session reaper** - Automatic cleanup prevents resource leaks

### 4. Safe Delegation Boundaries (控制机制)

**Problem**: How to delegate work without losing control or creating security risks.

**Solution**:
- **Sandbox inheritance** - Sandboxed parents cannot spawn unsandboxed children
- **Capability attenuation** - Tools restricted based on depth
- **Agent allowlists** - Cross-agent spawning controlled by config
- **Timeout enforcement** - Per-subagent run timeouts

---

## Key Capabilities

| Capability | Strength | Notes |
|------------|----------|-------|
| **Multi-Platform Gateway** | ⭐⭐⭐⭐⭐ | 15+ platforms, clean plugin SDK |
| **Subagent Orchestration** | ⭐⭐⭐⭐⭐ | Registry + control operations |
| **Session Persistence** | ⭐⭐⭐⭐ | Thread binding, session resumption |
| **Cron Scheduling** | ⭐⭐⭐⭐⭐ | Natural language, multi-platform delivery |
| **Spatial Scalability** | ⭐⭐⭐⭐ | Depth limiting, max children |
| **Self-Evaluation Correction** | ⭐⭐⭐⭐ | Registry tracking, auto-announce |
| **Integration (ACP)** | ⭐⭐⭐⭐⭐ | Codex/Claude Code harness spawning |
| **Sandbox Security** | ⭐⭐⭐⭐ | Inheritance rules, capability restrictions |

---

## Recommendations

### Strengths to Emulate

1. **Gateway-Centric Architecture**: The clean separation between gateway (routing/delivery) and agents (execution) is exemplary.

2. **Subagent Registry**: Centralized tracking with metadata (task, label, timeout, cleanup mode) provides excellent observability.

3. **Multi-Platform Session Binding**: Abstracting sessions from platforms enables powerful cross-platform workflows.

4. **Lifecycle Hooks**: Plugin-extensible spawn/completion handling allows custom orchestration logic.

5. **Dual Runtime Support**: Supporting both internal subagents and external ACP (Codex/Claude Code) harnesses provides flexibility.

### Potential Improvements

1. **Independent Evaluator Role**: Consider adding explicit verification agents for critical tasks.

2. **Sprint Contracts**: Add acceptance criteria/contract system for subagent delegation.

3. **Worktree Isolation**: Consider git worktree isolation for subagent file operations.

4. **Context Compression**: While sessions are isolated, explicit context compression for long threads could be beneficial.

5. **Evidence Requirements**: Structured verification evidence (test output, build results) vs. text summaries.

---

## Comparison Summary

| Dimension | Claude Code | oh-my-codex | Hermes | OpenClaw |
|-----------|-------------|-------------|--------|----------|
| **Primary Focus** | Temporal (verification) | Spatial (parallel) | Temporal (context mgmt) | Interaction (multi-platform) |
| **Recursive Planning** | Full 3-role | Full 3-role | Partial | Partial + ACP delegation |
| **Multi-Platform** | CLI only | CLI only | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Subagent Control** | N/A | Team mode | List/kill | ⭐⭐⭐⭐⭐ (list/kill/steer) |
| **Session Persistence** | Compression | Mode state | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ (thread binding) |
| **Scheduled Tasks** | Cron | Cron | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (nat lang) |
| **Integration** | Standalone | Standalone | Standalone | ⭐⭐⭐⭐⭐ (multi-runtime) |

---

## Conclusion

OpenClaw represents an **Interaction Scalability-first implementation** with **Gateway-Centric Harness** design:

- ✅ **Interaction Scalability**: Best-in-class multi-platform gateway with session binding
- ✅ **Spatial Scalability**: Comprehensive subagent orchestration with registry and control
- ✅ **Integration**: Unique ability to spawn external ACP harnesses (Codex/Claude Code)
- ✅ **Temporal Scalability**: Thread-bound persistent sessions, cron scheduling
- ✅ **Control Mechanisms**: Multi-layered depth limiting, sandbox inheritance, capability attenuation
- ⚠️ **Self-Evaluation Distortion**: Parent acts as implicit evaluator, though registry mitigates risk

The codebase demonstrates **Claw Software's focus** on practical deployment across diverse messaging platforms while maintaining orchestration capabilities. The dual runtime support (internal subagents + external ACP) is a unique strength.

**Harness Engineering Maturity**: **Very High** in interaction dimension, **High** in spatial/temporal dimensions. The gateway abstraction and subagent registry provide a solid foundation for multi-agent orchestration.

---

*上级目录: [[Research 总览 MOC]]*  
*分类: [[AI Systems]]*  
*相关: [[Claude Code Harness Engineering Analysis]], [[oh-my-codex Harness Engineering Analysis]], [[Hermes Agent Harness Engineering Analysis]]*