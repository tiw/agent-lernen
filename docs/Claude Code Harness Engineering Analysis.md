# Harness Engineering Analysis: Claude Code

*Research Date: 2026-04-11*
*Source: `/Users/ting/work/codes/claude-code/`*

---

## Executive Summary

| Aspect | Assessment |
|--------|------------|
| **Primary Dimension** | Temporal Scalability (时间可扩展性) - Anthropic-style runtime correction |
| **Secondary Dimensions** | Spatial (coordinator mode) + Interaction (permission system) |
| **Recursive Planning** | **Full Implementation** - Planner → Generator → Evaluator separation |
| **Self-Evaluation Risk** | **Low** - Independent verification agents prevent distortion |
| **Harness Stance** | **Harness-First** with Model capability awareness |

## Control Theory Mapping

### 1. Feedback Systems (反馈系统)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Verification Agent** | `tools/AgentTool/built-in/verificationAgent.ts` | Independent Evaluator role that tests actual application behavior |
| **Permission Classifier** | `utils/permissions/permissions.ts` | AI-powered auto-mode uses LLM-as-judge for permission decisions |
| **Task Notifications** | `tools/AgentTool/AgentTool.tsx` | Async agents report completion status via structured notifications |
| **Denial Tracking** | `utils/permissions/denialTracking.ts` | Tracks consecutive/total denials for fallback to manual approval |

**Key Insight**: The verification agent exemplifies the **Eval-as-Code** pattern with explicit `VERDICT: PASS/FAIL/PARTIAL` output format.

### 2. Control Mechanisms (控制机制)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Permission Rules** | `utils/permissions/permissions.ts` | Rule-based constraint system (allow/deny/ask patterns) |
| **Coordinator Mode** | `coordinator/coordinatorMode.ts` | Hierarchical agent orchestration with explicit worker management |
| **Worktree Isolation** | `utils/worktree.ts` | Git worktree isolation for parallel agent execution |
| **Sandbox Manager** | `utils/sandbox/sandbox-adapter.ts` | Execution environment isolation |
| **Skill System** | `tools/SkillTool/` | Reusable workflow constraints through skill definitions |

**Key Insight**: "Constraints are more effective than instructions" — the permission system uses executable rules (`Bash(rm:*)`) rather than fuzzy guidance.

### 3. Communication Infrastructure (通信基础设施)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **AGENTS.md Support** | Context loading for agent definitions | Structured intent expression through agent definitions |
| **MCP Protocol** | `services/mcp/` | Model Context Protocol for external tool integration |
| **Structured Tool Input** | `Tool.ts` | Zod schemas enforce structured communication |
| **Task Notifications** | XML-based notification format | Standardized agent-to-coordinator communication |

**Key Insight**: All agent communication is structured (Zod schemas) and versioned through the codebase.

### 4. Entropy Management (熵管理)

| Implementation | Location | Description |
|----------------|----------|-------------|
| **Modular Tool System** | `tools/` directory | ~40 self-contained tool modules |
| **Feature Flags** | `bun:bundle` feature system | Dead code elimination for unused features |
| **Lazy Loading** | Dynamic `import()` patterns | Heavy modules deferred until needed |
| **Permission Context** | Immutable permission state | DeepImmutable types prevent state mutation |

**Key Insight**: Feature flags enable **component lifecycle management** — features can be removed as model capabilities evolve.

## Architecture Analysis

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HARNESS LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    Skills    │  │   Agents     │  │  Coordinator │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                   FRAMEWORK LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Tool System │  │  Permission  │  │   Context    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    RUNTIME LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Anthropic   │  │     Bun      │  │     Ink      │       │
│  │     SDK      │  │   Runtime    │  │     UI       │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### Runtime Layer
- **Model API**: Anthropic SDK with streaming, retry logic, token counting
- **Execution**: Bun runtime for TypeScript
- **UI**: React + Ink for terminal rendering

### Framework Layer
- **Tool Registry**: Type-safe tool definitions with Zod schemas
- **Permission System**: Multi-mode permission handling (default/plan/bypassPermissions/auto/dontAsk)
- **Context Management**: File state caching, conversation history

### Harness Layer
- **Skill System**: Reusable workflow definitions
- **Agent System**: Built-in agents (general, verification, plan, explore)
- **Coordinator**: Multi-agent orchestration with hierarchical delegation

## Scalability Dimensions Assessment

