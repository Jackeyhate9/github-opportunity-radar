# GitHub 创业机会雷达 — Live

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 实时抓取 GitHub Trending + Search，发现 AI / 开发者工具的早期创业机会。
> **纯网页抓取，无 API、无 Token、无 mock 数据。**

## 核心理念

- **Live public first**：所有数据来自 github.com/trending + github.com/search 的实时网页抓取
- **无 API**：不使用 GitHub REST API / GraphQL，不依赖任何 Token
- **无 Mock**：所有数据都是真实的，缓存只是加速，不替代

## 快速启动

```bash
git clone https://github.com/YOUR_USER/github-opportunity-radar
cd github-opportunity-radar
pip install -r requirements.txt
python app.py web
# 浏览器访问 http://127.0.0.1:7860
```

> 详细入门请见 [docs/quickstart.md](docs/quickstart.md)
> 示例命令请见 [docs/examples.md](docs/examples.md)

## 如何跑完整 Live Scan

```bash
# 最小扫描
python app.py scan

# 自定义关键词、范围
python app.py scan --keywords "ollama,mcp,comfyui,gradio" --target 15 --min-stars 300

# 详细扫描（推荐）
python app.py scan --keywords "ollama,mcp,comfyui,gradio,ai agent,local llm,ai video,workflow automation" --target 15 --min-stars 300
```

输出包含：
- Scanned repos / Scored repos / Issues fetched
- 数据质量分布 (high/medium/low)
- 决策分布 (strong_candidate / niche_candidate 等)
- LLM success/failed
- Top 5 排名表（分数、数据质量、决策、推荐、MVP）
- Ranking Diagnostics 标记（service_first / plugin_first 等）
- CSV/JSON/MD 三种报告

## 如何开启/关闭 LLM

LLM **默认不启用**，不会影响核心扫描和评分。

### Provider 对比

| Provider | 连接方式 | JSON Schema | 需要 Key | 典型场景 |
|----------|----------|-------------|----------|----------|
| `ollama` | `/api/chat` + `/v1/chat/completions` | ❌ | 否 | 本地方案 |
| `openai_compatible` | `/chat/completions` | ✅ (可选) | 是 | OpenAI / Groq / DeepSeek 等 |
| `litellm_proxy` | `/chat/completions` (lite mode) | ✅ (可选) | 是 | LiteLLM 代理服务器 |

### CLI 命令

```bash
# 启用 Ollama（本地）
python app.py scan --enable-llm --llm-provider ollama --llm-model llama3.2

# 启用 OpenAI 兼容（API Key 从参数传入）
python app.py scan --enable-llm --llm-provider openai_compatible \
  --llm-base-url https://api.openai.com/v1 --llm-model gpt-4o-mini \
  --llm-api-key sk-xxx

# 或从环境变量读取 API Key（安全，不泄露到终端历史）
# set LLM_API_KEY=sk-xxx   (PowerShell)
# export LLM_API_KEY=sk-xxx (bash)
python app.py scan --enable-llm --llm-provider openai_compatible \
  --llm-base-url https://api.openai.com/v1 --llm-model gpt-4o-mini

# 高级参数
python app.py scan --enable-llm --llm-provider ollama \
  --llm-timeout 300 --llm-max-repos 5 --llm-use-json-schema \
  --llm-force-json-mode --llm-no-cache

# 关闭 LLM（纯规则分析）
python app.py scan
```

### 测试 LLM 连接（无需扫描）

```bash
# 测试 Ollama
python app.py llm-test --llm-provider ollama

# 测试 OpenAI 兼容
python app.py llm-test --llm-provider openai_compatible \
  --llm-base-url https://api.openai.com/v1 --llm-model gpt-4o-mini \
  --llm-api-key sk-xxx

# 带 JSON Schema 测试
python app.py llm-test --llm-provider ollama --llm-use-json-schema
```

### 安全提醒

- **不要将 API Key 写入脚本或配置文件**。使用环境变量 `LLM_API_KEY` 或 CLI 参数传入。
- 系统**不会**打印、记录或导出 API Key。
- 环境变量优先级：CLI 参数 > 环境变量。

### 失败降级机制

