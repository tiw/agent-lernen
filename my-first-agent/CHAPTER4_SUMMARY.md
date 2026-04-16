# 第四章学习总结：搜索与网络

> 学习时间：2026-04-14  
> 学习状态：✅ 完成  
> 核心收获：让 AI 突破训练数据限制，获取实时信息和项目上下文

---

## 🎯 学习目标

| 目标 | 完成情况 | 备注 |
|------|----------|------|
| 理解搜索与网络工具分工 | ✅ | WebSearch 找 URL，WebFetch 读内容 |
| 实现 WebSearchTool | ✅ | DuckDuckGo API，域名过滤 |
| 实现 WebFetchTool | ✅ | HTML→Markdown 转换，重定向处理 |
| 实现 GrepTool | ✅ | 三种输出模式，上下文行支持 |
| 实现 GlobTool | ✅ | glob 模式匹配，VCS 目录排除 |
| Agent 集成 | ✅ | 8 个工具协同工作 |

---

## 📝 核心代码

### 1. WebSearchTool（网络搜索）

```python
class WebSearchTool:
    """网络搜索工具 - 使用 DuckDuckGo API"""

    name = "web_search"
    description = "执行网络搜索，获取实时信息"

    def __init__(
        self,
        max_results: int = 10,
        allowed_domains: Optional[list[str]] = None,
        blocked_domains: Optional[list[str]] = None,
    ):
        self.max_results = max_results
        self.allowed_domains = [d.lower() for d in (allowed_domains or [])]
        self.blocked_domains = [d.lower() for d in (blocked_domains or [])]

    def call(self, query: str) -> WebSearchResult:
        """执行网络搜索"""
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

            filtered.append(SearchResult(
                title=r.get('title', ''),
                url=r.get('href', ''),
                snippet=r.get('body', ''),
            ))

        return WebSearchResult(query=query, results=filtered, ...)
```

**关键特性**：
- 使用 DuckDuckGo API（免费，无需 API Key）
- 支持域名白/黑名单过滤
- 结果数量限制

### 2. WebFetchTool（网页抓取）

```python
class WebFetchTool:
    """网页内容抓取工具"""

    MAX_MARKDOWN_LENGTH = 30_000  # 最大 Markdown 长度

    def call(self, url: str, prompt: Optional[str] = None) -> WebFetchResult:
        # 1. 发送请求
        headers = {'User-Agent': 'AIAgent/1.0'}
        response = requests.get(url, headers=headers, timeout=self.timeout)

        # 2. 检查重定向
        if response.history:
            final_url = response.url
            if urlparse(final_url).netloc != urlparse(url).netloc:
                return WebFetchResult(..., error="REDIRECT DETECTED")

        # 3. 转换为 Markdown
        html_content = response.text
        markdown_content = self._html_to_markdown(html_content)

        # 4. 截断
        if len(markdown_content) > self.MAX_MARKDOWN_LENGTH:
            markdown_content = markdown_content[:limit] + "\n\n[Content truncated...]"

        return WebFetchResult(...)
```

**关键特性**：
- HTML 自动转 Markdown（使用 markdownify）
- 重定向检测与处理
- 大小限制防止上下文爆炸

### 3. GrepTool（代码内容搜索）

```python
class GrepTool:
    """代码内容搜索工具（类似 grep/ripgrep）"""

    def call(
        self,
        pattern: str,
        output_mode: Literal['content', 'files_with_matches', 'count'] = 'files_with_matches',
        context: Optional[int] = None,
        glob: Optional[str] = None,
    ) -> GrepResult:
        # 编译正则
        regex = re.compile(pattern, re.IGNORECASE)

        # 收集所有匹配
        matches = self._grep_files(regex, context, glob)

        # 根据模式处理结果
        if output_mode == 'files_with_matches':
            return self._process_files_mode(...)
        elif output_mode == 'content':
            return self._process_content_mode(...)
        elif output_mode == 'count':
            return self._process_count_mode(...)
```

**三种输出模式**：
- `files_with_matches`：只返回匹配的文件路径
- `content`：显示匹配的行内容（支持上下文行）
- `count`：显示每个文件的匹配次数

