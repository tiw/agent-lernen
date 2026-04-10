"""
网络工具集 —— 让 AI Agent 搜索和抓取网页内容。
参考 Claude Code 的 WebSearch / WebFetch 工具设计。
"""

import re
import time
import hashlib
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
    results: list
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
    """

    def __init__(
        self,
        max_results: int = 10,
        allowed_domains: Optional[list] = None,
        blocked_domains: Optional[list] = None,
    ):
        if not HAS_DDG:
            raise ImportError(
                "duckduckgo-search is required. Install: pip install duckduckgo-search"
            )
        self.max_results = max_results
        self.allowed_domains = [d.lower() for d in (allowed_domains or [])]
        self.blocked_domains = [d.lower() for d in (blocked_domains or [])]

    def call(self, query: str) -> WebSearchResult:
        """执行网络搜索。"""
        if not query or len(query.strip()) < 2:
            raise ValueError("Search query must be at least 2 characters")

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

        return WebSearchResult(
            query=query,
            results=filtered,
            duration_seconds=duration,
            num_results=len(filtered),
        )


# ============================================================
# WebFetchTool
# ============================================================

class WebFetchTool:
    """
    网页内容抓取工具。
    """

    MAX_CONTENT_LENGTH = 50_000
    MAX_MARKDOWN_LENGTH = 30_000

    def __init__(self, timeout: int = 30):
        if not HAS_REQUESTS:
            raise ImportError(
                "requests is required. Install: pip install requests"
            )
        self.timeout = timeout

    def call(self, url: str, prompt: Optional[str] = None) -> WebFetchResult:
        """抓取网页内容。"""
        start_time = time.time()

        try:
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

            # 检查重定向
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

            # 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                return WebFetchResult(
                    url=url,
                    status_code=response.status_code,
                    content=f"Unsupported content type: {content_type}",
                    bytes_fetched=len(response.content),
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # 转换为 Markdown
            html_content = response.text
            markdown_content = self._html_to_markdown(html_content)

            # 截断
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
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            markdown = md(str(soup), heading_style='ATX')
            markdown = re.sub(r'\n{3,}', '\n\n', markdown)
            return markdown.strip()

        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['script', 'style']):
                tag.decompose()
            return soup.get_text(separator='\n', strip=True)

        # 最简回退：去除 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
