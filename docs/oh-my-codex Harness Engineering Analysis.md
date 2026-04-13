# Harness Engineering Analysis: oh-my-codex (OMX)

*Research Date: 2026-04-11*  
*Source: `/Users/ting/work/codes/oh-my-codex/`*

---

## Executive Summary

| Aspect | Assessment |
|--------|------------|
| **Primary Dimension** | Spatial Scalability (空间可扩展性) - Cursor-style coordination |
| **Secondary Dimensions** | Temporal (Ralph persistence) + Interaction (role-based governance) |
| **Recursive Planning** | **Strong Implementation** - Planner → Executor → Verifier separation |
| **Self-Evaluation Risk** | **Low** - Structured verification protocols prevent distortion |
| **Harness Stance** | **Harness-First** with Model capability awareness |

---

## Control Theory Mapping

### 1. Feedback Systems (反馈系统)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Verification Protocol** | `src/verification/verifier.ts` | Structured evidence-backed verification with PASS/FAIL/PARTIAL verdicts |
| **Task Status Tracking** | `src/team/contracts.ts` | State machine for task lifecycle (pending → in_progress → completed/failed) |
| **Team Events** | `src/team/contracts.ts` | 20+ event types for worker monitoring (task_completed, worker_idle, etc.) |
| **Mode State Persistence** | `src/modes/base.ts` | Durable state for long-running modes (ralph, team, autopilot) |
| **Fix-Verify Loop** | `src/verification/verifier.ts` | Max 3 retry attempts with escalation on failure |

**Key Insight**: The verification protocol enforces **evidence-backed completion** - no task is complete without command output evidence.

### 2. Control Mechanisms (控制机制)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Role-Based Constraints** | `prompts/*.md` | Each role has explicit scope guards (Planner doesn't implement) |
| **Team Orchestrator** | `src/team/orchestrator.ts` | Phase-based state machine (plan → prd → exec → verify → fix) |
| **Pipeline Orchestrator** | `src/pipeline/orchestrator.ts` | Configurable stage sequencing with artifact passing |
| **Worktree Isolation** | `src/team/worktree.ts` | Git worktree per worker for parallel execution |
| **Task Claims** | `src/team/contracts.ts` | Exclusive task ownership prevents duplicate work |

**Key Insight**: "Constraints are more effective than instructions" — role prompts use `<scope_guard>` to enforce boundaries.

### 3. Communication Infrastructure (通信基础设施)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **AGENTS.md Contract** | `AGENTS.md` | Top-level operating contract with delegation rules |
| **Role Prompts** | `prompts/*.md` | Structured role definitions (planner, executor, verifier) |
| **Task Mailboxes** | `src/team/` | Inbox/heartbeat/mailbox system for worker communication |
| **MCP Comm** | `src/team/mcp-comm.ts` | Model Context Protocol for inter-agent messaging |
| **State Persistence** | `.omx/` directory | Plans, logs, memory, and runtime state |

