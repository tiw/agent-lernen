"""
网络工具集 —— 让 AI Agent 搜索和抓取网页内容。
参考 Claude Code 的 WebSearch / WebFetch 工具设计。
从零手写 AI Agent 课程 · 第 4 章
"""

from __future__ import annotations

import re
import time
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from markdownify import markdownify as md
    HAS_MARKDOWNIFY = True
except ImportError:
    HAS_MARKDOWNIFY = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ============================================================
# 搜索结果缓存
# ============================================================

class SearchCache:
    """
    搜索结果缓存 — 避免重复搜索相同内容
    
    用法：
        cache = SearchCache(ttl=3600)  # 1 小时有效期
        result = cache.get(query)
        if result is None:
            result = search(query)
            cache.set(query, result)
    """
    
    def __init__(self, ttl: int = 3600, cache_file: Optional[str] = None):
        """
        Args:
            ttl: 缓存有效期（秒），默认 1 小时
            cache_file: 可选，持久化缓存文件路径
        """
        self.ttl = ttl
        self.cache_file = cache_file
        self.cache: dict[str, tuple[dict, float]] = {}
        
        if cache_file:
            self._load_from_file()
    
    def _generate_key(self, query: str) -> str:
        """生成缓存 key"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def get(self, query: str) -> Optional[WebSearchResult]:
        """获取缓存的搜索结果"""
        key = self._generate_key(query)
        
        if key in self.cache:
            result_dict, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return WebSearchResult(
                    query=result_dict['query'],
                    results=[SearchResult(**r) for r in result_dict['results']],
                    duration_seconds=result_dict['duration_seconds'],
                    num_results=result_dict['num_results'],
                )
            else:
                del self.cache[key]
        
        return None
    
    def set(self, query: str, result: WebSearchResult) -> None:
        """缓存搜索结果"""
        key = self._generate_key(query)
        
        result_dict = {
            'query': result.query,
            'results': [
                {'title': r.title, 'url': r.url, 'snippet': r.snippet}
                for r in result.results
            ],
            'duration_seconds': result.duration_seconds,
            'num_results': result.num_results,
        }
        
        self.cache[key] = (result_dict, time.time())
        
        if self.cache_file:
            self._save_to_file()
    
    def clear(self) -> None:
        """清除所有缓存"""
        self.cache.clear()
        if self.cache_file and Path(self.cache_file).exists():
            Path(self.cache_file).unlink()
    
    def _load_from_file(self) -> None:
        """从文件加载缓存"""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = {k: (v, float(t)) for k, (v, t) in data.items()}
        except Exception:
            pass
    
    def _save_to_file(self) -> None:
        """保存缓存到文件"""
        try:
            data = {k: (v, str(t)) for k, (v, t) in self.cache.items()}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ============================================================
# 工具结果
# ============================================================

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ''


@dataclass
class WebSearchResult:
    query: str
    results: list[SearchResult]
    duration_seconds: float
    num_results: int

    def to_display(self) -> str:
        lines = [f"Web search results for: \"{self.query}\"", ""]
        for i, r in enumerate(self.results, 1):
            lines.append(f"[{i}] {r.title}")
            lines.append(f"    URL: {r.url}")
            if r.snippet:
                lines.append(f"    {r.snippet}")
            lines.append("")
        lines.append(
            f"Found {self.num_results} results in {self.duration_seconds:.2f}s"
        )
        return '\n'.join(lines)


@dataclass
class WebFetchResult:
    url: str
    status_code: int
    content: str
    bytes_fetched: int
    duration_ms: float
    error: Optional[str] = None

    def to_display(self) -> str:
        if self.error:
            return f"Error fetching {self.url}: {self.error}"
        return (
            f"Fetched {self.url}\n"
            f"Status: {self.status_code}\n"
            f"Size: {self.bytes_fetched} bytes\n"
            f"Duration: {self.duration_ms:.0f}ms\n\n"
            f"{self.content}"
        )


# ============================================================
# WebSearchTool
# ============================================================

class WebSearchTool:
    """
    网络搜索工具。

    参考 Claude Code 的 WebSearchTool：
    - 使用 DuckDuckGo API（免费，无需 API Key）
    - 支持域名白/黑名单
    - 结果数量限制
    """

    name = "web_search"
    description = "执行网络搜索，获取实时信息。适用于查找最新新闻、文档、API 参考等。使用 DuckDuckGo 搜索引擎。"

    def __init__(
        self,
        max_results: int = 10,
        allowed_domains: Optional[list[str]] = None,
        blocked_domains: Optional[list[str]] = None,
        use_cache: bool = True,
        cache_ttl: int = 3600,
        cache_file: Optional[str] = None,
    ):
        """
        Args:
            max_results: 最大返回结果数
            allowed_domains: 只返回这些域名的结果
            blocked_domains: 排除这些域名的结果
            use_cache: 是否使用缓存
            cache_ttl: 缓存有效期（秒）
            cache_file: 可选，持久化缓存文件路径
        """
        if not HAS_DDG:
            raise ImportError(
                "duckduckgo-search is required. Install: pip install duckduckgo-search"
            )
        self.max_results = max_results
        self.allowed_domains = [d.lower() for d in (allowed_domains or [])]
        self.blocked_domains = [d.lower() for d in (blocked_domains or [])]
        self.use_cache = use_cache
        self.cache = SearchCache(ttl=cache_ttl, cache_file=cache_file) if use_cache else None

    def call(self, query: str) -> WebSearchResult:
        """
        执行网络搜索。

        Args:
            query: 搜索关键词

        Returns:
            WebSearchResult 包含搜索结果
        """
        if not query or len(query.strip()) < 2:
            raise ValueError("Search query must be at least 2 characters")

        # 检查缓存
        if self.cache:
            cached_result = self.cache.get(query)
            if cached_result:
                return cached_result

        start_time = time.time()

        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=self.max_results * 2))

        # 域名过滤
        filtered = []
        for r in raw_results:
            domain = urlparse(r.get('href', '')).netloc.lower()

            # 黑名单检查
            if self.blocked_domains and any(
                domain == bd or domain.endswith('.' + bd)
                for bd in self.blocked_domains
            ):
                continue

            # 白名单检查
            if self.allowed_domains and not any(
                domain == ad or domain.endswith('.' + ad)
                for ad in self.allowed_domains
            ):
                continue

            filtered.append(SearchResult(
                title=r.get('title', ''),
                url=r.get('href', ''),
                snippet=r.get('body', ''),
            ))

            if len(filtered) >= self.max_results:
                break

        duration = time.time() - start_time

        result = WebSearchResult(
            query=query,
            results=filtered,
            duration_seconds=duration,
            num_results=len(filtered),
        )

        # 缓存结果
        if self.cache:
            self.cache.set(query, result)

        return result

    def to_openai_format(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词（至少 2 个字符）",
                        },
                    },
                    "required": ["query"],
                },
            }
        }


# ============================================================
# WebFetchTool
# ============================================================

class WebFetchTool:
    """
    网页内容抓取工具。

    参考 Claude Code 的 WebFetchTool：
    - 抓取 URL 内容并转为 Markdown
    - 支持 prompt 引导内容提取
    - 大小限制防止上下文爆炸
    - 处理重定向
    """

    name = "web_fetch"
    description = "抓取网页内容并转换为 Markdown 格式。适用于阅读文档、文章、API 参考等网页内容。"

    MAX_CONTENT_LENGTH = 50_000  # 最大内容长度
    MAX_MARKDOWN_LENGTH = 30_000  # 最大 Markdown 长度

    def __init__(self, timeout: int = 30):
        """
        Args:
            timeout: 请求超时时间（秒）
        """
        if not HAS_REQUESTS:
            raise ImportError(
                "requests is required. Install: pip install requests"
            )
        self.timeout = timeout

    def call(self, url: str, prompt: Optional[str] = None) -> WebFetchResult:
        """
        抓取网页内容。

        Args:
            url: 目标 URL
            prompt: 可选，用于引导内容提取（当有 LLM 可用时使用）

        Returns:
            WebFetchResult 包含抓取结果
        """
        start_time = time.time()

        try:
            # 1. 发送请求
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (compatible; AIAgent/1.0; '
                    '+https://github.com/ai-agent)'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }

            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True,
            )

            # 2. 检查重定向
            if response.history:
                final_url = response.url
                if urlparse(final_url).netloc != urlparse(url).netloc:
                    return WebFetchResult(
                        url=url,
                        status_code=response.status_code,
                        content=(
                            f"REDIRECT DETECTED:\n"
                            f"Original URL: {url}\n"
                            f"Redirect URL: {final_url}\n"
                            f"Status: {response.status_code}\n\n"
                            f"Please fetch the redirected URL instead."
                        ),
                        bytes_fetched=0,
                        duration_ms=(time.time() - start_time) * 1000,
                    )

            # 3. 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                return WebFetchResult(
                    url=url,
                    status_code=response.status_code,
                    content=f"Unsupported content type: {content_type}",
                    bytes_fetched=len(response.content),
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # 4. 转换为 Markdown
            html_content = response.text
            markdown_content = self._html_to_markdown(html_content)

            # 5. 截断
            if len(markdown_content) > self.MAX_MARKDOWN_LENGTH:
                markdown_content = (
                    markdown_content[:self.MAX_MARKDOWN_LENGTH]
                    + "\n\n[Content truncated...]"
                )

            return WebFetchResult(
                url=url,
                status_code=response.status_code,
                content=markdown_content,
                bytes_fetched=len(response.content),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except requests.exceptions.Timeout:
            return WebFetchResult(
                url=url,
                status_code=0,
                content='',
                bytes_fetched=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=f"Request timed out after {self.timeout}s",
            )
        except requests.exceptions.RequestException as e:
            return WebFetchResult(
                url=url,
                status_code=0,
                content='',
                bytes_fetched=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    def _html_to_markdown(self, html: str) -> str:
        """将 HTML 转为 Markdown"""
        if HAS_MARKDOWNIFY and HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')

            # 移除不需要的元素
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()

            markdown = md(str(soup), heading_style='ATX')
            # 清理多余空行
            markdown = re.sub(r'\n{3,}', '\n\n', markdown)
            return markdown.strip()

        # 回退方案：简单文本提取
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            return text[:self.MAX_MARKDOWN_LENGTH]

        # 最简回退：返回原始 HTML
        return html[:self.MAX_MARKDOWN_LENGTH]

    def to_openai_format(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "要抓取的网页 URL",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "可选，用于引导内容提取的问题或指令",
                        },
                    },
                    "required": ["url"],
                },
            }
        }
