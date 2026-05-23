# arxiv-daily-digest

面向物理系学生的本地 arXiv 物理文献日报工具。项目每天从 arXiv 官方 API 抓取物理方向新论文，默认排除以机器学习、人工智能、LLM、RAG、Agent 为中心的论文，根据物理主题分类，并生成中英文双语“物理文献速读”报告。

默认 profile 是 `physics_student`，重点方向 profile 是 `condensed_matter_topology_qah`。

## 功能

- 每天抓取 arXiv 物理方向论文。
- 默认不检索 AI/ML/LLM 论文。
- 通过 `excluded_categories` 和 `excluded_keywords` 排除机器学习中心论文。
- 按凝聚态、拓扑量子物态、量子霍尔、超导、强关联、冷原子、量子光学等主题分类。
- 生成 Markdown、HTML、JSON 三种报告。
- 提供 CLI 和本地 Web App 两种入口。
- 默认 `MockProvider` 可离线运行，不需要任何 LLM API key。
- 真实 LLM API 只在后端调用，API key 只从环境变量读取。

报告重点解释：

- 研究问题
- 物理体系 / 材料体系 / 模型
- 关键物理概念
- 理论模型或实验方法
- 主要结果
- 与物理专业方向的相关性
- 阅读优先级
- 适合物理系学生理解的中文解释

## 安装

建议使用 Anaconda Python 3.12 或 Python 3.11+ 虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml
```

当前本地环境如果暂时不安装 FastAPI / uvicorn，也可以运行 `python -m arxiv_digest web`。命令会自动 fallback 到标准库 `http.server` 实现的本地 Web App。

## 本地 Web App

Mock 模式，不消耗外部 API：

```bash
python -m arxiv_digest web --profile physics_student --provider mock
```

当前网络不能访问 arXiv 时，用内置 sample feed 跑通网页 demo：

```bash
python -m arxiv_digest web --profile physics_student --provider mock --sample
```

打开：

```text
http://127.0.0.1:8000
```

首页行为：

- 如果今天已有同 profile 报告，直接展示报告。
- 如果今天没有报告，自动创建后台任务。
- 页面每 3 秒轮询任务状态。
- 任务完成后自动跳转到今日报告。
- 刷新首页不会重复创建正在运行的任务。
- `force=true` 才会强制重新生成，且必须通过 `WEB_ADMIN_TOKEN` 保护。

如果已安装 FastAPI / uvicorn，也可以直接运行：

```bash
uvicorn arxiv_digest.web.app:app --host 127.0.0.1 --port 8000 --reload
```

## 分享给别人访问

如果你要把链接分享给别人，建议使用公开只读模式：访问者可以看报告，但不能匿名触发 arXiv 抓取或真实 LLM 总结，避免别人刷新页面就消耗你的 API 额度。

```bash
export WEB_ADMIN_TOKEN="your-random-local-admin-token"
python -m arxiv_digest web \
  --public \
  --profile physics_student \
  --provider deepseek
```

`--public` 会绑定 `0.0.0.0:8000`。局域网内可用你的机器 IP 访问，例如：

```text
http://你的局域网IP:8000
```

如果你用反向代理、内网穿透或云服务器，可以设置公开地址，页面会显示分享链接：

```bash
export ARXIV_DIGEST_WEB_PUBLIC_BASE_URL="https://your-domain.example"
python -m arxiv_digest web --public --profile physics_student --provider deepseek
```

公开模式的规则：

- 已生成报告对访问者可读。
- `/reports/today?profile=physics_student` 可直接分享。
- 首页发现今天没有报告时，不会让匿名访问者自动触发真实 API。
- “开始抓取”和“强制刷新”都需要输入 `WEB_ADMIN_TOKEN`。
- `POST /api/run` 需要 `Authorization: Bearer <WEB_ADMIN_TOKEN>`。
- 不要把 `WEB_ADMIN_TOKEN` 发给普通访问者。

只有在你明确愿意让任何访问者触发 API 消耗时，才使用：

```bash
python -m arxiv_digest web --public --allow-public-auto-run --provider mock
```

真实 provider 不建议开启 `--allow-public-auto-run`。

## 任何人可打开的公开网址

如果目标是“给别人一个网址，任何人点开都能查阅”，推荐使用 GitHub Pages 发布静态报告，而不是把带 API key 的 Web App 暴露给公众。

项目已提供静态站点构建命令：

```bash
python -m arxiv_digest build-site --site-dir site
```

它会把 `reports/` 中的报告发布为：

```text
site/index.html
site/latest/physics_student.html
site/latest/condensed_matter_topology_qah.html
site/reports/YYYY-MM-DD-physics_student.html
```

开启 GitHub Pages 后，最终可分享的网址通常是：

```text
https://<你的GitHub用户名>.github.io/arxiv-daily-digest/
```

最新物理通用日报：

```text
https://<你的GitHub用户名>.github.io/arxiv-daily-digest/latest/physics_student.html
```

最新凝聚态 / 拓扑 / 量子反常霍尔日报：

```text
https://<你的GitHub用户名>.github.io/arxiv-daily-digest/latest/condensed_matter_topology_qah.html
```

这个公开站点是静态 HTML：

- 任何人可读。
- 不包含 API key。
- 不会调用 DeepSeek、Qwen、Gemini、Claude 或 arXiv API。
- 不会让访问者触发重新生成。
- 每天由 GitHub Actions 生成并部署。

## 真实 API 网页

不要把 API key 写进代码、`config.yaml`、HTML、JS、测试文件或提交到 Git。只设置环境变量：

```bash
export DEEPSEEK_API_KEY="..."
export ARXIV_DIGEST_PROVIDER=deepseek
python -m arxiv_digest web --profile physics_student --provider deepseek
```

其他 provider 同理：

```bash
export DASHSCOPE_API_KEY="..."
python -m arxiv_digest web --profile physics_student --provider qwen