### Temporal Scalability: ⭐⭐⭐⭐⭐ (Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Context Reset** | `compact/` service for conversation compression | Prevents context window overflow |
| **Sprint Contracts** | Verification agent's predefined criteria | Explicit `VERDICT: PASS/FAIL` output |
| **State Isolation** | Evaluator doesn't share state with Generator | `disallowedTools` prevents self-modification |
| **Independent Evaluation** | Verification agent tests real application | Playwright/MCP browser automation |
| **Direction Drift Protection** | Coordinator mode with task notifications | Clear separation between planning and execution |

**Three-Role Implementation**:
```
Coordinator (Planner) → Worker Agents (Generator) → Verification Agent (Evaluator)
```

The verification agent is a **pure Evaluator**:
- Cannot modify files (`disallowedTools: [FILE_EDIT, FILE_WRITE, ...]`)
- Must test actual application behavior
- Ends with objective `VERDICT: PASS/FAIL/PARTIAL`

### Spatial Scalability: ⭐⭐⭐⭐ (Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Recursive Decomposition** | Coordinator mode spawns sub-planners | `AgentTool` with `description` + `prompt` |
| **Parallel Execution** | Async agent launching with background mode | `run_in_background: true` |
| **Worktree Isolation** | Git worktree per agent | `createAgentWorktree()` in `utils/worktree.ts` |
| **Convergence** | Task notifications with structured results | XML-based `<task-notification>` format |
| **Multi-Agent Teams** | TeamCreate/TeamDelete tools | `TeamCreateTool`, `TeamDeleteTool` |

**Architecture Pattern**:
```typescript
// Coordinator spawns parallel workers
AgentTool({ description: "Research auth", prompt: "..." })
AgentTool({ description: "Research storage", prompt: "..." })

// Workers notify on completion
<task-notification>
  <task-id>agent-a1b</task-id>
  <status>completed</status>
  <result>...</result>
</task-notification>
```

### Interaction Scalability: ⭐⭐⭐⭐⭐ (Strong)

| Capability | Implementation | Evidence |
|------------|----------------|----------|
| **Environment Governance** | Permission rules as executable constraints | `Bash(rm:*)`, `Bash(npm publish:*)` patterns |
| **Knowledge Versioning** | AGENTS.md, skills in repo | Markdown-based agent definitions |
| **Constraint-Based Control** | Permission modes + rules | `default`/`plan`/`bypassPermissions`/`auto`/`dontAsk` |
| **Throughput Prioritization** | Auto-mode with classifier | AI classifier for permission decisions |

**Constraint Examples**:
```typescript
// More effective than "Be careful with rm"
{ toolName: "Bash", ruleContent: "rm:*", behavior: "ask" }

// More effective than "Don't publish without approval"
{ toolName: "Bash", ruleContent: "npm publish:*", behavior: "ask" }
```

**Four Foundational Consensus**:

| Principle | Implementation | Status |
|-----------|----------------|--------|
| **Leverage Point Shift** | Human designs AGENTS.md, not writes code | ✅ Full |
| **Knowledge Versioning** | Agents/skills defined in repo Markdown | ✅ Full |
| **Constraints Over Instructions** | Permission rules with executable patterns | ✅ Full |
| **Throughput Over Perfection** | Auto-mode classifier accepts calculated risk | ✅ Full |

## Recursive Planning Architecture

### Role Separation

| Role | Component | Responsibilities | Isolation |
|------|-----------|------------------|-----------|
| **Planner** | Coordinator Mode | Break tasks, spawn workers, synthesize results | No direct code generation |
| **Generator** | Worker Agents | Implement based on prompts | No evaluation authority |
| **Evaluator** | Verification Agent | Test against Sprint Contract | No shared state with Generator |

### Verification Agent Architecture

```typescript
// PURE EVALUATOR - Cannot modify project
export const VERIFICATION_AGENT: BuiltInAgentDefinition = {
  agentType: 'verification',
  disallowedTools: [
    AGENT_TOOL_NAME,      // Cannot spawn sub-agents
    FILE_EDIT_TOOL_NAME,  // Cannot modify files
    FILE_WRITE_TOOL_NAME, // Cannot create files
    // ... other write tools
  ],
  getSystemPrompt: () => VERIFICATION_SYSTEM_PROMPT,
  // Must end with VERDICT: PASS/FAIL/PARTIAL
}
```

**State Isolation Mechanisms**:
1. **Tool Restrictions**: Explicit `disallowedTools` list
2. **Process Isolation**: Separate agent context
3. **Contract-Based Evaluation**: Predefined acceptance criteria
4. **Real Application Testing**: Playwright/MCP browser automation

## Self-Evaluation Distortion Prevention

