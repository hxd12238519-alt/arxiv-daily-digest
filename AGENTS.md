# AGENTS.md

## 项目目标

`arxiv-daily-digest` 每天从 arXiv 官方 API 获取物理方向新论文，基于标题、摘要、作者和分类进行去重、物理主题分类、中文解释和双语速读报告生成。默认 profile 必须是 `physics_student`，它抓取 arXiv `cond-mat.str-el` 强关联电子分类下的新论文；重点 profile 是 `spt_anomaly_generalized_symmetry`。正常运行默认使用 `deepseek`，API key 只允许从环境变量读取；`mock` provider 仅用于测试和离线开发。

## 目录结构

```text
src/arxiv_digest/        应用源码
src/arxiv_digest/llm/    LLM schema、抽象类和 provider
src/arxiv_digest/web/    本地 Web App、后台任务和静态模板
src/arxiv_digest/site.py 静态站点构建，用于 GitHub Pages 公开查阅
tests/                   pytest 测试
reports/                 生成的日报
data/                    SQLite 数据库
.github/workflows/       GitHub Actions
```

## 开发命令

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m arxiv_digest doctor
```

## 测试命令

```bash
pytest
```

## Lint / Format 命令

```bash
ruff check .
ruff format .
```

## 代码风格

- 使用 Python 3.11+。
- 类型标注尽量完整。
- 函数保持短小，错误信息要清晰。
- SQLite 写入必须使用参数化 SQL。
- 外部 API 调用必须有 timeout、retry 和错误记录。
- 单篇论文处理失败不能中断整个批处理。

## 禁止事项

- 不要硬编码 API key。
- 不要在 Web 模板、前端 JS、测试文件或日志中输出 API key。
- 不要在测试中访问真实网络、arXiv 或任何 LLM API。
- 不要爬 arXiv HTML 页面，只能使用官方 API。
- 不要绕过 arXiv rate limit；不得并发请求 arXiv API，连续请求至少间隔 3 秒。
- 不要把默认 profile 改回 AI/ML/LLM 方向。
- 不要把默认 provider 改回 `mock`；测试需要离线确定性输出时才显式使用 `mock` provider。
- 不要默认下载 PDF；PDF 解析只能作为默认禁用的后续扩展。
- Web 公开分享模式下，生成任务和 `force=true` 重新生成必须经过 `WEB_ADMIN_TOKEN` 保护。
- GitHub Pages 静态站点只能发布报告，不允许包含 API key 或触发真实 API 的前端逻辑。

## 修改完成要求

- 修改后必须运行 `pytest`。
- 涉及格式或 lint 时运行 `ruff format .` 和 `ruff check .`。
- 完成任务时总结修改内容、运行方式和测试结果。