LLM **不可用时自动降级**为 rule-based scan，不会中断主流程：
```
LLM status: unavailable / fallback to rule-based
```

扫描结果状态包括：
- `completed_with_llm_errors` — 扫描完成但部分 LLM 分析失败
- `completed` — 全部正常

新参数控制：
- `--llm-continue-on-error`（默认 true）：LLM 失败时继续扫描其余仓库
- `--llm-no-cache`：禁用 LLM 结果缓存（默认根据 `readme_hash + issue_titles_hash + model + prompt_version + schema_version` 缓存）

## 评分模型 (100分)

| 维度 | 满分 | 数据来源 | 说明 |
|------|------|----------|------|
| **Hot Score** | 25 | Trending ★/wk + stars | 真实周增长 + Stars 边际递减 |
| **Issue Score** | 25 | Issues 页面直接抓取 | Issue 数量 + 评论 + 标签 |
| **Early Score** | 20 | README 分析 | alpha/beta/experimental/roadmap/v0.x |
| **Commercial Gap** | 20 | README 分析 | 无 pricing/enterprise/sales 信号越多分越高 |
| **MVP Feasibility** | 10 | Issue 分类 | 安装/UI/文档类痛点易产品化 |

## 什么是 data_quality_score

数据质量评分（0-100）独立于机会评分，用于评估抓取数据的可靠性：

| 分数区间 | 标签 | 含义 |
|----------|------|------|
| 75-100 | high | 基础信息完整、README 可读、Issue 数据充足 |
| 45-74 | medium | 部分信息缺失或 Issue 数量不足 |
| 0-44 | low | 严重缺失，结果不可靠 |

5 个组成部分：
1. **基础信息** (20pt)：full_name、description、stars、language 是否齐全
2. **README** (20pt)：是否成功抓取完整 README
3. **Issue 数据** (30pt)：抓到的 Issue 数量和丰富度
4. **Issue 分类** (15pt)：Issue 是否覆盖多个痛点分类
5. **LLM 分析** (15pt)：LLM 是否成功分析（可选）

**重要**：不要只看 opportunity_score。如果 data_quality_score < 45，排名可能不可靠。

## 什么是 Verdict

决策（opportunity_verdict）是对机会的定性判断：

| 决策 | 含义 |
|------|------|
| strong_candidate | ⭐ 机会评分高且数据质量高，值得重点研究 |
| niche_candidate | 🔍 有机会但方向较窄，需要进一步验证 |
| service_opportunity | 🛠 安装/文档/新手痛点集中，适合做服务而非产品 |
| plugin_opportunity | 🔌 工作流/API 集成需求集中，适合做插件或 MCP |
| weak_candidate | ⚠ 暂不值得做，需求不够明确 |
| avoid | ❌ 已有成熟商业方案或数据质量过低 |

## 什么是 final_recommendation

最终建议（final_recommendation）是规则引擎独立生成的行动建议，**不需要 LLM**：

| 建议 | 触发条件 |
|------|----------|
| build_prototype_now | strong_candidate + DQ >= 75 + issue_score >= 15 |
| research_manually_first | niche_candidate 或 DQ < 60 |
| good_for_service_business | service_opportunity |
| good_for_plugin_business | plugin_opportunity |
| add_to_watchlist | weak_candidate 或高热度低需求 |
| skip | avoid 或 DQ < 40 + 弱候选 |

判定逻辑严格基于规则，LLM 不可用时 final_recommendation 仍然正常生成。

## 什么是 Ranking Diagnostics

排名诊断（ranking_flags）标记每个 repo 的潜在问题：

| 标记 | 含义 |
|------|------|
| score_may_be_unreliable | 高分低数据质量 |
| commercial_risk | 高分但商业化信号强 |
| weak_issue_evidence | Issue 少但分数高 |
| hype_without_pain | 热度高但 Issue 需求弱 |
| niche_but_painful | 痛点明确但热度低 |
| service_first | 安装/文档类痛点占比高 |
| plugin_first | 工作流/API 类痛点占比高 |

## 如何使用 Watchlist

Watchlist 支持 7 天连续观察：

