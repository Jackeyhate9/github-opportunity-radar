# Changelog

## v0.5 (current)
- WindowsPath crash fix: `str()` conversion for file output paths
- `view_repo_detail` signature fix: removed `df` parameter, uses `SelectData.index[0]` directly
- Auto-open browser on `python app.py web`
- All Gradio startup warnings eliminated

## v0.4 — Experiment Tracker
- `experiment-create` / `experiment-list` / `experiment-update` / `experiment-report` / `experiment-dashboard`
- `experiment-codex-task`: auto-generate Codex-style coding task from MVP brief
- Support `--mvp-type` and `--external-project-path`
- Gradio WebUI: experiment management tab with create / list / update / report / codex task

## v0.3 — Validation Pack + Daily Watchlist
- `validation-pack`: 7-file opportunity validation pack (brief / landing / MVP / replies / interviews / plan / launch)
- `daily-scan`: lightweight watchlist-only scan (stars + issues + scores deltas)
- `daily-report`: markdown daily watchlist report
- Watchlist: `needs_review` / `review_reason` auto-flagging
- Watchlist review fields: hypothesis / target user / monetization / validation

## v0.2 — LLM Enhancement Layer
- Multi-provider support: Ollama / OpenAI-compatible / LiteLLM Proxy
- JSON Schema + JSON Mode + Text fallback chain
- Provider router with auto-fallback
- LLM result caching (by readme_hash + issue_hash + model)
- `llm-test` CLI command
- Preload mechanism for cold-start reduction
- 300s timeout for large model first load

## v0.1 — Core Scan Engine
- Live GitHub Trending + Search scraping (no API, no token)
- 5-dimension scoring: Hot(25) + Issue(25) + Early(20) + CommercialGap(20) + MVPFeasibility(10)
- README signal analysis (early + commercial signals)
- Issue 8-dimension keyword classification
- 6-level verdict engine + final_recommendation
- MVP recommendation engine (rule-based)
- Ranking diagnostics (7 flag types)
- Gradio WebUI with Chinese interface
- CSV / JSON / Markdown export
- `smoke-test` command
- Run.bat Windows launcher
