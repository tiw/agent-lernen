# 第八章学习总结：技能系统

> 学习时间：2026-04-14  
> 学习状态：✅ 完成  
> 核心收获：实现技能系统，让 Agent 拥有专家级能力

---

## 📖 本章要点

### 技能 vs 工具

| 维度 | 工具（Tools） | 技能（Skills） |
|------|-------------|--------------|
| 本质 | 代码函数 | Markdown 文档 |
| 能力 | 执行操作 | 指导行为 |
| 扩展 | 需要写代码 | 只需要写 Markdown |
| 粒度 | 原子操作 | 复合流程 |

**关键理解**：技能不是代码，是**提示词工程的结构化封装**。

### 技能文件格式

```markdown
---
name: skill-name
description: 简短描述
when_to_use: 何时使用
allowed-tools: Read, Write
arguments: arg1 arg2
---

# Skill Content

详细指导内容...
```

---

## 💻 已实现代码

### 1. SkillFrontmatter（技能元数据）✅

### 2. Skill（技能类）✅

### 3. SkillLoader（技能加载器）✅

---

## 📊 测试结果

```
✅ frontmatter 解析
✅ 技能加载
✅ prompt 构建
✅ 技能搜索
```

---

## 📁 创建的文件

```
~/my-first-agent/skills/
├── __init__.py
├── skill.py          # 技能类（8.5KB）
└── loader.py         # 加载器（7KB）

~/my-first-agent/my-skills/
├── code-review/
│   └── SKILL.md
└── article-writing/
    └── SKILL.md
```

---

_总结完成时间：2026-04-14_  
_学习时长：约 1.5 小时_  
_状态：第八章完成 ✅_  
_下一步：继续学习第九章（MCP 协议）_