1. **加入 Watchlist**：在 WebUI 中输入 "owner/repo" → 点击"加入 Watchlist"
2. **自动记录**：每次扫描自动更新 stars、issues、分数变化
3. **手动复盘**：填写 hypothesis、target_user_guess、monetization_guess
4. **Needs Review**：当 star 增长快 / 分数大幅变动时自动标记
5. **导出报告**：`python app.py scan` 后，WebUI 中点击"导出 Watchlist 报告"

### 手动复盘字段

| 字段 | 说明 |
|------|------|
| user_hypothesis | 我认为这个机会是什么 |
| target_user_guess | 目标用户是谁 |
| monetization_guess | 可能怎么收钱 |
| validation_next_step | 下一步验证动作 |
| validation_result | 验证结果记录 |

### Needs Review 触发条件

1. stars_delta_since_last_scan > 100
2. issues_delta_since_last_scan > 5
3. opportunity_score 比上次增加 >= 10
4. data_quality_score 从 low/medium 变成 high
5. final_recommendation 从 watchlist/research 变成 build_prototype_now

## 为什么不要只看 opportunity_score

opportunity_score 是综合热度、需求、早期度、商业空白和可行性的分数，但它有局限性：

1. **数据质量低时分数不可靠**：如果 data_quality_score < 50，分数不能反映真实情况
2. **高热度 ≠ 真实需求**：hot_score 高但 issue_score 低的项目可能只是围观
3. **商业化信号不一定是坏事**：commercial_gap 扣分但说明项目已经验证了商业模式
4. **痛点分布决定产品形态**：安装部署痛点适合做服务，工作流痛点适合做插件

**建议**：始终结合 verdict + final_recommendation + ranking_flags 综合判断。

## v0.3: 自动观察 + 机会验证

### Daily Watchlist Scan

```bash
python app.py daily-scan
```

作用：
- 只扫描 Watchlist 中的 repo
- 更新 stars / open issues / README / scores
- 自动计算 deltas 和 needs_review

触发 needs_review 条件：
- star 增长 >= 100
- issues 增长 >= 5
- opportunity_score 增长 >= 10
- recommendation 变化
- 新增 issue 中出现 pricing / enterprise / self-host / deploy / api / integration / windows / cuda / oom / plugin / mcp / workflow 关键词

### Daily Report

```bash
python app.py daily-report
```

生成 `outputs/daily_watchlist_report.md`，包含：
- Summary（repo 总数、更新数、需要 review 数、最大 star 增长、最大 issue 增长）
- Needs Review（每个需要 review 的 repo 的详细 delta）
- No Major Change（无明显变化的 repo）

### Validation Pack

```bash
# 基础版本
python app.py validation-pack --repo owner/name

# 带 LLM 增强
python app.py validation-pack --repo owner/name --enable-llm --llm-provider ollama
```

生成 `outputs/validation_packs/owner__name/`，包含 7 个文件：
1. **opportunity_brief.md** — 机会摘要、目标用户、痛点证据、最小验证方式
2. **landing_page_copy.md** — 标题、副标题、3 个痛点、3 个卖点、CTA、FAQ
3. **mvp_scope.md** — MVP 做什么/不做什么、7 天计划、技术栈建议
4. **issue_reply_drafts.md** — 针对代表性 issues 的回复草稿（不自动发送）
5. **user_interview_questions.md** — 10 个用户访谈问题
6. **7_day_validation_plan.md** — Day 1-7 验证计划 + 成功标准
7. **launch_post_drafts.md** — GitHub Discussion / Reddit / HN / X / 小红书发布草稿

### 安全限制

- 所有草稿都标记为 `DRAFT`
- 不自动评论 GitHub issue
- 不自动发 Reddit / HN / X
- 不泄露 API key 到任何报告

### 如何连续 7 天观察 Watchlist

```bash
# Day 1: 扫描并加入 Watchlist
python app.py scan --keywords "ollama,mcp,comfyui" --target 15
python app.py web  # 打开 WebUI，候选 repo 加入 Watchlist，填写复盘字段

# Day 2-7: 每日扫描和报告
python app.py daily-scan
python app.py daily-report

# 在 WebUI 中查看变化
python app.py web

# 为有潜力的 repo 生成验证包
python app.py validation-pack --repo owner/name
```