export CUSTOM_LLM_API_KEY="..."
python -m arxiv_digest web --profile physics_student --provider custom_http
```

公网或非 `127.0.0.1` 绑定时，请设置：

```bash
export WEB_ADMIN_TOKEN="your-random-local-admin-token"
```

`POST /api/run` 的强制刷新需要：

```text
Authorization: Bearer <WEB_ADMIN_TOKEN>
```

不要把 API key 发给 Codex，不要提交 `.env`。

## CLI 用法

物理通用方向：

```bash
python -m arxiv_digest run-daily --profile physics_student --provider mock
```

凝聚态 / 拓扑 / 量子反常霍尔方向：

```bash
python -m arxiv_digest run-daily --profile condensed_matter_topology_qah --provider mock
```

离线 demo：

```bash
python -m arxiv_digest run-daily --profile physics_student --provider mock --sample
```

常用命令：

```bash
python -m arxiv_digest doctor
python -m arxiv_digest init-db
python -m arxiv_digest fetch --profile physics_student
python -m arxiv_digest fetch --profile physics_student --sample
python -m arxiv_digest analyze --profile physics_student --provider mock --limit 10
python -m arxiv_digest report --profile physics_student --format all
```

报告文件名包含 profile：

```text
reports/YYYY-MM-DD-physics_student.md
reports/YYYY-MM-DD-physics_student.html
reports/YYYY-MM-DD-physics_student.json
reports/YYYY-MM-DD-condensed_matter_topology_qah.md
```

## Live Smoke Test

真实 arXiv API 和真实 LLM provider 的实战测试默认拒绝运行。必须显式开启：

```bash
ALLOW_LIVE_API_TEST=1 python -m arxiv_digest live-smoke \
  --profile physics_student \
  --provider deepseek \
  --limit 2
```

限制：

- `--limit` 最大 5。
- 不打印 API key。
- 不打印完整 raw response。
- API key 缺失时给出清晰错误。
- 当前环境无网络权限时会提示检查网络和 provider 设置。

## Profile 配置

`config.example.yaml` 使用多 profile 架构：

```yaml
default_profile: physics_student

profiles:
  physics_student:
    arxiv:
      categories:
        - cond-mat.mes-hall
        - cond-mat.mtrl-sci
        - cond-mat.str-el
        - quant-ph
      keywords:
        - condensed matter
        - quantum Hall
        - topological
      excluded_categories:
        - cs.AI
        - cs.LG
        - stat.ML
      excluded_keywords:
        - machine learning
        - deep learning
        - large language model
        - LLM
```

`categories` 和 `keywords` 是正向检索条件；`excluded_categories` 和 `excluded_keywords` 用于排除机器学习中心论文。代码会优先在 arXiv query 中使用 `ANDNOT`，如果复杂 query 失败，会回退到正向检索后本地 post-filter。

## 彻底排除机器学习论文

在目标 profile 中维护：

```yaml
excluded_categories:
  - cs.AI
  - cs.LG
  - cs.CL
  - cs.CV
  - stat.ML
excluded_keywords:
  - machine learning
  - deep learning
  - neural network
  - large language model
  - LLM
  - transformer
  - foundation model
  - RAG
  - AI agent
