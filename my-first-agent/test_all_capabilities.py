"""
My Agent 完整能力测试套件
测试所有已实现的功能模块
从零手写 AI Agent 课程 · 综合测试
"""

import os
import sys
import asyncio
import tempfile
import shutil
from pathlib import Path

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")

def print_section(text):
    print(f"\n{Colors.OKCYAN}▸ {text}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKBLUE}ℹ {text}{Colors.ENDC}")


# ────────────────────────────────────────────────────────
# 测试 1: 工具系统
# ────────────────────────────────────────────────────────

def test_tools():
    print_header("🧪 测试 1: 工具系统")

    from tools import (
        BashTool, PythonTool,
        FileReadTool, FileWriteTool, FileEditTool, FileSandbox,
        WebSearchTool, WebFetchTool,
        GrepTool, GlobTool,
    )

    print_section("BashTool")
    bash = BashTool()
    result = bash.execute("echo 'Hello World'")
    if "Hello World" in result:
        print_success(f"BashTool: {result.strip()}")
    else:
        print_error("BashTool 失败")

    print_section("PythonTool")
    python = PythonTool()
    result = python.execute("print(sum(range(1, 101)))")
    if "5050" in result:
        print_success(f"PythonTool: 1+2+...+100 = {result.strip()}")
    else:
        print_error("PythonTool 失败")

    print_section("FileReadTool + FileWriteTool")
    sandbox = FileSandbox(allowed_dirs=[os.getcwd()])
    write_tool = FileWriteTool(sandbox=sandbox)
    read_tool = FileReadTool(sandbox=sandbox)

    test_file = os.path.join(os.getcwd(), "test_capability.txt")
    write_tool.call(test_file, "Test content line 1\nTest content line 2")
    result = read_tool.call(test_file)
    if "Test content" in result.content:
        print_success(f"FileRead/Write: 读取 {result.num_lines} 行")
    else:
        print_error("FileRead/Write 失败")

    os.unlink(test_file)

    print_section("FileEditTool")
    edit_tool = FileEditTool(sandbox=sandbox)
    write_tool.call(test_file, "Hello World")
    result = edit_tool.call(test_file, "Hello World", "Hello Agent")
    if result.success:
        print_success("FileEditTool: 编辑成功")
    else:
        print_error("FileEditTool 失败")

    os.unlink(test_file)

    print_section("GrepTool")
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "test.py"), 'w') as f:
            f.write("def hello():\n    print('Hi')\n")

        grep = GrepTool(root_dir=tmpdir)
        result = grep.call("def ", output_mode='files_with_matches')
        if result.num_files >= 1:
            print_success(f"GrepTool: 找到 {result.num_files} 个文件")
        else:
            print_error("GrepTool 失败")

    print_section("GlobTool")
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "src"))
        with open(os.path.join(tmpdir, "src", "main.py"), 'w') as f:
            f.write("# test")

        glob = GlobTool(root_dir=tmpdir)
        result = glob.call("**/*.py")
        if result.num_files >= 1:
            print_success(f"GlobTool: 找到 {result.num_files} 个 Python 文件")
        else:
            print_error("GlobTool 失败")

    print_section("WebFetchTool (需要网络)")
    try:
        fetch = WebFetchTool(timeout=5)
        result = fetch.call("https://httpbin.org/html")
        if result.status_code == 200:
            print_success(f"WebFetchTool: {result.bytes_fetched} bytes")
        else:
            print_warning(f"WebFetchTool: 状态码 {result.status_code}")
    except Exception as e:
        print_warning(f"WebFetchTool: 网络不可用 - {e}")

    print_success("工具系统测试完成")


# ────────────────────────────────────────────────────────
# 测试 2: 记忆系统
# ────────────────────────────────────────────────────────