**关键特性**：
- 自动排除 VCS 目录（.git, .svn 等）
- 结果截断防止上下文爆炸
- 支持上下文行（-A/-B/-C）

### 4. GlobTool（文件路径匹配）

```python
class GlobTool:
    """文件路径模式匹配工具（类似 glob）"""

    DEFAULT_MAX_RESULTS = 100

    def call(self, pattern: str, path: Optional[str] = None) -> GlobResult:
        search_path = Path(path).resolve() if path else self.root_dir

        # 手动遍历实现 glob 匹配
        files = self._glob_files(search_path, pattern)

        # 截断
        truncated = len(files) > self.max_results
        files = files[:self.max_results]

        # 转为相对路径
        relative_files = [str(f.relative_to(search_path)) for f in files]

        return GlobResult(filenames=relative_files, truncated=truncated, ...)
```

**关键特性**：
- 支持 glob 模式（*, **, ?）
- 结果截断（默认 100）
- 自动排除 VCS 目录

---

## 🧪 测试结果

### WebSearchTool

```
⚠️  搜索失败（可能需要网络）: https://www.bing.com/search?q=...
```

**说明**：由于网络原因，DuckDuckGo 搜索失败。但在网络正常环境下应该可以工作。

### WebFetchTool

```
✅ 抓取：https://httpbin.org/html
   状态码：200
   大小：3741 bytes
   内容预览：# Herman Melville - Moby-Dick ...
```

**说明**：✅ 成功抓取网页并转换为 Markdown

### GrepTool

```
✅ files_with_matches: 找到 3 个文件
   Found 3 files with matches:
     config.py
     utils.py
     app.py

✅ content 模式:
   config.py:1:import os
   utils.py:1:import os
   app.py:1:import os

✅ count 模式:
   Match counts per file:
     app.py: 1
     config.py: 1
     utils.py: 1
```

**说明**：✅ 三种输出模式全部工作正常

### GlobTool

```
✅ **/*.py: 找到 5 个文件
   Found 5 files:
     setup.py
     tests/test_main.py
     src/main.py
     src/core/__init__.py
     src/core/utils.py

✅ **/__init__.py: 找到 1 个文件
✅ *.md: 找到 1 个文件
```

**说明**：✅ glob 模式匹配工作正常

---

## ⚠️ 遇到的问题与解决

### 问题 1：DuckDuckGo 库改名

**警告**：
```
RuntimeWarning: This package (`duckduckgo_search`) has been renamed to `ddgs`!
```

**解决**：库仍然可用，但建议未来使用新名称 `ddgs`

### 问题 2：网络搜索失败

**错误**：
```
https://www.bing.com/search?q=... return None
```

**原因**：DuckDuckGo 使用 Bing 搜索结果，国内网络可能无法访问

**解决**：
1. 使用代理
2. 或替换为其他搜索 API（如 Google Custom Search、百度 API）

### 问题 3：HTML 转 Markdown 依赖

**依赖**：
- `markdownify`：HTML → Markdown 转换
- `beautifulsoup4`：HTML 解析

**解决**：已安装这些依赖，并有回退方案（简单文本提取）

---

## 📊 教程评价

| 维度 | 评分 | 说明 |
|------|------|------|
| 概念清晰度 | ⭐⭐⭐⭐⭐ | 搜索与网络分工讲解清晰 |
| 代码可读性 | ⭐⭐⭐⭐⭐ | 代码结构清晰，注释详细 |
| 实践指导性 | ⭐⭐⭐⭐☆ | 有完整实现和测试 |
| 网络适配 | ⭐⭐⭐☆☆ | 国内网络可能有问题 |
| 新手友好度 | ⭐⭐⭐⭐☆ | 循序渐进，容易跟上 |

**总体评分**：⭐⭐⭐⭐☆（4.5/5）

---

## 🔧 教程改进建议

### 1. 增加国内搜索 API 支持

```python
# 可选的国内搜索 API
SEARCH_PROVIDERS = {
    "baidu": "https://www.baidu.com/s?wd={query}",
    "sogou": "https://www.sogou.com/web?query={query}",
    "bing_cn": "https://cn.bing.com/search?q={query}",
}
```

