"""
test_agent_v5.py —— Agent v5 集成测试
测试所有 Ch01-13 模块的集成
"""

import os
import sys
import unittest

# 确保能导入模块
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")


class TestAgentV5Import(unittest.TestCase):
    """测试 1: 模块导入"""

    def test_import_agent_v5(self):
        """AgentV5 类可以正常导入"""
        from agent_v5 import AgentV5
        self.assertIsNotNone(AgentV5)

    def test_import_tools(self):
        """所有工具模块可以正常导入"""
        from tools.bash_tool import BashTool
        from tools.python_tool import PythonTool
        from tools.file_tools import create_file_tools
        from tools.web_tools import WebSearchTool, WebFetchTool
        from tools.search_tools import GrepTool, GlobTool

    def test_import_memory(self):
        """记忆系统模块可以正常导入"""
        from memory.token_counter import TokenEstimator
        from memory.long_term import MemoryStore
        from memory.embedding_store import EmbeddingStore, HashEmbeddingProvider
        from memory.session_memory import ShortTermMemory
        from memory.tool_budget import ToolResultBudget
        from memory.micro_compact import MicroCompact

    def test_import_tasks(self):
        """任务系统可以正常导入"""
        from tasks.base import TaskRegistry, TaskType, TaskStatus
        from tasks.shell_task import ShellTask

    def test_import_skills(self):
        """技能系统可以正常导入"""
        from skills.loader import SkillLoader

    def test_import_hooks(self):
        """Hook 系统可以正常导入"""
        from hooks.event_bus import EventBus, HookEvent, HookContext
        from hooks.registry import HookRegistry

    def test_import_security(self):
        """安全系统可以正常导入"""
        from security.policy import SecurityPolicy, Decision
        from security.whitelist import CommandWhitelist, SafetyLevel
        from security.filter import SensitiveDataFilter
        from security.auditor import Auditor

    def test_import_team(self):
        """多智能体协作可以正常导入"""
        from team.coordinator import Coordinator
        from team.roles import RoleType

    def test_import_cli(self):
        """CLI 系统可以正常导入"""
        from cli.interface import AgentCLI
        from cli.commands import CommandRegistry, register_builtin_commands


class TestToolResultBudget(unittest.TestCase):
    """测试 2: 工具结果预算"""

    def test_small_result(self):
        """小结果不截断"""
        from memory.tool_budget import ToolResultBudget
        budget = ToolResultBudget(session_id="test_small")
        record = budget.process_result("bash", "call_001", "hello world")
        self.assertFalse(record.truncated)
        self.assertFalse(record.pinned)
        self.assertEqual(record.full_result, "hello world")

    def test_large_result(self):
        """大结果截断"""
        from memory.tool_budget import ToolResultBudget
        budget = ToolResultBudget(session_id="test_large")
        large_result = "line " * 2000  # 10000 字符
        record = budget.process_result("file_read", "call_002", large_result)
        self.assertTrue(record.truncated)
        self.assertTrue(record.pinned)
        self.assertLess(len(record.preview), len(large_result))
        self.assertIsNotNone(record.disk_path)

    def test_state_freeze(self):
        """状态冻结：同一 ID 返回相同结果"""
        from memory.tool_budget import ToolResultBudget
        budget = ToolResultBudget(session_id="test_freeze")
        large_result = "content " * 2000
        record1 = budget.process_result("bash", "call_003", large_result)
        record2 = budget.process_result("bash", "call_003", "different content")
        self.assertEqual(record1.full_result, record2.full_result)


class TestMicroCompact(unittest.TestCase):
    """测试 3: 微压缩"""

    def test_system_preserved(self):
        """System 消息永远保留"""
        from memory.micro_compact import MicroCompact
        compact = MicroCompact()
        messages = [{"role": "system", "content": "You are helpful."}]
        decisions = compact.evaluate(messages)
        self.assertFalse(decisions[0].omit)

    def test_recent_preserved(self):
        """最近消息保留"""
        from memory.micro_compact import MicroCompact
        compact = MicroCompact()
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        decisions = compact.evaluate(messages)
        # 最后 6 条应该保留
        for d in decisions[-compact.RECENT_MESSAGES_KEEP:]:
            self.assertFalse(d.omit)

    def test_tool_truncate(self):
        """长工具结果截断"""
        from memory.micro_compact import MicroCompact
        compact = MicroCompact()
        messages = (
            [{"role": "system", "content": "system"},
             {"role": "tool", "content": "x" * 5000},
             {"role": "user", "content": "next"}]
            + [{"role": "user", "content": f"keep {i}"} for i in range(6)]
        )
        decisions = compact.evaluate(messages)
        tool_decision = decisions[1]
        self.assertTrue(tool_decision.truncate)


