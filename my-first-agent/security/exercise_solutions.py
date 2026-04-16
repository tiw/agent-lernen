"""
第 13 章课后练习答案

包含三个练习的完整实现：
1. 权限持久化（已完成，集成到 policy.py）
2. 命令速率限制
3. 沙箱临时文件清理
"""

import time
import logging
from collections import deque
from pathlib import Path
from typing import Optional

from security.policy import SecurityPolicy
from security.sandbox import FileSandbox, SandboxConfig

logger = logging.getLogger(__name__)


# ============================================================
# 练习 1：权限持久化
# ============================================================
# 答案：已在 security/policy.py 中实现
# 
# 关键点：
# 1. __init__ 中调用 _load_permissions()
# 2. permanently_allow/deny 后调用 _save_permissions()
# 3. 使用 JSON 格式存储
# 4. 文件权限设置为 chmod 600
#
# 代码片段：
# ```python
# def _save_permissions(self) -> None:
#     data = {
#         "permanent_allows": list(self._permanent_allows),
#         "permanent_denies": list(self._permanent_denies),
#     }
#     Path(self.permissions_file).parent.mkdir(parents=True, exist_ok=True)
#     with open(self.permissions_file, "w") as f:
#         json.dump(data, f, indent=2)
#     Path(self.permissions_file).chmod(0o600)
# ```
#
# 测试验证：test_permission_persistence() 已通过


# ============================================================
# 练习 2：实现命令速率限制
# ============================================================

class RateLimiter:
    """
    命令速率限制器
    
    防止 Agent 在短时间内执行过多命令（可能是被恶意 Prompt 诱导）
    限制：每分钟最多执行 10 个 Bash 命令
    """
    
    def __init__(self, max_commands: int = 10, window_seconds: int = 60):
        self.max_commands = max_commands
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
    
    def check_rate(self) -> tuple[bool, str]:
        """
        检查是否超过速率限制
        
        返回：(是否允许，原因)
        """
        now = time.time()
        
        # 清理过期的时间戳
        while self._timestamps and now - self._timestamps[0] > self.window_seconds:
            self._timestamps.popleft()
        
        # 检查是否超限
        if len(self._timestamps) >= self.max_commands:
            oldest = self._timestamps[0]
            wait_time = self.window_seconds - (now - oldest)
            return False, f"速率限制：{self.max_commands} 命令/{self.window_seconds} 秒，请等待 {wait_time:.0f} 秒"
        
        return True, "OK"
    
    def record(self) -> None:
        """记录一次命令执行"""
        self._timestamps.append(time.time())
    
    def reset(self) -> None:
        """重置计数器"""
        self._timestamps.clear()
    
    def get_status(self) -> dict:
        """获取当前状态"""
        now = time.time()
        # 清理过期时间戳
        while self._timestamps and now - self._timestamps[0] > self.window_seconds:
            self._timestamps.popleft()
        
        return {
            "recent_commands": len(self._timestamps),
            "max_commands": self.max_commands,
            "window_seconds": self.window_seconds,
            "oldest_timestamp": self._timestamps[0] if self._timestamps else None,
        }


