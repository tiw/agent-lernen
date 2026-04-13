# Harness Engineering Analysis: Hermes Agent

*Research Date: 2026-04-11*  
*Source: `/Users/ting/work/codes/hermes-agent/`*

---

## Executive Summary

| Aspect | Assessment |
|--------|------------|
| **Primary Dimension** | Temporal Scalability (时间可扩展性) - Context management & persistence |
| **Secondary Dimensions** | Spatial (delegation) + Interaction (multi-platform) |
| **Recursive Planning** | **Partial Implementation** - Subagent delegation without explicit Evaluator |
| **Self-Evaluation Risk** | **Medium** - Relies on parent agent for verification, no independent Evaluator role |
| **Harness Stance** | **Model-Aware Harness** - Heavy context management with model capability adaptation |

---

## Control Theory Mapping

### 1. Feedback Systems (反馈系统)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Context Compression** | `agent/context_compressor.py` | Automatic summarization of conversation history |
| **Memory Manager** | `agent/memory_manager.py` | Multi-provider memory orchestration with recalls |
| **Session Search** | `hermes_state.py` | FTS5 SQLite search across past conversations |
| **Skill System** | `agent/skill_utils.py` | Self-improving procedural memory from experience |
| **Checkpoint Manager** | `tools/checkpoint_manager.py` | Git-based filesystem snapshots for rollback |

**Key Insight**: The context compressor implements **iterative summarization** - preserves info across multiple compactions, a sophisticated feedback loop for long-running sessions.

### 2. Control Mechanisms (控制机制)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Iteration Budget** | `run_agent.py` - `IterationBudget` class | Thread-safe iteration counter (default 90 for parent, 50 for subagents) |
| **Delegation Depth Limit** | `tools/delegate_tool.py` | `MAX_DEPTH = 2` - parent → child → grandchild rejected |
| **Blocked Tools for Children** | `tools/delegate_tool.py` | `DELEGATE_BLOCKED_TOOLS` - prevents recursive delegation, memory writes |
| **Checkpoint Snapshots** | `tools/checkpoint_manager.py` | Shadow git repos for transparent rollback |
| **Approval System** | `tools/approval.py` | Dangerous command detection with user confirmation |

**Key Insight**: The delegation system implements **constrained autonomy** - children get restricted toolsets and cannot recursively delegate.

### 3. Communication Infrastructure (通信基础设施)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Multi-Platform Gateway** | `gateway/` directory | Telegram, Discord, Slack, WhatsApp, Signal adapters |
| **MCP Integration** | `tools/mcp_tool.py` | Model Context Protocol for external tool servers |
| **AGENTS.md Contract** | `AGENTS.md` | Top-level development guide for AI assistants |
| **Skill Markdown** | `skills/` directory | YAML frontmatter + markdown for skill definitions |
| **Cron Delivery** | `cron/scheduler.py` | Scheduled task delivery to any platform |

**Key Insight**: Multi-platform support demonstrates **interaction scalability** - same agent instance handles conversations across many platforms simultaneously.

### 4. Entropy Management (熵管理)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Context Pruning** | `agent/context_compressor.py` | Tool output pruning before LLM summarization (cheap pre-pass) |
| **Modular Tool Registry** | `tools/registry.py` | Self-contained tool modules with lazy registration |
| **SessionDB with FTS5** | `hermes_state.py` | Full-text search for cross-session recall |
| **Skill Lifecycle** | `agent/skill_utils.py` | Platform-specific skill enabling/disabling |
| **Model Metadata** | `agent/model_metadata.py` | Context length tracking per model/provider |

---