### 如何判断一个机会是否值得做

1. **有真实 issue**：至少 5+ 条相关 issue，不是自嗨
2. **有重复痛点**：多条 issue 提到同一个问题
3. **有增长**：star / issue 在增加（Watchlist 自动追踪）
4. **7 天可做 demo**：MVP 范围足够小（见 mvp_scope.md）
5. **能找到明确目标用户**：issue 作者就是潜在用户
6. **有可能收费**：痛点够痛，用户愿意付费解决

---

## 常见问题

### GitHub 页面抓不到怎么办

可能的原因和解决：
- **频率限制**：扫描频率控制在 2s/次，如果持续失败，增大 `--delay` 参数
- **页面结构变化**：GitHub 偶尔更新 HTML 结构，检查 `scraper.py` 的选择器是否需要更新
- **网络问题**：确保能访问 github.com，部分网络环境需要代理

### Ollama 没启动 / 模型未下载怎么办

LLM 默认不启用。如果 `--enable-llm` 但 Ollama 不可用：
1. 系统会自动降级为 rule-based 分析
2. 扫描结果不受影响，只是没有 LLM 增强内容
3. 输出明确显示 `LLM status: unavailable / fallback to rule-based`

使用 `llm-test` 诊断：
```bash
python app.py llm-test --llm-provider ollama
# Connection: ok → Ollama 正在运行
# Connection: error → 先运行 ollama serve
# Model 'qwen2.5:14b' not pulled yet → 先运行 ollama pull qwen2.5:14b
```

如果模型未下载，可以先手动拉取或使用 Preload 功能：
```bash
ollama pull qwen2.5:14b
# 或在 WebUI 中点击「预加载 Ollama 模型」
```

V0.2.2 新增预加载机制（`client.preload()`），可在扫描前预热模型减少冷启动延迟。
超时从 120s 提升到 300s，有足够时间等待模型首次加载。

### 为什么不是每次都能抓满 N 个

- **Trending 页面只显示 25 个项目**，过滤关键词后可能只剩几个
- **Search 也有频率限制**，快速多次搜索可能被拦截
- 系统会组合 trending (daily/weekly/monthly/language) + search fallback 尽量凑够数量

### 中文在 PowerShell 显示乱码怎么办

PowerShell 控制台对 UTF-8 中文的显示可能不正确，输出类似：

```
Rec: �ʺ�������/�̳�
```

但**文件内容是正确的 UTF-8**。请用以下方式确认：
- `cat outputs/latest_report.csv`（输出到文件显示正确）
- 在 VS Code 中打开 CSV/JSON/MD 文件
- 浏览器打开 WebUI 页面（中文正常）

建议将 PowerShell 编码设为 UTF-8：
```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
```

### stars_delta_7d 为什么是 approx

- Trending 页面显示的 "X stars this week" 是 GitHub 估算值
- 部分 repo 没有 delta 数据，显示为 N/A
- 跨语言、跨周期的 trending 来源使用对应字段 (1d/7d/30d)

## 数据流

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ github.com/  │    │ github.com/  │    │ raw          │
│   trending   │    │    search    │    │ content      │
│ (★/wk 增量)  │    │ (关键词搜索)  │    │ (README)     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       ▼                   ▼                   ▼
   ┌─────────────────────────────────────────────────┐
   │    HTTP 文件缓存 + SQLite 数据库 (8 表)           │
   │    scan_runs / repos / repo_snapshots           │
   │    star_history / issues / scores / llm_analyses │
   │    watchlist                                     │
   └─────────────────────┬───────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────────┐
   │         评分引擎 (5 维度, 满分 100)               │
   │ Hot(25) + Issue(25) + Early(20)                 │
   │ + CommercialGap(20) + MVPFeasibility(10)        │
   │ + data_quality_score(100) + ranking_flags       │
   └─────────────────────┬───────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────────┐
   │    决策引擎 (6 级 verdict + final_recommendation)│
   │    strong_candidate / niche_candidate /          │
   │    service_opportunity / plugin_opportunity /    │
   │    weak_candidate / avoid                        │
   └─────────────────────┬───────────────────────────┘
                         │
                         ▼
   ┌─────────────────────────────────────────────────┐
   │    MVP 推荐引擎 (规则驱动, 无 LLM)                │
   │    安装器 / 插件 / WebUI / SaaS                  │
   └─────────┬───────────────────────────┬───────────┘
             │                           │
             ▼                           ▼
   ┌──────────────────┐       ┌──────────────────┐
   │  LLM 增强分析     │       │  导出 CSV/JSON/MD│
   │  (可选, 不覆盖规则)│       │  + Watchlist 报告 │
   └────────┬─────────┘       └──────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────┐
   │  Gradio Web UI                               │
   │  扫描 + 排行榜 + 详情 + Watchlist + 复盘字段   │
   └──────────────────────────────────────────────┘