def test_memory():
    print_header("🧠 测试 2: 记忆系统")

    from memory import (
        TokenEstimator, MemoryStore, Memory, MemoryType,
        EmbeddingStore, SemanticMemorySearch,
        SessionMemory,
    )

    print_section("TokenEstimator")
    estimator = TokenEstimator()
    text = "Hello, this is a test message for token estimation."
    tokens = estimator.estimate(text)
    print_success(f"TokenEstimator: '{text[:30]}...' ≈ {tokens} tokens")

    print_section("MemoryStore (SQLite)")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        store = MemoryStore(db_path)

        memory = Memory(
            content="用户喜欢使用 Python 编程",
            memory_type=MemoryType.USER_PREF,
            source="test",
            tags=["python", "preference"],
            importance=0.8,
        )
        store.add(memory)

        results = store.search(query="Python")
        if len(results) >= 1:
            print_success(f"MemoryStore: 找到 {len(results)} 条记忆")
        else:
            print_error("MemoryStore 失败")

    print_section("EmbeddingStore + SemanticSearch")
    with tempfile.TemporaryDirectory() as tmpdir:
        mem_db = os.path.join(tmpdir, "mem.db")
        emb_db = os.path.join(tmpdir, "emb.db")

        mem_store = MemoryStore(mem_db)
        emb_store = EmbeddingStore(emb_db)

        memories = [
            Memory(content="Python 编程教程", memory_type=MemoryType.FACT),
            Memory(content="JavaScript 入门指南", memory_type=MemoryType.FACT),
            Memory(content="数据库设计原则", memory_type=MemoryType.FACT),
        ]
        for m in memories:
            mid = mem_store.add(m)
            emb_store.add(mid, m.content)

        search = SemanticMemorySearch(mem_store, emb_store)
        results = search.search("编程", mode='semantic', limit=5)
        if len(results) >= 1:
            print_success(f"SemanticSearch: 找到 {len(results)} 条相关记忆")
        else:
            print_warning("SemanticSearch: 无结果")

    print_section("SessionMemory")
    session = SessionMemory()
    session.record_tool_call()
    session.record_tool_call()
    should_update = session.should_update(6000)
    print_success(f"SessionMemory: 应该更新 = {should_update}")

    print_success("记忆系统测试完成")


# ────────────────────────────────────────────────────────
# 测试 3: 任务系统
# ────────────────────────────────────────────────────────

async def test_tasks_async():
    print_header("📋 测试 3: 任务系统")

    from tasks import TaskType, TaskStatus, ShellTask, TaskRegistry

    print_section("ShellTask")
    task = ShellTask("echo 'Hello from ShellTask'", description="测试任务")
    result = await task.run()
    if "Hello from ShellTask" in result:
        print_success(f"ShellTask: {result.strip()}")
    else:
        print_error("ShellTask 失败")

    print_section("TaskRegistry")
    registry = TaskRegistry()

    def on_notify(msg):
        print_info(f"  通知：{msg['event']} - Task {msg['task_id']}")

    registry.on_notification(on_notify)

    task = ShellTask("echo 'Registry test'", description="注册表测试")
    registry.register(task)
    print_success(f"TaskRegistry: 注册任务 {task.task_id}")

    asyncio_task = await registry.start(task.task_id)
    await asyncio_task
    print_success(f"TaskRegistry: 任务状态 {task.state.status.value}")

    print_success("任务系统测试完成")


# ────────────────────────────────────────────────────────
# 测试 4: Hook 系统
# ────────────────────────────────────────────────────────

async def test_hooks_async():
    print_header("🪝 测试 4: Hook 系统")

    from hooks import HookEvent, HookContext, EventBus, HookRegistry
    from hooks.builtin import security_scan, SessionPersister

    print_section("EventBus")
    bus = EventBus()
    call_log = []

    def hook1(ctx):
        call_log.append("hook1")

    async def hook2(ctx):
        call_log.append("hook2")

    bus.on(HookEvent.TOOL_CALL, hook1)
    bus.on(HookEvent.TOOL_CALL, hook2)

    ctx = HookContext(
        event=HookEvent.TOOL_CALL,
        data={"tool_name": "bash", "command": "ls -la"},
    )
    await bus.emit(HookEvent.TOOL_CALL, ctx)

    if len(call_log) == 2:
        print_success(f"EventBus: 执行 {len(call_log)} 个 Hook")
    else:
        print_error("EventBus 失败")

    print_section("SecurityScanner Hook")
    bus = EventBus()
    bus.on(HookEvent.TOOL_CALL, security_scan)

    ctx = HookContext(
        event=HookEvent.TOOL_CALL,
        data={"tool_name": "bash", "command": "rm -rf /"},
    )
    await bus.emit(HookEvent.TOOL_CALL, ctx)

    if ctx.should_abort:
        print_success(f"SecurityScanner: 已拦截 - {ctx.abort_reason}")
    else:
        print_error("SecurityScanner 未拦截")

    print_section("SessionPersister")
    with tempfile.TemporaryDirectory() as tmpdir:
        persister = SessionPersister(storage_dir=tmpdir)

        ctx = HookContext(
            event=HookEvent.SESSION_START,
            data={},
            session_id="test-001",
        )
        await persister.on_session_start(ctx)
        print_success("SessionPersister: 会话启动")

        ctx = HookContext(
            event=HookEvent.SESSION_END,
            data={"history": [{"role": "user", "content": "Hello"}]},
            session_id="test-001",
        )
        await persister.on_session_end(ctx)
        print_success("SessionPersister: 会话保存")

    print_success("Hook 系统测试完成")


# ────────────────────────────────────────────────────────
# 测试 5: 多 Agent 协作
# ────────────────────────────────────────────────────────

