# Reference Catalog: Major Open-Source Coding Skills & Agents

Use this catalog as a starting point — supplement with web search for recent developments.

| Tool/Skill | Type | Key Capabilities | Best For | License |
|------------|------|-----------------|----------|---------|
| **PR-Agent (Qodo)** | PR review agent | `/review`, `/improve`, `/ask`, `/describe`, auto PR descriptions, security detection, code suggestions, multi-git-provider | General PR review automation | Open source |
| **Qodo Skills** | Agent skills | `qodo-get-rules` (semantic rule fetch), `qodo-pr-resolver` (interactive PR issue resolution), severity-based enforcement | Teams using Agent Skills standard (Claude Code, Cursor, etc.) | Open source |
| **Kodus AI / Kody** | Code review agent | Context-aware learning, plain-English rule definition, technical debt tracking, model-agnostic (bring your own API key), multi-repo awareness | Custom rule enforcement, cost-conscious teams, air-gapped deployments | Open source (AGPLv3) |
| **roborev** | Background review agent | Post-commit hooks, continuous review, auto-fix loop, code analysis (duplication, complexity, dead code), multi-agent support | Local/background review, commit-time quality gates | Open source (MIT) |
| **Superpowers** | Skills framework | Brainstorming, planning, TDD enforcement, systematic debugging, subagent-driven dev, two-stage code review, verification | Engineering discipline, structured agent workflows | Open source (MIT) |
| **CodeRabbit** | PR review agent | Line-by-line comments, severity rankings, chat interface, one-click fixes | Fast feedback, team collaboration | Proprietary |
| **Graphite Agent** | PR workflow agent | Stacked PRs, sequenced changes, fix conversion | Teams using stacked PR workflows | Proprietary |
| **Augment Code Review** | AI code review | High precision/recall (Code Review Bench #1), context beyond PR, guardrails | High-signal review, low noise | Proprietary |
| **Rovo Dev (Atlassian)** | PR review agent | Jira requirement validation, built-in security/compliance, customizable standards | Teams in Atlassian ecosystem | Proprietary |
| **Ellipsis** | Action-oriented agent | Reads reviewer comments, auto-implements fixes, runs tests | Reducing review-to-fix cycle | Proprietary |

## Research Guidelines

- Search for the latest version, features, and community activity
- Check GitHub stars, last commit date, and issue response time
- Look for MCP integration, Agent Skills standard compatibility
- Identify the tool's strengths AND its hard limits