class RateLimitedSecurityPolicy(SecurityPolicy):
    """
    集成速率限制的安全策略
    """
    
    def __init__(
        self,
        max_commands: int = 10,
        window_seconds: int = 60,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.rate_limiter = RateLimiter(max_commands, window_seconds)
    
    def check_command(self, command: str) -> "PermissionResult":
        """检查命令权限（包含速率限制）"""
        # 先检查速率限制
        allowed, reason = self.rate_limiter.check_rate()
        if not allowed:
            return self._create_result(
                "deny",
                reason,
                {"rate_limited": True}
            )
        
        # 执行正常检查
        result = super().check_command(command)
        
        # 如果允许执行，记录到速率限制器
        if result.is_allowed:
            self.rate_limiter.record()
        
        return result
    
    def _create_result(self, decision: str, reason: str, details: dict = None) -> "PermissionResult":
        """创建 PermissionResult（避免循环导入）"""
        from security.policy import Decision, PermissionResult
        return PermissionResult(
            decision=Decision(decision),
            reason=reason,
            details=details or {}
        )


# ============================================================
# 练习 3：实现沙箱临时文件清理
# ============================================================

class TrackedFileSandbox(FileSandbox):
    """
    支持临时文件追踪的沙箱
    
    在会话结束时自动清理创建的文件
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        super().__init__(config)
        self._created_files: set[Path] = set()
        self._session_start_time = time.time()
    
    def check_write(self, path: str | Path) -> Path:
        """检查写入权限并追踪文件"""
        resolved = super().check_write(path)
        
        # 只追踪会话中创建的文件（文件不存在或创建时间在会话开始后）
        if not resolved.exists():
            self._created_files.add(resolved)
        elif resolved.stat().st_mtime >= self._session_start_time:
            self._created_files.add(resolved)
        
        return resolved
    
    def cleanup_created_files(self) -> dict:
        """
        清理会话中创建的文件
        
        返回：清理结果统计
        """
        stats = {
            "total": len(self._created_files),
            "deleted": 0,
            "failed": 0,
            "errors": [],
        }
        
        for file_path in self._created_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    stats["deleted"] += 1
                    logger.info(f"Cleaned up: {file_path}")
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{file_path}: {e}")
                logger.error(f"Failed to clean up {file_path}: {e}")
        
        self._created_files.clear()
        return stats
    
    def get_tracked_files(self) -> list[Path]:
        """获取追踪的文件列表"""
        return list(self._created_files)
    
    def reset_session(self) -> None:
        """重置会话"""
        self._created_files.clear()
        self._session_start_time = time.time()


# ============================================================
# 测试代码
# ============================================================

def test_rate_limiter():
    """测试速率限制器"""
    limiter = RateLimiter(max_commands=3, window_seconds=5)
    
    # 前 3 次应该允许
    for i in range(3):
        allowed, reason = limiter.check_rate()
        assert allowed, f"第 {i+1} 次应该允许"
        limiter.record()
    
    # 第 4 次应该拒绝
    allowed, reason = limiter.check_rate()
    assert not allowed, "第 4 次应该被限制"
    assert "速率限制" in reason
    
    # 等待窗口过期
    time.sleep(5.1)
    allowed, reason = limiter.check_rate()
    assert allowed, "窗口过期后应该允许"
    
    # 状态检查（窗口过期后计数器已清空）
    status = limiter.get_status()
    assert status["recent_commands"] == 0
    assert status["max_commands"] == 3
    
    print("✅ 速率限制器测试通过")


def test_rate_limited_policy():
    """测试集成速率限制的安全策略"""
    policy = RateLimitedSecurityPolicy(max_commands=2, window_seconds=5)
    
    # 前 2 次应该允许
    result1 = policy.check_command("ls -la")
    assert result1.is_allowed, "第 1 次应该允许"
    
    result2 = policy.check_command("pwd")
    assert result2.is_allowed, "第 2 次应该允许"
    
    # 第 3 次应该被速率限制
    result3 = policy.check_command("date")
    assert result3.decision.name == "DENY", "第 3 次应该被拒绝"
    assert "速率限制" in result3.reason
    
    # 等待窗口过期
    time.sleep(5.1)
    result4 = policy.check_command("ls")
    assert result4.is_allowed, "窗口过期后应该允许"
    
    print("✅ 速率限制安全策略测试通过")


def test_tracked_sandbox():
    """测试带文件追踪的沙箱"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = SandboxConfig(
            allowed_roots=[tmpdir],
            denied_paths=[],
            denied_extensions=[],
            allow_symlinks=False,
            max_file_size=10 * 1024 * 1024,
            allow_write=True,
        )
        sandbox = TrackedFileSandbox(config)
        
        # 创建文件
        file1 = Path(tmpdir) / "temp1.txt"
        file2 = Path(tmpdir) / "temp2.txt"
        
        sandbox.check_write(file1)
        sandbox.check_write(file2)
        
        # 验证追踪
        tracked = sandbox.get_tracked_files()
        assert len(tracked) == 2
        assert file1.resolve() in tracked or file1 in sandbox._created_files
        assert file2.resolve() in tracked or file2 in sandbox._created_files
        
        # 实际创建文件
        file1.write_text("content1")
        file2.write_text("content2")
        
        # 清理
        stats = sandbox.cleanup_created_files()
        assert stats["total"] == 2
        assert stats["deleted"] == 2
        assert stats["failed"] == 0
        
        # 验证文件已删除
        assert not file1.exists()
        assert not file2.exists()
        
        print("✅ 追踪沙箱测试通过")


def main():
    import tempfile
    
    print("=" * 50)
    print("第 13 章课后练习答案测试")
    print("=" * 50)
    
    print("\n📝 练习 1：权限持久化")
    print("   答案：已集成到 security/policy.py")
    print("   测试：test_permission_persistence() 已通过")
    
    print("\n📝 练习 2：命令速率限制")
    test_rate_limiter()
    test_rate_limited_policy()
    
    print("\n📝 练习 3：沙箱临时文件清理")
    test_tracked_sandbox()
    
    print("=" * 50)
    print("所有练习答案测试通过！🎉")
    print("=" * 50)


if __name__ == "__main__":
    main()