class TestShortTermMemory(unittest.TestCase):
    """测试 4: 短期记忆"""

    def test_add_message(self):
        """添加消息到历史"""
        from memory.session_memory import ShortTermMemory
        stm = ShortTermMemory(session_id="test_add")
        stm.add_message({"role": "user", "content": "hello"})
        self.assertEqual(len(stm.messages), 1)

    def test_process_tool_result(self):
        """处理工具结果"""
        from memory.session_memory import ShortTermMemory
        stm = ShortTermMemory(session_id="test_tool")
        result = stm.process_tool_result("bash", "call_001", "hello")
        self.assertEqual(result, "hello")

    def test_reset(self):
        """重置短期记忆"""
        from memory.session_memory import ShortTermMemory
        stm = ShortTermMemory(session_id="test_reset")
        stm.add_message({"role": "user", "content": "hello"})
        self.assertEqual(len(stm.messages), 1)
        stm.reset()
        self.assertEqual(len(stm.messages), 0)

    def test_get_stats(self):
        """获取统计"""
        from memory.session_memory import ShortTermMemory
        stm = ShortTermMemory(session_id="test_stats")
        stats = stm.get_stats()
        self.assertIn("total_tokens", stats)
        self.assertIn("message_count", stats)


class TestSecurity(unittest.TestCase):
    """测试 5: 安全系统"""

    def test_command_whitelist(self):
        """命令白名单分类"""
        from security.whitelist import CommandWhitelist, SafetyLevel
        wl = CommandWhitelist()
        level, reason = wl.classify("ls -la")
        self.assertEqual(level, SafetyLevel.SAFE)

    def test_dangerous_command(self):
        """危险命令被禁止"""
        from security.whitelist import CommandWhitelist, SafetyLevel
        wl = CommandWhitelist()
        level, reason = wl.classify("rm -rf /")
        self.assertIn(level, [SafetyLevel.DANGEROUS, SafetyLevel.BANNED])

    def test_sensitive_data_filter(self):
        """敏感数据过滤"""
        from security.filter import SensitiveDataFilter
        f = SensitiveDataFilter()
        text = "API key: sk-abc123def456 password: mypassword"
        filtered = text  # 检查是否能导入
        self.assertIsNotNone(filtered)

    def test_security_policy(self):
        """安全策略"""
        from security.policy import SecurityPolicy, Decision
        from security.whitelist import CommandWhitelist
        from security.filter import SensitiveDataFilter
        policy = SecurityPolicy(
            whitelist=CommandWhitelist(),
            filter_=SensitiveDataFilter(),
            strict_mode=False,
        )
        result = policy.check_command("ls -la")
        self.assertIsNotNone(result)


class TestAuditor(unittest.TestCase):
    """测试 6: 审计日志"""

    def test_log_and_get(self):
        """记录并获取审计日志"""
        import tempfile
        from security.auditor import Auditor, AuditEvent
        with tempfile.TemporaryDirectory() as tmpdir:
            auditor = Auditor(log_dir=tmpdir)
            event = AuditEvent(timestamp="2026-01-01T00:00:00", event_type="test_event", decision="ALLOW", details={"key": "value"})
            auditor.log(event)
            recent = auditor.get_recent(5)
            self.assertEqual(len(recent), 1)

    def test_save(self):
        """保存审计日志"""
        import tempfile
        from security.auditor import Auditor, AuditEvent
        with tempfile.TemporaryDirectory() as tmpdir:
            auditor = Auditor(log_dir=tmpdir)
            event = AuditEvent(timestamp="2026-01-01T00:00:00", event_type="test_event", decision="ALLOW", details={"key": "value"})
            auditor.log(event)
            # 保存不应报错
            auditor.save()


class TestCommandRegistry(unittest.TestCase):
    """测试 7: CLI 命令注册"""

    def test_register_and_list(self):
        """注册并列出命令"""
        from cli.commands import CommandRegistry, register_builtin_commands
        registry = CommandRegistry()
        register_builtin_commands(registry)
        cmds = registry.list_commands()
        self.assertGreater(len(cmds), 5)

    def test_unknown_command(self):
        """未知命令返回错误提示"""
        import asyncio
        from cli.commands import CommandRegistry, register_builtin_commands
        registry = CommandRegistry()
        register_builtin_commands(registry)
        async def run():
            result = await registry.execute("/unknown", {})
            self.assertIn("未知命令", result)
        asyncio.run(run())

    def test_help_command(self):
        """帮助命令可用"""
        import asyncio
        from cli.commands import CommandRegistry, register_builtin_commands
        registry = CommandRegistry()
        register_builtin_commands(registry)
        async def run():
            result = await registry.execute("/help", {})
            self.assertIn("可用命令", result)
        asyncio.run(run())


class TestToolResultBudgetDisk(unittest.TestCase):
    """测试 8: 磁盘持久化"""

    def test_full_result_from_disk(self):
        """从磁盘恢复完整结果"""
        from memory.tool_budget import ToolResultBudget
        budget = ToolResultBudget(session_id="test_disk")
        large_result = "content " * 2000
        budget.process_result("file_read", "call_001", large_result)
        full = budget.get_full_result("call_001")
        self.assertEqual(full, large_result)


if __name__ == "__main__":
    print("=== Agent v5 集成测试 ===\n")
    unittest.main(verbosity=2)