```

## 项目结构

```
github-opportunity-radar/
├── app.py                 # CLI 入口 (scan / export / web)
├── Run.bat                # Windows 启动器
├── requirements.txt       # 依赖
├── src/
│   ├── scraper.py          # HTTP 抓取 + 重试 + 缓存 + 限速
│   ├── trending_scraper.py # github.com/trending (daily/weekly/monthly/language)
│   ├── github_search_scraper.py # github.com/search
│   ├── repo_page_scraper.py # 仓库详情 + README + /issues 直接抓取
│   ├── repo_search.py       # 搜索编排 (trending + search fallback)
│   ├── readme_analyzer.py   # README 信号检测
│   ├── issue_classifier.py  # Issue 8 维度分类
│   ├── scorer.py            # 5 维度评分 + data_quality_score + verdict + final_recommendation
│   ├── ranking_diagnostics.py # 排名诊断 (7 种标记 + 行动建议)
│   ├── mvp_recommender.py   # 规则引擎 MVP 推荐
│   ├── database.py          # SQLite 8 表 (含 watchlist)
│   ├── report.py            # CSV/JSON/MD 导出 + Watchlist 报告
│   ├── daily_watchlist.py   # 每日 Watchlist 扫描 (v0.3)
│   ├── daily_report.py      # 每日 Watchlist 报告 (v0.3)
│   ├── validation_pack.py   # 创业验证包生成器 (v0.3)
│   ├── webui.py             # Gradio 中文界面
│   ├── config.py            # 配置项
│   └── forecast/            # 趋势预测层 (v0.5)
│       ├── __init__.py
│       ├── adapter.py           # ForecastAdapter 抽象基类
│       ├── baseline.py          # BaselineForecastAdapter (默认可用)
│       ├── timesfm_adapter.py   # TimesFMAdapter (可选)
│       ├── models.py            # 数据模型
│       ├── features.py          # 衍生特征 + Signal Score
│       ├── service.py           # 编排服务
│       ├── database.py          # historical_metrics + metric_forecasts 表
│       ├── demo_fixture.py      # 4 组演示数据
│       └── cli.py               # CLI 入口
│   └── llm/                 # LLM 增强分析层
│       ├── base.py          # LLMConfig + LLMClient 抽象 + chat_json()
│       ├── provider_router.py # 客户端工厂 (v0.2.2 新增)
│       ├── ollama_client.py # Ollama (预加载 + 3 层 fallback + 300s 超时)
│       ├── openai_compatible_client.py # JSON Schema → JSON Mode → Text fallback
│       ├── litellm_proxy_client.py     # LiteLLM 代理客户端
│       ├── prompts.py       # 中文/英文提示词模板 + 测试提示词
│       ├── schemas.py       # LLM 输出 pydantic 模型
│       ├── json_repair.py   # JSON 提取/修复/校验
│       └── analyzer.py      # LLM 分析编排器 (provider_router + 缓存 + status_detail)
├── data/
│   └── radar.sqlite         # SQLite 数据库
├── cache/                   # HTTP 响应缓存
└── outputs/                 # CSV/JSON/MD 导出
```

## 什么是 suggested_next_action

`suggested_next_action` 是 ranking_diagnostics 根据 ranking_flags 组合生成的具体行动建议：

| 触发条件 | 建议 |
|----------|------|
| 热度虚高 + 分数不可靠 | 先不要做产品，手动验证 Issue 是否真实代表付费需求 |
| 商业化风险 | 存在成熟竞品，建议做差异化定位 |
| 服务优先 + 插件优先 | 痛点混合，建议先发布服务/教程，再考虑产品化 |
| 服务优先 | 考虑做部署服务、教程模板、咨询，而非 SaaS 产品 |
| 插件优先 | 考虑做插件、MCP Server、Chrome 扩展、n8n 节点 |
| 小而痛 | 适合小团队深耕细分领域，不要急于扩展 |
| Issue 证据不足 | Issue 数据不足，建议手动调研 Reddit/Discord 确认需求 |

## 什么是 top_pain_cluster

`top_pain_cluster` 是 Issue 分类中数量最多的痛点类别。通过痛点聚类，可以快速知道用户最需要什么：

| 聚类 | 含义 | 变现路径 |
|------|------|----------|
| install_deploy | 安装部署痛点 | 适合做一键安装器、Docker 模板、Windows 启动器或付费部署服务 |
| performance_gpu | 显存/性能痛点 | 适合做显存配置推荐器、量化工具、云 GPU 启动器 |
| workflow_integration | 工作流断点 | 适合做 API 连接器、MCP Server、Chrome 扩展、n8n 节点 |
| newbie_docs | 新手不会用 | 适合做中文教程包、WebUI 封装、模板市场或付费部署文档 |
| feature_request | 功能请求 | 适合做功能投票平台、插件市场或定制开发服务 |
| enterprise_team | 企业/团队需求 | 适合做私有化部署脚手架、SSO 集成、权限管理 |
| compatibility_upgrade | 兼容性/迁移问题 | 适合做迁移工具、兼容层或升级辅助工具 |
| mobile_ui | 移动端/前端UI机会 | 适合做移动端 WebApp、PWA 封装或移动端监控面板 |

`top_pain_cluster_name` 是中文名称，`top_pain_cluster_count` 是对应的 Issue 数量。

## 什么是 needs_review 和 review_reason

`needs_review` 和 `review_reason` 是 Watchlist 的自动提醒机制。当以下情况发生时，Watchlist 项会被自动标记为需要人工复盘：

1. `stars_delta_since_last_scan > 100` — 快速增长，需要确认原因
2. `issues_delta_since_last_scan > 5` — 需求爆发，需要检查新 Issue 类型
3. `opportunity_score` 比上次增加 >= 10 — 评分大幅提升
4. `data_quality_score` 从 low/medium 变成 high — 数据质量改善
5. `final_recommendation` 从 watchlist/research 变成 build_prototype_now — 机会升级

在 WebUI Watchlist 表格中，"需Review"列会显示 ⚠ 标记。导出 Watchlist 报告时，标记项会额外显示提醒。

## 如何用 Watchlist 连续观察 7 天

Watchlist 的设计目标是 7 天连续观察同一批候选项目：

```bash
# Day 1：首次扫描
python app.py scan --keywords "ollama,mcp,comfyui,gradio" --target 15 --min-stars 300

