# Project Architecture

```
app.py                  CLI entry point (argparse subcommands)
├── scan                Full trending + search + score pipeline
├── web                 Gradio web UI
├── export              Export latest report
├── daily-scan          Watchlist-only scan
├── daily-report        Watchlist markdown report
├── validation-pack     7-file opportunity validation
├── mvp-brief           Generate MVP brief
├── experiment-*        Experiment tracker
├── smoke-test          Offline health check
├── llm-test            LLM connection test
└── Run.bat             Windows menu launcher

src/
├── scraper.py              HTTP + rate-limit + cache layer
├── trending_scraper.py     github.com/trending parser
├── github_search_scraper.py github.com/search parser
├── repo_page_scraper.py    Repo detail + README + issues
├── repo_search.py          Trending + search orchestration
├── readme_analyzer.py      Early/commercial signal detection
├── issue_classifier.py     8-category keyword classification
├── scorer.py               5-dimension + data_quality + verdict
├── ranking_diagnostics.py  7 flag types + action suggestions
├── mvp_recommender.py      Rule-based MVP type recommendation
├── database.py             SQLite (8 tables)
├── report.py               CSV/JSON/MD export + watchlist report
├── daily_watchlist.py      Watchlist delta tracking
├── daily_report.py         Daily markdown report
├── validation_pack.py      7-file validation pack generator
├── webui.py                Gradio interface (Chinese)
├── config.py               Settings + env loading
├── mvp_brief_generator.py  Full MVP brief generation
├── experiment_tracker.py   Experiment CRUD + reporting
└── llm/                    Optional LLM layer
    ├── base.py                 Abstract LLM client
    ├── provider_router.py      Client factory
    ├── ollama_client.py        Ollama support
    ├── openai_compatible_client.py  OpenAI / Groq / DeepSeek
    ├── litellm_proxy_client.py LiteLLM proxy
    ├── prompts.py              Prompt templates
    ├── schemas.py              Pydantic output models
    ├── json_repair.py          JSON extraction & repair
    └── analyzer.py             Orchestration + caching
```

## Data flow

```
Trending + Search → HTTP cache → SQLite → Scorer → Verdict → Export / WebUI
                                               ↕
                                          LLM (optional)
```