| Risk Factor | Mitigation | Evidence |
|-------------|------------|----------|
| **Self-grading** | Independent verification agent | Verification agent cannot be the implementer |
| **Rationalization** | Explicit command output requirement | "A check without a Command run block is not a PASS" |
| **Drift from goals** | Sprint Contract predefined | Criteria set before work begins |
| **Over-investment bias** | Fresh agent for verification | No shared context with implementer |

**Verification Prompt Excerpt**:
```
=== RECOGNIZE YOUR OWN RATIONALIZATIONS ===
You will feel the urge to skip checks. These are the exact excuses you reach for:
- "The code looks correct based on my reading" — reading is not verification. Run it.
- "The implementer's tests already pass" — the implementer is an LLM. Verify independently.
- "This is probably fine" — probably is not verified. Run it.
```

## Core Problems Solved

### 1. Long-Running Agent Consistency (时间可扩展性)

**Problem**: Agents drift off-target after hours of work.

**Solution**: 
- Context compression service (`compact/`)
- Sprint-based execution with verification checkpoints
- Independent Evaluator role prevents self-evaluation distortion

### 2. Multi-Agent Coordination (空间可扩展性)

**Problem**: Hundreds of agents working simultaneously create chaos.

**Solution**:
- Coordinator mode with hierarchical delegation
- Worktree isolation for parallel development
- Structured task notifications for convergence
- Team management tools for agent groups

### 3. Permission at Scale (交互可扩展性)

**Problem**: Human cannot review every tool call from hundreds of agents.

**Solution**:
- Executable permission rules (constraints > instructions)
- AI classifier for auto-mode permission decisions
- Denial tracking with fallback to manual approval
- Multiple permission modes for different risk tolerances

### 4. Self-Evaluation Distortion (自评失真)

**Problem**: Agent discovers defects but rationalizes them as acceptable.

**Solution**:
- Verification agent with explicit tool restrictions
- Mandatory command execution for verification
- Predefined Sprint Contracts
- State isolation between Generator and Evaluator

## Key Capabilities

| Capability | Strength | Notes |
|------------|----------|-------|
| **Recursive Planning** | ⭐⭐⭐⭐⭐ | Full Planner → Generator → Evaluator separation |
| **Temporal Scalability** | ⭐⭐⭐⭐⭐ | Context management, sprint contracts, verification |
| **Spatial Scalability** | ⭐⭐⭐⭐ | Worktree isolation, coordinator mode, teams |
| **Interaction Scalability** | ⭐⭐⭐⭐⭐ | Permission rules, auto-mode, constraint-based |
| **Self-Evaluation Correction** | ⭐⭐⭐⭐⭐ | Independent verification agent |
| **Component Lifecycle** | ⭐⭐⭐⭐ | Feature flags enable dynamic capability removal |
| **Entropy Management** | ⭐⭐⭐⭐ | Modular tools, lazy loading, immutable state |

## Recommendations

### Strengths to Emulate

1. **Verification Agent Pattern**: The three-role separation with explicit disallowedTools is an exemplary implementation of recursive planning.

2. **Permission Rule System**: The constraint-based approach (`Bash(rm:*)`) is more scalable than natural language instructions.

3. **Feature Flag Lifecycle**: Using `bun:bundle` feature flags enables graceful component retirement as models improve.

4. **Structured Communication**: XML-based task notifications provide clear convergence mechanisms.

### Potential Improvements

1. **Explicit Sprint Contracts**: While verification has predefined criteria, the main agent loop could benefit from more explicit Sprint Contract definitions at task start.

2. **Component Lifecycle Documentation**: Feature flags exist but could be more explicitly mapped to model capability evolution.

3. **Convergence Algorithms**: Document the specific algorithms for merging parallel agent outputs (currently implicit in coordinator mode).

## Conclusion

Claude Code represents a **mature Harness-First implementation** with strong alignment to the Harness Engineering Unified Framework:

- ✅ **Temporal Scalability**: Independent verification, context management, sprint contracts
- ✅ **Spatial Scalability**: Coordinator mode, worktree isolation, team management
- ✅ **Interaction Scalability**: Executable constraints, permission rules, auto-mode
- ✅ **Recursive Planning**: Full Planner → Generator → Evaluator separation
- ✅ **Self-Evaluation Distortion Prevention**: State-isolated verification agent

The codebase demonstrates Anthropic's focus on **runtime correction** (时间可扩展性) as the primary dimension, with supporting implementations for spatial and interaction scalability.

---

*上级目录: [[Research 总览 MOC]]*  
*分类: [[AI Systems]]*  
*相关: [[OpenClaw Harness Engineering Analysis]], [[oh-my-codex Harness Engineering Analysis]], [[Hermes Agent Harness Engineering Analysis]]*