# Day 1 后续：打开 WebUI，把候选 repo 加入 Watchlist
python app.py web
# 在 WebUI 中输入 "owner/repo" → 点击"加入 Watchlist"
# 手动填写复盘字段（user_hypothesis / target_user_guess / monetization_guess / validation_next_step）

# Day 2-7：每天重新扫描
python app.py scan --keywords "ollama,mcp,comfyui,gradio" --target 15 --min-stars 300

# 每次扫描后，打开 WebUI → 加载 Watchlist
# 查看：
#   - stars_delta_since_last_scan（本周新增 Stars）
#   - stars_delta_since_first_seen（累计增量）
#   - needs_review（是否需要手动复盘）
#   - 分数变化
#   - 决策/建议变化

# 填写验证结果
# 在 WebUI 中更新 validation_result 字段

# Day 7：导出 Watchlist 报告
# 在 WebUI 中点击"导出 Watchlist 报告"
# 输出文件：outputs/watchlist_YYYYMMDD_HHMMSS.md
```

报告包含：每个 repo 的机会评分、数据质量、决策、建议、累计增长、复盘字段内容、Needs Review 状态。

## 如何运行 smoke-test

```bash
python app.py smoke-test
```

`smoke-test` 执行代码健康检查：
1. 所有核心模块 import（含 forecast v0.5 模块）
2. 数据库初始化 + 所有表检查（含 historical_metrics / metric_forecasts）
3. 评分引擎对最小 repo dict 评分
4. ranking_diagnostics 返回 flags
5. 报告导出器生成临时 CSV/JSON/MD
6. Watchlist DB 函数（add/load/remove）
7. scores 表 watchlist 表新增列检查
8. BaselineForecastAdapter 预测 14 天并验证输出
9. TimesFMAdapter 未安装时自动 fallback
10. demo fixture 生成 4 组数据并预测

不需要网络，不修改扫描数据。输出 "Smoke test passed." 表示全部正常。

## v0.5: Forecast Layer — 趋势预测

> 新增可插拔趋势预测层，基于历史指标预测未来走势，不替代现有评分。

### 运行 Demo

```bash
python app.py forecast demo --horizon 30
```

内置 4 个 demo 场景：
- 快速爆红 + Issue 激增
- 稳定增长 + Issue 关闭良好
- 突然爆红后快速回落
- 数据不足

### CLI 命令

```bash
python app.py forecast demo                    # 运行演示数据
python app.py forecast run --entity-type repo \
  --entity-id owner/name --metric stars_count \
  --horizon 30                                 # 对已有数据预测