async def test_team_async():
    print_header("👥 测试 5: 多 Agent 协作")

    from team import (
        RoleType, SimulatedAgent, MessageBus, TaskBoard, Coordinator,
        PLANNER_ROLE, CODER_ROLE, TESTER_ROLE,
    )

    print_section("SimulatedAgent")
    agent = SimulatedAgent(PLANNER_ROLE)
    result = await agent.execute("Build a web app")
    if "Project Plan" in result:
        print_success(f"SimulatedAgent: {result[:50]}...")
    else:
        print_error("SimulatedAgent 失败")

    print_section("MessageBus")
    bus = MessageBus()
    bus.register_agent("agent1")
    bus.register_agent("agent2")

    from team.message_bus import Message
    await bus.send(Message(sender="agent1", receiver="agent2", content="Hello"))
    msg = await bus.receive("agent2")
    if msg and msg.content == "Hello":
        print_success("MessageBus: 消息传递成功")
    else:
        print_error("MessageBus 失败")

    print_section("TaskBoard")
    board = TaskBoard()
    task1 = await board.create_task("Research", priority=1)
    task2 = await board.create_task("Implement", priority=1, dependencies=[task1.id])

    claimed = await board.claim_task("agent1")
    if claimed:
        print_success(f"TaskBoard: 认领任务 #{claimed.id}")

    await board.complete_task(task1.id, "Done")
    print_success(f"TaskBoard: 完成 {board.completed_count}/{board.total_count}")

    print_section("Coordinator")
    coordinator = Coordinator("test-team")
    coordinator.add_roles([RoleType.PLANNER, RoleType.CODER, RoleType.TESTER])

    result = await coordinator.plan_and_execute("Build a calculator")
    if result['tasks_completed'] > 0:
        print_success(f"Coordinator: 完成 {result['tasks_completed']} 个任务")
    else:
        print_warning("Coordinator: 无任务完成")

    print_success("多 Agent 协作测试完成")


# ────────────────────────────────────────────────────────
# 测试 6: CLI 界面
# ────────────────────────────────────────────────────────

def test_cli():
    print_header("💻 测试 6: CLI 界面")

    from cli import ThemeConfig, AGENT_THEME, CommandRegistry, AgentCompleter

    print_section("ThemeConfig")
    print_success(f"ThemeConfig: 提示符 = {ThemeConfig.PROMPT_PREFIX}")
    print_success(f"ThemeConfig: 状态 = {ThemeConfig.STATUS_READY}")

    print_section("CommandRegistry")
    registry = CommandRegistry()
    from cli.commands import register_builtin_commands
    register_builtin_commands(registry)

    cmds = registry.list_commands()
    print_success(f"CommandRegistry: {len(cmds)} 个命令")

    print_section("AgentCompleter")
    from prompt_toolkit.document import Document
    completer = AgentCompleter()

    doc = Document(text="/he", cursor_position=3)
    completions = list(completer.get_completions(doc, None))
    if len(completions) >= 1:
        print_success(f"AgentCompleter: {len(completions)} 个补全建议")
    else:
        print_warning("AgentCompleter: 无补全")

    print_success("CLI 界面测试完成")


# ────────────────────────────────────────────────────────
# 主测试流程
# ────────────────────────────────────────────────────────

async def run_all_tests():
    print_header("🦞 My Agent 完整能力测试")

    print_info("测试所有已实现的功能模块")
    print_info("按任意键开始...")

    # 测试 1: 工具系统
    try:
        test_tools()
    except Exception as e:
        print_error(f"工具系统测试失败：{e}")
        import traceback
        traceback.print_exc()

    # 测试 2: 记忆系统
    try:
        test_memory()
    except Exception as e:
        print_error(f"记忆系统测试失败：{e}")
        import traceback
        traceback.print_exc()

    # 测试 3: 任务系统
    try:
        await test_tasks_async()
    except Exception as e:
        print_error(f"任务系统测试失败：{e}")
        import traceback
        traceback.print_exc()

    # 测试 4: Hook 系统
    try:
        await test_hooks_async()
    except Exception as e:
        print_error(f"Hook 系统测试失败：{e}")
        import traceback
        traceback.print_exc()

    # 测试 5: 多 Agent 协作
    try:
        await test_team_async()
    except Exception as e:
        print_error(f"多 Agent 协作测试失败：{e}")
        import traceback
        traceback.print_exc()

    # 测试 6: CLI 界面
    try:
        test_cli()
    except Exception as e:
        print_error(f"CLI 界面测试失败：{e}")
        import traceback
        traceback.print_exc()

    print_header("🎉 测试完成")
    print_success("所有能力模块测试完毕")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