### 2. 增加搜索结果缓存

```python
class SearchCache:
    def __init__(self, ttl: int = 3600):
        self.cache: dict[str, tuple[WebSearchResult, float]] = {}
        self.ttl = ttl  # 缓存有效期（秒）

    def get(self, query: str) -> Optional[WebSearchResult]:
        if query in self.cache:
            result, timestamp = self.cache[query]
            if time.time() - timestamp < self.ttl:
                return result
            del self.cache[query]
        return None

    def set(self, query: str, result: WebSearchResult):
        self.cache[query] = (result, time.time())
```

### 3. 增加 ripgrep 后端支持

```python
def _grep_with_ripgrep(self, pattern: str) -> list[dict]:
    """使用 ripgrep 进行搜索（性能更好）"""
    if not shutil.which('rg'):
        return self._grep_with_python(pattern)  # 回退

    result = subprocess.run(
        ['rg', '--json', pattern, self.root_dir],
        capture_output=True, text=True
    )
    # 解析 JSON 输出
    ...
```

### 4. 增加 .gitignore 支持

```python
import pathspec

def _load_gitignore(self) -> pathspec.PathSpec:
    """加载 .gitignore 文件"""
    gitignore_path = self.root_dir / '.gitignore'
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            return pathspec.PathSpec.from_lines('gitwildmatch', f)
    return None
```

---

## 💡 学习心得

### 核心收获

1. **搜索工具让 Agent 突破知识截止** — 获取实时信息
2. **WebSearch 和 WebFetch 分工明确** — 一个找 URL，一个读内容
3. **Grep 和 Glob 分工明确** — 一个搜内容，一个搜路径
4. **上下文预算至关重要** — 所有工具都有结果限制

### 设计启发

1. **优雅降级** — WebFetch 在无 markdownify 时回退到纯文本
2. **相对路径** — 输出使用相对路径，节省 token
3. **安全排除** — 自动排除 .git、node_modules 等噪音目录
4. **三种输出模式** — GrepTool 的 files/content/count 模式灵活实用

### 与 Claude Code 对比

| 特性 | Claude Code | 我们的实现 | 差距 |
|------|-------------|------------|------|
| WebSearch | ✅ Anthropic API | ✅ DuckDuckGo | 接近 |
| WebFetch | ✅ 预批准域名 | ✅ 基础 | 接近 |
| Grep | ✅ ripgrep | ✅ Python re | 有差距 |
| Glob | ✅ 支持 | ✅ 支持 | 接近 |
| 结果缓存 | ❌ 无 | ❌ 无 | 平手 |
| .gitignore | ❌ 无 | ❌ 无 | 平手 |

---

## 📁 项目文件

```
~/my-first-agent/
├── agent_v4.py                # 第四章：带搜索与网络工具的 Agent
├── tools/
│   ├── web_tools.py           # WebSearchTool, WebFetchTool
│   └── search_tools.py        # GrepTool, GlobTool
├── test_chapter4.py           # 第四章测试
├── CHAPTER4_SUMMARY.md        # 第四章总结（本文件）
└── ...
```

---

## 📚 下一章预习

**第五章：记忆系统（上）—— 短期记忆**

学习目标：
- 理解短期记忆的概念
- 实现会话记忆（Session Memory）
- 实现 Token 计数与管理
- 实现上下文压缩

预习问题：
1. 什么是短期记忆？为什么需要？
2. 如何管理 Token 预算？
3. 如何压缩对话历史？

---

## 🏋️ 课后练习完成

| 练习 | 完成情况 | 说明 |
|------|----------|------|
| ripgrep 后端 | ⏸️ 待完成 | 可以使用 subprocess 调用 |
| 搜索结果缓存 | ⏸️ 待完成 | 可以用字典或 SQLite |
| WebFetch prompt 提取 | ⏸️ 待完成 | 可以用 LLM 摘要 |
| .gitignore 支持 | ⏸️ 待完成 | 使用 pathspec 库 |

---

_总结完成时间：2026-04-14_  
_学习时长：约 2 小时_  
_状态：第四章完成 ✅_  
_下一步：继续学习第五章（记忆系统）_