```

### 使用 TimesFM（可选）

```bash
# 1. 安装依赖
pip install timesfm torch

# 2. 设置环境变量启用
set ENABLE_TIMESFM=true

# 3. 运行 demo（自动使用 TimesFM）
python app.py forecast demo
```

如果 TimesFM 未安装、ENABLE_TIMESFM 未设置、或模型加载失败，系统自动降级到 BaselineForecastAdapter。smoke-test 不受影响。

### WebUI 面板

在 repo 详情页底部新增 **趋势预测** 面板，展示：
- 趋势标签：heating_up / cooling_down / stable / noisy
- 7/14/30 天预测增速
- 预测置信度
- Signal Score (0-100)
- 异常信号标记

### Forecast Signal Score

不修改原始 `opportunity_score`，新增独立 `forecast_signal_score` (0-100)：
- 未来增长为正 → 加分
- 增速加快 → 加分
- 波动过大 → 降置信度
- 数据不足 → 维持 50 分
- 异常尖峰 → 标记但不直接高分

## 配置项

编辑 `src/config.py` 可调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `request_delay_seconds` | 2.0 | 请求间隔，防止限流 |
| `cache_max_age_hours` | 6 | HTTP 缓存有效期 |
| `default_target_count` | 15 | 默认扫描仓库数 |
| `default_min_stars` | 100 | 最小 Stars |
| `enable_raw_readme_fetch` | True | 从 raw.githubusercontent 获取 README |
| `enable_github_search_fallback` | True | Trending 不足时用 search 补充 |
| `llm_provider` | "none" | LLM 提供商 |
| `llm_model` | "qwen2.5:14b" | LLM 模型 |
| `llm_timeout` | 300 | LLM 请求超时（秒） |
| `llm_cache_enabled` | True | 是否启用 LLM 结果缓存 |
| `llm_use_json_schema` | False | JSON Schema 严格模式 |
| `llm_force_json_mode` | False | 强制 json_object 模式 |
| `llm_preload_model` | False | 扫描前预加载 Ollama 模型 |

## 注意事项

1. **抓取延迟**：每次请求间隔 2s，完整扫描约 1-3 分钟
2. **Rate Limit**：GitHub 对无认证请求有限制（约 60 req/hr），缓存有效期内不会重复请求
3. **LLM 独立性**：LLM 失败不会影响核心评分和 recommendation；所有 final_recommendation 由规则独立生成
4. **分数 ≠ 决策**：不要只看 opportunity_score，结合 verdict + final_recommendation + ranking_flags 综合判断
5. **7 天观察**：用 Watchlist 持续扫描同一批 repo，观察 stars 和分数变化
6. **Watchlist 导出**：支持 `watchlist_report` 模式，包含用户复盘字段和系统建议