## Architecture Analysis

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HARNESS LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    Skills    │  │   Memory     │  │   Gateway    │       │
│  │ (procedural) │  │  (semantic)  │  │(multi-platform│       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Cron Jobs  │  │ Checkpoints  │  │  Context     │       │
│  │ (scheduled)  │  │ (snapshots)  │  │Compression   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                   FRAMEWORK LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   AIAgent    │  │  ToolRegistry│  │  PromptBuilder│       │
│  │ (main loop)  │  │ (40+ tools)  │  │  (system)    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Delegate   │  │  Auxiliary   │  │  Subdirectory│       │
│  │  (subagents) │  │   Client     │  │    Hints     │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    RUNTIME LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ OpenAI-compatible│ │   SQLite   │  │    Git       │       │
│  │   API client │  │ (sessions)   │  │(checkpoints) │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Lines of Code | Purpose |
|-----------|---------------|---------|
| `cli.py` | 416K | Main CLI entry point |
| `run_agent.py` | 10K+ | AIAgent class - core conversation loop |
| `tools/delegate_tool.py` | 45K | Subagent spawning with isolation |
| `agent/context_compressor.py` | 33K | Automatic context compression |
| `tools/mcp_tool.py` | 84K | MCP client integration |
| `agent/auxiliary_client.py` | 104K | Vision, summarization, model routing |

---

## Scalability Dimensions Assessment

### Temporal Scalability: ⭐⭐⭐⭐⭐ (Very Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Context Compression** | Structured summarization with iterative updates | `ContextCompressor` class with `_previous_summary` |
| **Token Budget Protection** | Tail protection by token count, not message count | `tail_token_budget` proportional to context |
| **Model-Aware Limits** | Per-model context length tracking | `agent/model_metadata.py` - context length queries |
| **Session Persistence** | SQLite SessionDB with FTS5 search | `hermes_state.py` - full conversation history |
| **Checkpoint Rollback** | Shadow git repos for filesystem snapshots | `tools/checkpoint_manager.py` |
| **Memory Provider System** | Pluggable memory (builtin + external) | `agent/memory_manager.py` |

**Context Compression Algorithm**:
```python
# 1. Prune old tool results (cheap, no LLM call)
# 2. Protect head messages (system + first exchange)
# 3. Protect tail by token budget (most recent ~20K tokens)
# 4. Summarize middle turns with structured LLM prompt
# 5. Iteratively update previous summary on subsequent compactions
```

**Structured Summary Template**:
- Goal
- Progress
- Decisions
- Files
- Next Steps

### Spatial Scalability: ⭐⭐⭐ (Moderate)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Subagent Delegation** | `delegate_task` tool with isolated context | `tools/delegate_tool.py` |
| **Parallel Execution** | `ThreadPoolExecutor` for batch delegation | `concurrent.futures` in delegate_tool |
| **Depth Limiting** | `MAX_DEPTH = 2` prevents infinite recursion | Hard limit in delegate_tool |
| **Tool Restrictions** | Children get blocked toolsets | `DELEGATE_BLOCKED_TOOLS` frozenset |
| **Batch Mode** | Multiple subagents in parallel | `batch` parameter in delegation |

**Limitations**:
- No explicit **Planner → Executor → Evaluator** separation
- Parent agent acts as implicit coordinator but also does verification
- No worktree isolation (relies on filesystem state)
- Children share parent's terminal environment

### Interaction Scalability: ⭐⭐⭐⭐⭐ (Very Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Multi-Platform Gateway** | Telegram, Discord, Slack, WhatsApp, Signal, etc. | `gateway/platforms/` directory |
| **Cross-Platform Continuity** | Session search works across platforms | `hermes_state.py` |
| **Cron Scheduling** | Natural language scheduled tasks | `cron/scheduler.py` |
| **Voice Memo Support** | Transcription integration | Mentioned in README |
| **Platform-Specific Skills** | Platform-conditional skill loading | `skill_matches_platform()` in skill_utils |

---

## Recursive Planning Architecture

### Current Implementation

```
┌─────────────────────────────────────────────────────────────┐
│                    PARENT AGENT                              │
│              (Coordinator + Evaluator hybrid)                │
│                     IterationBudget(90)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ delegate_task
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     CHILD AGENT                              │
│              (Executor - isolated context)                   │
│         IterationBudget(50) + blocked tools                 │
│     Cannot: delegate, write memory, send messages           │
└──────────────────────────┬──────────────────────────────────┘
                           │ Result summary
                           ▼
                    Parent evaluates
```

### Delegation Constraints

**Blocked Tools for Children** (`DELEGATE_BLOCKED_TOOLS`):
- `delegate_task` - no recursive delegation
- `clarify` - no user interaction
- `memory` - no writes to shared MEMORY.md
- `send_message` - no cross-platform side effects
- `execute_code` - should reason step-by-step

**What This Achieves**:
- Prevents infinite recursion
- Centralizes user interaction in parent
- Maintains memory consistency
- Controls blast radius of subagent actions

**What's Missing**:
- No independent Evaluator role
- Parent does both coordination AND verification
- No explicit Sprint Contract
- Verification relies on parent agent's judgment

---

## Self-Evaluation Distortion Prevention

| Risk Factor | Mitigation | Evidence |
|-------------|------------|----------|
| **Self-grading** | Parent agent reviews child summaries | No independent Evaluator |
| **No evidence requirement** | Children provide summaries, not command output | Summary format is descriptive, not evidence-based |
| **Context isolation** | Children have isolated conversation history | Fresh context, no parent history |
| **Depth limiting** | `MAX_DEPTH = 2` prevents too much delegation | Hard stop at grandchild |
| **Iteration budgets** | Separate budgets for parent (90) vs child (50) | `IterationBudget` class |

**Comparison with Claude Code / oh-my-codex**:

| Aspect | Claude Code | oh-my-codex | Hermes |
|--------|-------------|-------------|--------|
| Evaluator Role | Independent verification agent | Independent verifier role | Parent agent (dual role) |
| Evidence Required | Command output | Command output | Summary description |
| State Isolation | Process/container | Worktree + role guards | Context isolation only |
| Verdict Format | `VERDICT: PASS/FAIL` | `VERDICT: PASS/FAIL/PARTIAL` | Text summary |

**Risk Assessment**: **Medium** - The parent agent acting as both coordinator and evaluator creates potential for self-evaluation distortion. There's no independent verification with evidence requirements.

---

## Core Problems Solved

### 1. Long-Running Session Management (时间可扩展性)

**Problem**: How to maintain coherent conversations over hours/days without context overflow.

**Solution**:
- **Context compression** with structured summarization
- **Iterative summary updates** (preserves info across compactions)
- **Token-budget tail protection** (not just message count)
- **Model-aware limits** (different models have different context lengths)
- **SessionDB with FTS5** (search across past conversations)

### 2. Multi-Platform Presence (交互可扩展性)

**Problem**: How to provide consistent agent experience across many messaging platforms.

**Solution**:
- **Gateway architecture** with platform adapters
- **Unified session state** in SQLite (works across platforms)
- **Cron scheduling** with platform delivery
- **Platform-specific skill loading**

### 3. Safe Subagent Execution (空间可扩展性 - Partial)

**Problem**: How to delegate work without losing control.

**Solution**:
- **Tool blocking** - children cannot delegate recursively
- **Context isolation** - fresh conversation for each child
- **Iteration budgets** - separate limits for parent/child
- **Depth limiting** - hard stop at 2 levels

**Gap**: No explicit Planner → Executor → Evaluator separation. Parent does both coordination and verification.

### 4. Persistent Memory (熵管理)

**Problem**: How to accumulate knowledge across sessions.

**Solution**:
- **Skill system** - procedural memory from experience
- **Memory providers** - pluggable semantic memory
- **Session search** - FTS5 full-text search
- **Checkpoint snapshots** - filesystem rollback capability

---

## Key Capabilities

| Capability | Strength | Notes |
|------------|----------|-------|
| **Context Compression** | ⭐⭐⭐⭐⭐ | Best-in-class iterative summarization |
| **Temporal Scalability** | ⭐⭐⭐⭐⭐ | Excellent long-running session support |
| **Multi-Platform** | ⭐⭐⭐⭐⭐ | Most comprehensive platform support |
| **Spatial Scalability** | ⭐⭐⭐ | Basic delegation without full role separation |
| **Self-Evaluation Correction** | ⭐⭐⭐ | Parent dual-role creates distortion risk |
| **Memory System** | ⭐⭐⭐⭐⭐ | Multi-provider with semantic + procedural |
| **Scheduled Execution** | ⭐⭐⭐⭐⭐ | Built-in natural language cron |
| **Checkpoint/Rollback** | ⭐⭐⭐⭐⭐ | Shadow git repos for snapshots |

---

## Recommendations

### Strengths to Emulate

1. **Context Compression Algorithm**: The iterative summarization with structured templates (Goal, Progress, Decisions, Files, Next Steps) is exemplary.

2. **Model-Aware Context Management**: Tracking context lengths per model/provider enables optimal token usage.

3. **Multi-Platform Gateway**: The clean abstraction for Telegram/Discord/Slack/etc. is a great example of interaction scalability.

4. **Checkpoint Manager**: Shadow git repos provide transparent rollback without polluting user directories.

5. **Pluggable Memory Providers**: The `MemoryManager` with builtin + external provider support shows good extensibility design.

### Potential Improvements

1. **Independent Evaluator Role**: Add a verification role similar to Claude Code's verification agent or oh-my-codex's verifier.

2. **Evidence-Based Verification**: Require command output evidence, not just descriptive summaries.

3. **Sprint Contracts**: Define explicit acceptance criteria before subagent delegation.

4. **Worktree Isolation**: Consider git worktree isolation for subagents (like oh-my-codex).

5. **Explicit Three-Role Separation**: Separate Planner, Executor, and Evaluator into distinct roles.

---

## Comparison Summary

| Dimension | Claude Code | oh-my-codex | Hermes Agent |
|-----------|-------------|-------------|--------------|
| **Primary Focus** | Temporal (verification) | Spatial (coordination) | Temporal (context mgmt) |
| **Recursive Planning** | Full 3-role separation | Full 3-role separation | Partial (no Evaluator) |
| **Context Management** | Compression + verification | Mode state + checkpoints | **Best: Iterative compression** |
| **Multi-Platform** | CLI-focused | CLI-focused | **Best: Multi-platform gateway** |
| **Verification** | Independent agent | Independent verifier | Parent dual-role |
| **Scheduled Tasks** | Cron support | Cron support | **Best: Built-in natural language cron** |

---

## Conclusion

Hermes Agent represents a **Temporal Scalability-focused implementation** with **Model-Aware Harness** design:

- ✅ **Temporal Scalability**: Best-in-class context compression with iterative summarization
- ✅ **Interaction Scalability**: Comprehensive multi-platform gateway
- ✅ **Memory Management**: Pluggable semantic + procedural memory
- ⚠️ **Spatial Scalability**: Basic delegation without full role separation
- ⚠️ **Self-Evaluation Distortion**: Parent dual-role creates moderate risk

The codebase demonstrates **Nous Research's focus** on long-running, persistent agents that can work across multiple platforms over extended periods. The context compression system is particularly sophisticated, with model-aware limits and iterative summary updates.

**Harness Engineering Maturity**: **High** in temporal/interaction dimensions, **Medium** in spatial dimension due to lack of independent Evaluator role.

---

*上级目录: [[Research 总览 MOC]]*  
*分类: [[AI Systems]]*  
*相关: [[Claude Code Harness Engineering Analysis]], [[oh-my-codex Harness Engineering Analysis]], [[OpenClaw Harness Engineering Analysis]]*