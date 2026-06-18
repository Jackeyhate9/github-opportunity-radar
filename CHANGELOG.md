# Changelog

## v0.5 — Forecast Layer (current)
- New `src/forecast/` pluggable forecast package (9 files)
- `ForecastAdapter` abstract base class with `fit_or_prepare()` / `forecast()` / `detect_anomaly()` / `explain_forecast()`
- `BaselineForecastAdapter`: naive last-value / moving-average / exponential-smoothing (no deps, always works)
- `TimesFMAdapter`: lazy-load TimesFM, `ENABLE_TIMESFM=true` to activate, auto-fallback to baseline on failure
- `historical_metrics` + `metric_forecasts` SQLite tables (migration-safe)
- `ForecastService` orchestration: store metrics → run adapter → save forecasts
- `compute_forecast_features()` → `ForecastFeatures` (growth 7/14/30d, acceleration, volatility, trend_label, explanation)
- `compute_forecast_signal()` → `forecast_signal_score` (0-100, independent of existing scores)
- 4 demo fixtures: spike+growth / steady+closing / flash-in-pan / insufficient-data
- `python app.py forecast demo` — run demo with 4 scenarios
- `python app.py forecast run --entity-type repo --entity-id owner/name --metric stars_count --horizon 30`
- WebUI repo detail: Forecast panel with trend_label, confidence, signal score
- Smoke-test covers: BaselineAdapter forecast, TimesFMAdapter fallback, DB tables, demo fixture prediction
- WindowsPath crash fix: `str()` conversion for file output paths (v0.5.1)
- `view_repo_detail` signature fix: removed `df` parameter, uses `SelectData.index[0]` directly (v0.5.1)
- Auto-open browser on `python app.py web` (v0.5.1)

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