```

## 新增物理方向 profile

可以在 `profiles` 下新增，例如：

- `high_energy_theory`
- `quantum_optics`
- `cold_atoms`
- `superconductivity`
- `statistical_physics`
- `astrophysics`
- `nuclear_physics`

最小结构：

```yaml
profiles:
  quantum_optics:
    display_name: "Quantum Optics"
    display_name_zh: "量子光学"
    description: "Quantum optics and light-matter interaction."
    arxiv:
      categories:
        - quant-ph
        - physics.optics
      keywords:
        - quantum optics
        - photon
        - cavity
        - light-matter interaction
      excluded_categories:
        - cs.AI
        - cs.LG
        - stat.ML
      excluded_keywords:
        - machine learning
        - large language model
    topics:
      - topic: "Quantum Optics"
        topic_zh: "量子光学"
      - topic: "Other Physics"
        topic_zh: "其他物理方向"
```

## LLM Provider

默认：

```yaml
llm:
  provider: mock
  model: mock-v1
```

Custom HTTP OpenAI-compatible：

```yaml
llm:
  provider: custom_http
  model: your-model
providers:
  custom_http:
    endpoint: "https://your-endpoint/v1/chat/completions"
    api_key_env: CUSTOM_LLM_API_KEY
```

DeepSeek：

```yaml
llm:
  provider: deepseek
providers:
  deepseek:
    base_url: "https://api.deepseek.com"
    model: "deepseek-chat"
    api_key_env: DEEPSEEK_API_KEY
```

Qwen：

```yaml
llm:
  provider: qwen
providers:
  qwen:
    model: "qwen-plus"
    api_key_env: DASHSCOPE_API_KEY
```

Ollama：

```yaml
llm:
  provider: ollama
providers:
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen2.5:7b"
```

Gemini / Claude 入口保留，但当前核心包未内置 SDK 调用；建议通过 `custom_http` 接兼容网关，或在对应 provider 文件中补原生 SDK。

## `.env`

`.env` 和 `.env.*` 已被 `.gitignore` 忽略，`.env.example` 可提交。

```bash
CUSTOM_LLM_API_KEY=...
DEEPSEEK_API_KEY=...
DASHSCOPE_API_KEY=...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...
LITELLM_API_KEY=...
ARXIV_DIGEST_DEFAULT_PROFILE=physics_student
ARXIV_DIGEST_PROVIDER=mock
WEB_ADMIN_TOKEN=...
ALLOW_LIVE_API_TEST=1
ARXIV_DIGEST_WEB_PUBLIC_BASE_URL=https://your-domain.example
```

## GitHub Actions

工作流在 `.github/workflows/daily.yml`，每天日本时间 09:00 运行。未设置真实 LLM secrets 时，默认 `mock` provider 仍可跑通。

工作流会：

1. 运行每日抓取、分析和报告生成。
2. 提交 `reports/` 和 `data/`。
3. 构建 `site/` 静态站。
4. 部署到 GitHub Pages。

首次使用需要在 GitHub 仓库设置里启用 Pages：

1. 打开仓库 Settings。
2. 进入 Pages。
3. Source 选择 `GitHub Actions`。
4. 手动运行一次 `Daily arXiv Digest` workflow。
5. Actions 完成后，使用 Pages 显示的 URL 分享。

GitHub Secrets 可按需设置：

- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `CUSTOM_LLM_API_KEY`

## Codex App 本地 Actions

不要在 action 脚本里写真实 API key，只读取系统环境变量。

Install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run Web:

```bash
source .venv/bin/activate
python -m arxiv_digest web --profile physics_student --provider ${ARXIV_DIGEST_PROVIDER:-mock}
```

Test:

```bash
source .venv/bin/activate
pytest
ruff check .
```

Live Smoke Test:

```bash
source .venv/bin/activate
ALLOW_LIVE_API_TEST=1 python -m arxiv_digest live-smoke \
  --profile physics_student \
  --provider ${ARXIV_DIGEST_PROVIDER:-mock} \
  --limit 2
```

## arXiv API 合规

- 使用官方 API：`https://export.arxiv.org/api/query`。
- 不爬 arXiv HTML 页面。
- 不并发请求 arXiv API。
- 连续请求默认间隔 3 秒。
- 默认每天最多抓取 100 篇。
- 使用 SQLite 按 `arxiv_id` 去重。
- 默认不下载 PDF，只链接回 arXiv abs 和 PDF 页面。

## 开发命令

```bash
pytest
ruff check .
ruff format .
```