**Key Insight**: All knowledge is **versioned in repo** (AGENTS.md, prompts/*.md) - not scattered in Slack/docs.

### 4. Entropy Management (熵管理)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Modular Role System** | `prompts/` directory | 30+ specialized roles for specific tasks |
| **Skill System** | `skills/` directory | Reusable workflows (deep-interview, ralph, team) |
| **Phase Controllers** | `src/team/phase-controller.ts` | Bounded execution phases prevent drift |
| **Workflow Transitions** | `src/state/workflow-transition.ts` | Exclusive mode enforcement (can't run team + ralph simultaneously) |
| **Commit Hygiene** | `src/team/commit-hygiene.ts` | Structured commit context for traceability |

---

## Architecture Analysis

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HARNESS LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   $ralph     │  │   $team      │  │  $deep-inter │       │
│  │ (persistent) │  │ (parallel)   │  │   (clarify)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   $ralplan   │  │   Skills     │  │   Pipeline   │       │
│  │ (planning)   │  │ (workflows)  │  │ (stages)     │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                   FRAMEWORK LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Planner    │  │   Executor   │  │   Verifier   │       │
│  │  (Prometheus)│  │  (implement) │  │ (evidence)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Analyst    │  │   Architect  │  │   Critic     │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    RUNTIME LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Codex CLI   │  │    tmux      │  │   Node.js    │       │
│  │ (execution)  │  │ (sessions)   │  │ (runtime)    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### Harness Layer Components

| Component | Purpose | Harness Engineering Mapping |
|-----------|---------|---------------------------|
| **$deep-interview** | Clarify intent before planning | Planner role - separates planning from execution |
| **$ralplan** | Create approved implementation plan | Sprint Contract - defines acceptance criteria before work |
| **$team** | Parallel execution with coordination | Spatial Scalability - recursive decomposition |
| **$ralph** | Persistent completion/verification loop | Temporal Scalability - prevents direction drift |
| **Skills** | Reusable workflows | Constraint templates - executable patterns |

---

## Scalability Dimensions Assessment

### Spatial Scalability: ⭐⭐⭐⭐⭐ (Very Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Recursive Decomposition** | Team mode with role-specific task assignment | `getPhaseAgents()` in `orchestrator.ts` |
| **Parallel Execution** | Multi-worker tmux sessions | `runtime.ts` - 160K lines of coordination logic |
| **Worktree Isolation** | Git worktree per worker | `worktree.ts` - isolated repo copies |
| **Task Convergence** | Task status state machine + integration | `contracts.ts` - status transitions |
| **Role Specialization** | 30+ specialized prompts | `prompts/` directory |

**Team Phase Pipeline**:
```
team-plan → team-prd → team-exec → team-verify → team-fix (loop)
```

**Role Assignment per Phase**:
- **team-plan**: analyst, planner
- **team-prd**: product-manager, analyst
- **team-exec**: executor, designer, test-engineer
- **team-verify**: verifier, quality-reviewer, security-reviewer
- **team-fix**: executor, build-fixer, debugger

### Temporal Scalability: ⭐⭐⭐⭐ (Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Persistent State** | Mode state in `.omx/` directory | `modes/base.ts` - durable state management |
| **Ralph Persistence** | Owner-session tracking | `ralph/contract.ts` - completion loops |
| **Verification Checkpoints** | Structured verification at task end | `verifier.ts` - evidence requirements |
| **Fix-Verify Loop** | Max 3 retries with escalation | `verifier.ts` - retry logic |
| **Session Resume** | Read mode state on resume | `canResumePipeline()` in `pipeline/orchestrator.ts` |

**Ralph Pattern** (Persistent Completion Loop):
```typescript
// ralph persistence contract
interface RalphState {
  owner_omx_session_id: string;  // Track ownership
  current_phase: string;         // Progress tracking
  iteration: number;             // Loop count
  max_iterations: number;        // Bounded execution
}
```

### Interaction Scalability: ⭐⭐⭐⭐⭐ (Very Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Environment Governance** | AGENTS.md as top-level contract | `AGENTS.md` - 18K bytes of guidance |
| **Constraint-Based Control** | Role scope guards | `<scope_guard>` in role prompts |
| **Knowledge Versioning** | Prompts in repo, not runtime | `prompts/*.md` files |
| **Autonomy Directive** | "Proceed automatically without asking" | `AGENTS.md` opening comment |
| **Throughput Prioritization** | Default to execution, ask last | Executor prompt: "explore first, ask last" |

**Four Foundational Consensus**:

| Principle | Implementation | Status |
|-----------|----------------|--------|
| **Leverage Point Shift** | Human uses `$` commands, doesn't micromanage | ✅ Full |
| **Knowledge Versioning** | AGENTS.md + prompts/*.md in repo | ✅ Full |
| **Constraints Over Instructions** | Role scope guards + state machines | ✅ Full |
| **Throughput Over Perfection** | "KEEP GOING UNTIL FULLY RESOLVED" | ✅ Full |

---

## Recursive Planning Architecture

### Three-Role Separation

```
┌─────────────────────────────────────────────────────────────┐
│                     PLANNER (Prometheus)                     │
│  - Turns requests into actionable work plans                 │
│  - Writes to .omx/plans/*.md (read-only for others)         │
│  - Does NOT implement                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ Plan with acceptance criteria
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      EXECUTOR                                │
│  - Explore, implement, verify, finish                        │
│  - "KEEP GOING UNTIL THE TASK IS FULLY RESOLVED"            │
│  - Must provide verification evidence                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ Implementation + verification output
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      VERIFIER                                │
│  - Evidence-backed verification                              │
│  - Required: test, typecheck, lint, build evidence          │
│  - Verdict: PASS/FAIL/PARTIAL                               │
└─────────────────────────────────────────────────────────────┘
```

### Role Constraints (State Isolation)

| Role | Can Do | Cannot Do |
|------|--------|-----------|
| **Planner** | Write plans to `.omx/plans/`, ask about tradeoffs | Write code, implement |
| **Executor** | Implement, verify, run tests | Rewrite global plan |
| **Verifier** | Review evidence, issue verdict | Modify implementation |

**Planner Scope Guard**:
```markdown
<scope_guard>
- Write plans only to `.omx/plans/*.md`
- Do not write code files
- Do not generate a final plan until user clearly requests
</scope_guard>
```

**Executor Success Criteria**:
```markdown
A task is complete only when:
1. Requested behavior is implemented
2. `lsp_diagnostics` is clean
3. Relevant tests pass
4. Build/typecheck succeeds
5. No temporary/debug leftovers
6. **Final output includes concrete verification evidence**
```

---

## Self-Evaluation Distortion Prevention

| Risk Factor | Mitigation | Evidence |
|-------------|------------|----------|
| **Self-grading** | Independent verification role | `verifier.ts` - separate verification step |
| **Rationalization** | "No evidence = not complete" rule | Executor prompt: "Never claim success without tool-backed evidence" |
| **Drift from goals** | Plan saved to `.omx/plans/` (read-only) | Planner constraint: plans are read-only during execution |
| **Premature completion** | "KEEP GOING UNTIL FULLY RESOLVED" | Executor identity statement |
| **Over-investment bias** | Max 3 fix attempts, then escalate | `verifier.ts`: "If still failing after 3 attempts, escalate" |

**Verification Requirements by Task Size**:

| Size | Required Evidence |
|------|-------------------|
| **Small** | Type check on modified files, related tests |
| **Standard** | Full type check, test suite, linter, end-to-end |
| **Large** | Full type check, complete test suite, security review, performance assessment, API compatibility |

---

## Core Problems Solved

### 1. Multi-Agent Coordination (空间可扩展性)

**Problem**: How to coordinate multiple agents working in parallel without chaos.

**Solution**:
- **Phase-based orchestration**: plan → prd → exec → verify → fix
- **Role specialization**: Different agents for different phases
- **Worktree isolation**: Each worker has isolated git worktree
- **Task state machine**: Exclusive ownership via task claims

### 2. Long-Running Task Persistence (时间可扩展性)

**Problem**: How to maintain progress over hours/days without losing state.

**Solution**:
- **Ralph persistence**: Owner-session tracking with durable state
- **Mode state in `.omx/`**: JSON state files survive restarts
- **Verification checkpoints**: Evidence required at each completion
- **Pipeline stages**: Bounded phases with clear entry/exit criteria

### 3. Intent Clarification vs Execution Separation

**Problem**: How to prevent agents from implementing before understanding.

**Solution**:
- **$deep-interview**: Explicit clarification phase
- **$ralplan**: Separate planning with user approval
- **Planner scope guard**: Cannot write code
- **Ask gate**: "Ask only when progress is impossible"

### 4. Quality Verification (自评失真预防)

**Problem**: How to prevent agents from rationalizing incomplete work.

**Solution**:
- **Evidence requirement**: No command output = not verified
- **Independent verification**: Verifier role separate from executor
- **Fix-verify loop**: Max 3 retries with escalation
- **Lore commits**: Decision context preserved in git trailers

---

## Key Capabilities

| Capability | Strength | Notes |
|------------|----------|-------|
| **Recursive Planning** | ⭐⭐⭐⭐⭐ | Clear Planner → Executor → Verifier separation |
| **Spatial Scalability** | ⭐⭐⭐⭐⭐ | Team mode with phase orchestration |
| **Temporal Scalability** | ⭐⭐⭐⭐ | Ralph persistence + mode state |
| **Interaction Scalability** | ⭐⭐⭐⭐⭐ | AGENTS.md contract, role scope guards |
| **Self-Evaluation Correction** | ⭐⭐⭐⭐⭐ | Evidence-backed verification |
| **Role Specialization** | ⭐⭐⭐⭐⭐ | 30+ specialized prompts |
| **State Management** | ⭐⭐⭐⭐⭐ | Durable mode state + workflow transitions |
| **Constraint Enforcement** | ⭐⭐⭐⭐ | Scope guards in role prompts |

---

## Recommendations

### Strengths to Emulate

1. **Explicit Phase Orchestration**: The `team-plan → team-prd → team-exec → team-verify → team-fix` pipeline is a clear implementation of recursive planning.

2. **Role-Based Constraints**: Using `<scope_guard>` in prompts is an elegant way to enforce Harness boundaries without code.

3. **Evidence-Backed Verification**: The "No evidence = not complete" rule prevents self-evaluation distortion effectively.

4. **Durable State Management**: Mode state in `.omx/` enables true temporal scalability.

5. **Autonomy Directive**: "Proceed automatically without asking" maximizes throughput.

### Potential Improvements

1. **Explicit Sprint Contracts**: While plans have acceptance criteria, they could be more explicitly structured like Claude Code's Sprint Contracts.

2. **Component Lifecycle**: Feature flags or version gates for retiring roles as models improve (similar to Claude Code's feature flags).

3. **Convergence Algorithms**: Document the specific algorithms for merging parallel work (cherry-pick, rebase, cross-rebase logic exists but could be more explicit).

---

## Comparison: Claude Code vs oh-my-codex

| Aspect | Claude Code | oh-my-codex |
|--------|-------------|-------------|
| **Primary Dimension** | Temporal (runtime correction) | Spatial (parallel coordination) |
| **Three-Role Pattern** | Coordinator → Worker → Verification Agent | Planner → Executor → Verifier |
| **State Isolation** | Process/container isolation | Role scope guards + worktree isolation |
| **Persistence** | Context compression | Mode state in `.omx/` |
| **Verification** | External application testing | Evidence-backed verification protocol |
| **Multi-Agent** | Coordinator mode with worktrees | Team mode with phase orchestration |
| **Permission Model** | Rule-based with classifier | Role-based with scope guards |

---

## Conclusion

oh-my-codex represents a **mature Harness-First implementation** focused on **Spatial Scalability** (空间可扩展性):

- ✅ **Spatial Scalability**: Phase orchestration, role specialization, worktree isolation
- ✅ **Temporal Scalability**: Ralph persistence, mode state, verification checkpoints
- ✅ **Interaction Scalability**: AGENTS.md contract, role scope guards, autonomy directive
- ✅ **Recursive Planning**: Clear Planner → Executor → Verifier separation
- ✅ **Self-Evaluation Distortion Prevention**: Evidence-backed verification protocol

The codebase demonstrates a **Cursor-style approach** to Harness Engineering - focusing on coordination architecture for parallel agent execution, with strong role separation and phase-based orchestration.

---

*上级目录: [[Research 总览 MOC]]*  
*分类: [[AI Systems]]*  
*相关: [[Claude Code Harness Engineering Analysis]], [[OpenClaw Harness Engineering Analysis]], [[Hermes Agent Harness Engineering Analysis]]*