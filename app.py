#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import settings
from src.database import init_db, save_scan_run, get_or_create_repo, save_snapshot
from src.database import save_issues, save_score, save_llm_analysis, finish_scan_run
from src.database import get_latest_scan_runs, get_repos_for_scan
from src.database import add_to_watchlist, get_watchlist, save_mvp_brief, get_mvp_briefs
from src.database import get_repo_id_by_name
from src.ranking_diagnostics import analyze_ranking_quality
from src.repo_search import search_repos, clear_cache
from src.repo_page_scraper import scrape_issues_direct
from src.readme_analyzer import analyze_readme
from src.issue_classifier import classify_issues, CATEGORY_NAMES
from src.scorer import calculate_opportunity_score
from src.mvp_recommender import recommend_mvp
from src.report import export_csv, export_json, export_markdown
from src.llm.base import LLMConfig
from src.llm.analyzer import LLMAnalyzer
from src.llm.provider_router import create_client, test_connection
from src.llm.prompts import LLM_TEST_PROMPT
from src.daily_watchlist import run_daily_scan
from src.daily_report import generate_daily_report
from src.validation_pack import generate_validation_pack
from src.mvp_brief_generator import generate_mvp_brief, select_mvp_type


def run_scan(keywords=None, target_count=15, min_stars=100, max_stars=50000,
             min_open_issues=5, max_issues=20, trending_period="weekly",
             request_delay=2.0, enable_raw_readme=True,
             enable_search_fallback=True, exclude_commercial=False,
             enable_llm=False, llm_provider="none", llm_base_url="http://localhost:11434",
             llm_model="qwen2.5:14b", llm_api_key="", llm_temperature=0.2,
             llm_max_tokens=1200, llm_language="zh", llm_max_repos=10,
             llm_timeout=300, llm_use_json_schema=False,
             llm_force_json_mode=False, llm_cache_enabled=True,
             llm_continue_on_error=True):
    keywords = keywords or settings.default_keywords

    settings.request_delay_seconds = request_delay
    settings.enable_raw_readme_fetch = enable_raw_readme
    settings.enable_github_search_fallback = enable_search_fallback
    settings.exclude_mature_commercial = exclude_commercial

    print("=" * 68)
    print("  GitHub Opportunity Radar - Live Public Scan")
    print("=" * 68)
    print(f"  Keywords: {', '.join(keywords)}")
    print(f"  Target: {target_count} repos | Stars: {min_stars}-{max_stars}")
    print(f"  Issues: {min_open_issues}+ | Trending: {trending_period}")
    if enable_llm:
        print(f"  LLM: {llm_provider} / {llm_model} (timeout: {llm_timeout}s)")
    print()

    init_db()

    scan_run_id = save_scan_run(
        keywords=keywords,
        target_repo_count=target_count,
        min_stars=min_stars,
        max_stars=max_stars,
        min_open_issues=min_open_issues,
        max_issues_per_repo=max_issues,
        trending_period=trending_period,
        total_repos=0,
        llm_enabled=enable_llm,
        llm_provider=llm_provider if enable_llm else None,
        llm_model=llm_model if enable_llm else None,
    )

    llm_analyzer = None
    if enable_llm and llm_provider != "none":
        llm_config = LLMConfig(
            provider=llm_provider,
            base_url=llm_base_url,
            model=llm_model,
            api_key=llm_api_key,
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
            timeout=llm_timeout,
            language=llm_language,
            max_repos=llm_max_repos,
            use_json_schema=llm_use_json_schema,
            force_json_mode=llm_force_json_mode,
            cache_enabled=llm_cache_enabled,
        )
        llm_analyzer = LLMAnalyzer(llm_config)
        if not llm_analyzer.enabled:
            print("  [LLM] Provider unavailable, fallback to rule-based analysis.\n")
        else:
            print(f"  [LLM] Using {llm_provider} / {llm_model}\n")

    repos = search_repos(
        keywords=keywords,
        target_count=target_count,
        min_stars=min_stars,
        max_stars=max_stars,
        min_open_issues=min_open_issues,
        trending_period=trending_period,
    )

    if not repos:
        print("\nNo repos found.")
        finish_scan_run(scan_run_id, "completed", "No repos found")
        return []

    print(f"Analyzing {len(repos)} repos...\n")

    total_issues_fetched = 0
    total_issues_classified = 0
    results = []
    for idx, repo in enumerate(repos):
        fn = repo["full_name"]
        print(f"  [{idx+1}/{len(repos)}] {fn} ({repo.get('stars', '?')} stars)")

        repo_id = get_or_create_repo(repo)
        snapshot_id, data_quality = save_snapshot(scan_run_id, repo_id, repo)

        readme_text = repo.get("readme_text", "")
        readme_analysis = analyze_readme(readme_text)
        repo["readme_early_signals"] = readme_analysis["early_signals"]
        repo["readme_commercial_signals"] = readme_analysis["commercial_signals"]
        repo["readme_major_version"] = readme_analysis["major_version"]

        issues = scrape_issues_direct(fn, max_count=max_issues)
        classification = classify_issues(issues)
        save_issues(snapshot_id, issues)
        total_issues_fetched += len(issues)
        total_issues_classified += sum(classification.get("category_counts", {}).values())

        scores = calculate_opportunity_score(repo, issues, classification, data_quality,
                                              llm_status="", llm_analysis=None)
        repo.update(scores)
        repo["data_quality"] = data_quality

        if exclude_commercial and repo["commercial_gap_score"] < 5:
            repo["opportunity_score"] *= 0.5

        mvp = recommend_mvp(repo, issues, classification)
        repo.update(mvp)
        repo["category_summary"] = {
            CATEGORY_NAMES.get(k, k): v
            for k, v in classification.get("category_counts", {}).items()
        }

        save_score(scan_run_id, snapshot_id, repo, mvp, classification)
        results.append(repo)

        delta = repo.get("stars_delta_7d")
        delta_str = f" +{delta}/wk" if delta else ""
        print(f"    Score: {repo['opportunity_score']}/100{delta_str}")
        print(f"    DQ: {repo.get('data_quality_label', '')} ({repo.get('data_quality_score', 0)}) | Verdict: {repo.get('opportunity_verdict', '')}")

    results.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

    llm_analyzed = 0
    llm_failed = 0
    if llm_analyzer and llm_analyzer.enabled:
        print(f"\n  [LLM] Analyzing top {min(len(results), llm_max_repos)} repos...")
        llm_analyzer.cache = {}
        for idx, repo in enumerate(results[:llm_max_repos]):
            fn = repo["full_name"]
            repo["repo_id"] = get_or_create_repo(repo)
            print(f"  [LLM] [{idx+1}/{min(len(results), llm_max_repos)}] {fn}")
            issues = scrape_issues_direct(fn, max_count=max_issues)

            import time as _time
            repo_start = _time.time()
            analysis = llm_analyzer.analyze_repo(
                repo, issues, scan_run_id,
                db_save_func=lambda sid, rid, a: save_llm_analysis(sid, rid, a)
            )
            repo_elapsed = _time.time() - repo_start
            status = analysis.get("llm_status", "failed")
            sd = analysis.get("status_detail", "")

            if not llm_continue_on_error and status != "success":
                print(f"    LLM error (continue_on_error=false), stopping LLM analysis")
                break

            if status == "success":
                llm_analyzed += 1
                repo["llm_status"] = "success"
                repo["llm_summary"] = analysis.get("one_sentence_summary", "")
                repo["llm_mvp_idea"] = analysis.get("best_mvp_idea", "")
                repo["llm_target_customer"] = analysis.get("target_customer", "")
                repo["llm_monetization_angle"] = analysis.get("monetization_angle", "")
                repo["llm_build_difficulty"] = analysis.get("build_difficulty", "")
                repo["llm_confidence"] = analysis.get("confidence", "")
                repo["llm_user_pain_summary"] = analysis.get("user_pain_summary", "")
                repo["llm_why_now"] = analysis.get("why_now", "")
                repo["llm_build_plan"] = analysis.get("first_7_day_build_plan", [])
                repo["llm_risks"] = analysis.get("risks", [])
                repo["llm_pain_clusters"] = analysis.get("pain_clusters", [])
                updated_scores = calculate_opportunity_score(
                    repo, issues, classification, data_quality,
                    llm_status="success", llm_analysis=analysis
                )
                repo.update(updated_scores)
                print(f"    LLM status: success | {sd} | {repo_elapsed:.1f}s")
            elif status == "unavailable":
                llm_failed += 1
                print(f"    LLM unavailable ({sd}), stopping LLM analysis")
                break
            else:
                llm_failed += 1
                repo["llm_status"] = "failed"
                updated_scores = calculate_opportunity_score(
                    repo, issues, classification, data_quality,
                    llm_status="failed", llm_analysis=None
                )
                repo.update(updated_scores)
                print(f"    LLM status: failed | {sd} | {repo_elapsed:.1f}s")

    finish_scan_run(scan_run_id, "completed")

    print(f"\n{'='*68}")
    print(f"  SCAN SUMMARY")
    print(f"{'='*68}")
    print(f"  Scanned repos:    {len(repos)}")
    print(f"  Scored repos:     {len(results)}")
    print(f"  Issues fetched:   {total_issues_fetched}")
    print(f"  Issues classified:{total_issues_classified}")
    print(f"  LLM analyzed:     {llm_analyzed}")
    print(f"  LLM failed:       {llm_failed}")
    print()
    print(f"  TOP 5 Opportunities")
    print(f"  {'='*50}")
    for i, r in enumerate(results[:5], 1):
        delta = f" (+{r.get('stars_delta_7d')}/wk)" if r.get("stars_delta_7d") else ""
        dq = r.get("data_quality_score", 0)
        verdict = r.get("opportunity_verdict", "")
        rec_key = r.get("final_recommendation", "")
        from src.scorer import RECOMMENDATION_MAP_CN
        rec_cn = RECOMMENDATION_MAP_CN.get(rec_key, rec_key)
        flags = r.get("ranking_flags", [])
        flag_str = f" | Flags: {', '.join(flags)}" if flags else ""
        print(f"  {i}. {r['full_name']} ({r.get('stars', 0)} stars){delta}")
        print(f"     Score: {r['opportunity_score']}/100 | DQ: {dq} | Verdict: {verdict} | Rec: {rec_cn}{flag_str}")
        print(f"     MVP: {r.get('recommended_mvp_idea', '')}")
        print()

    export_csv(results)
    export_json(results)
    export_markdown(results)
    print(f"  Scan run #{scan_run_id} complete.")
    return results


def cmd_scan(args):
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
    settings.llm_use_json_schema = getattr(args, "llm_use_json_schema", False)
    run_scan(
        keywords=keywords,
        target_count=args.target,
        min_stars=args.min_stars,
        max_stars=args.max_stars,
        min_open_issues=args.min_issues,
        max_issues=args.max_issues or 20,
        trending_period=args.trending or "weekly",
        request_delay=args.delay or 2.0,
        enable_raw_readme=not args.no_readme,
        enable_search_fallback=not args.no_search,
        exclude_commercial=args.exclude_commercial,
        enable_llm=args.enable_llm,
        llm_provider=args.llm_provider or "none",
        llm_base_url=args.llm_base_url or "http://localhost:11434",
        llm_model=args.llm_model or "qwen2.5:14b",
        llm_api_key=args.llm_api_key or "",
        llm_temperature=args.llm_temperature or 0.2,
        llm_max_tokens=args.llm_max_tokens or 1200,
        llm_language=args.llm_language or "zh",
        llm_max_repos=args.llm_max_repos or 10,
        llm_timeout=getattr(args, "llm_timeout", 300),
        llm_use_json_schema=getattr(args, "llm_use_json_schema", False),
        llm_force_json_mode=getattr(args, "llm_force_json_mode", False),
        llm_cache_enabled=not getattr(args, "llm_no_cache", False),
        llm_continue_on_error=getattr(args, "llm_continue_on_error", True),
    )


def cmd_smoke_test(args=None):
    errors = []

    modules = [
        "src.config", "src.database", "src.scorer",
        "src.ranking_diagnostics", "src.report", "src.mvp_recommender",
        "src.readme_analyzer", "src.issue_classifier",
        "src.repo_page_scraper", "src.repo_search",
        "src.llm.base", "src.llm.analyzer", "src.llm.prompts",
        "src.llm.schemas", "src.llm.json_repair",
        "src.llm.provider_router",
        "src.daily_watchlist", "src.daily_report", "src.validation_pack",
        "src.mvp_brief_generator",
        "src.experiment_tracker",
    ]
    for mod in modules:
        try:
            __import__(mod)
        except Exception as e:
            errors.append(f"Import {mod}: {e}")

    try:
        init_db()
        import sqlite3
        conn = sqlite3.connect(str(settings.db_path))
        conn.row_factory = sqlite3.Row
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        required_tables = {"scan_runs", "repos", "repo_snapshots", "star_history",
                           "issues", "scores", "watchlist", "llm_analyses"}
        missing = required_tables - set(tables)
        if missing:
            errors.append(f"DB missing tables: {missing}")
    except Exception as e:
        errors.append(f"DB init: {e}")

    try:
        min_repo = {
            "full_name": "test/foo", "stars": 500, "forks": 10,
            "open_issues_count": 8, "description": "test",
            "language": "Python", "created_at": "2025-01-01T00:00:00Z",
            "pushed_at": "2026-01-01T00:00:00Z",
            "readme_text": "# Foo\nEarly stage tool for developers.",
        }
        from src.readme_analyzer import analyze_readme
        ra = analyze_readme(min_repo["readme_text"])
        min_repo["readme_early_signals"] = ra["early_signals"]
        min_repo["readme_commercial_signals"] = ra["commercial_signals"]
        min_repo["readme_major_version"] = ra["major_version"]
        from src.issue_classifier import classify_issues
        dummy_issues = [{"title": "Cannot install", "body": "Help", "labels": []}]
        cls = classify_issues(dummy_issues)
        result = calculate_opportunity_score(min_repo, dummy_issues, cls, "medium")
        assert "opportunity_score" in result, "score missing"
        assert "opportunity_verdict" in result, "verdict missing"
        assert "final_recommendation" in result, "rec missing"
    except Exception as e:
        errors.append(f"Scorer test: {e}")

    try:
        dummy_score = {
            "opportunity_score": 80, "data_quality_score": 30,
            "hot_score": 22, "issue_score": 5, "early_score": 15,
            "commercial_gap_score": 3, "open_issues_count": 2,
            "readme_commercial_signals": ["pricing", "enterprise", "contact sales"],
        }
        dummy_cls = {"category_counts": {}}
        diag = analyze_ranking_quality(dummy_score, dummy_cls)
        assert "ranking_flags" in diag, "flags missing"
    except Exception as e:
        errors.append(f"Ranking diagnostics test: {e}")

    try:
        import tempfile, os
        dummy_results = [{
            "full_name": "test/bar", "url": "https://github.com/test/bar",
            "description": "test repo", "language": "Python",
            "stars": 100, "forks": 5, "open_issues_count": 3,
            "data_quality": "medium", "data_quality_score": 60,
            "data_quality_label": "medium",
            "opportunity_verdict": "weak_candidate",
            "final_recommendation": "add_to_watchlist",
            "hot_score": 10, "issue_score": 10, "early_score": 10,
            "commercial_gap_score": 15, "mvp_feasibility_score": 5,
            "opportunity_score": 50,
            "readme_early_signals": [], "readme_commercial_signals": [],
            "top_pain_categories": {}, "top_pain_cluster": "",
            "top_pain_cluster_name": "", "pain_cluster_evidence": [],
            "pain_cluster_monetization_hint": "",
            "top_pain_cluster_count": 0, "mvp_type": "",
            "recommended_mvp_idea": "", "best_for": "",
            "ranking_flags": [], "ranking_warning": "",
            "suggested_next_action": "",
            "why_opportunity": "", "why_not_worth": "",
            "seven_day_mvp_plan": [],
        }]
        import copy
        export_csv(copy.deepcopy(dummy_results))
        export_json(copy.deepcopy(dummy_results))
        export_markdown(copy.deepcopy(dummy_results))
    except Exception as e:
        errors.append(f"Report export test: {e}")

    try:
        import sqlite3
        conn2 = sqlite3.connect(str(settings.db_path))
        conn2.row_factory = sqlite3.Row
        cur = conn2.execute("SELECT id FROM repos LIMIT 1")
        existing_repo = cur.fetchone()
        conn2.close()
        if existing_repo:
            rid = existing_repo["id"]
            ok = add_to_watchlist(rid, "smoke test")
            assert ok, "add_to_watchlist failed"
            wl = get_watchlist()
            assert any(w.get("repo_id") == rid for w in wl), "watchlist item not found"
        cols = ["user_hypothesis", "target_user_guess", "monetization_guess",
                "validation_next_step", "validation_result", "needs_review", "review_reason"]
        conn3 = sqlite3.connect(str(settings.db_path))
        conn3.row_factory = sqlite3.Row
        existing = {r["name"] for r in conn3.execute(
            "SELECT name FROM pragma_table_info('watchlist')"
        ).fetchall()}
        conn3.close()
        missing_cols = [c for c in cols if c not in existing]
        if missing_cols:
            errors.append(f"Watchlist missing columns: {missing_cols}")
        conn4 = sqlite3.connect(str(settings.db_path))
        conn4.row_factory = sqlite3.Row
        score_cols = {r["name"] for r in conn4.execute(
            "SELECT name FROM pragma_table_info('scores')"
        ).fetchall()}
        conn4.close()
        for sc in ["ranking_flags_json", "ranking_warning", "suggested_next_action"]:
            if sc not in score_cols:
                errors.append(f"scores missing column: {sc}")

        conn5 = sqlite3.connect(str(settings.db_path))
        conn5.row_factory = sqlite3.Row
        llm_cols = {r["name"] for r in conn5.execute(
            "SELECT name FROM pragma_table_info('llm_analyses')"
        ).fetchall()}
        conn5.close()
        for lc in ["cache_key", "prompt_version", "schema_version", "latency_ms", "status_detail"]:
            if lc not in llm_cols:
                errors.append(f"llm_analyses missing column: {lc}")
    except Exception as e:
        errors.append(f"DB migration test: {e}")

    try:
        from src.config import OUTPUTS_DIR
        tmp_dir = OUTPUTS_DIR / "validation_packs"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        from src.validation_pack import generate_validation_pack
        out_dir, files = generate_validation_pack(
            "test/validation-pack-test",
            issues=[{"title": "Cannot install on Windows", "body": "Help needed", "labels": ["bug"]}],
        )
        expected = ["opportunity_brief.md", "landing_page_copy.md", "mvp_scope.md",
                     "issue_reply_drafts.md", "user_interview_questions.md",
                     "7_day_validation_plan.md", "launch_post_drafts.md"]
        created = [p.name for p in files]
        missing_pack = [e for e in expected if e not in created]
        if missing_pack:
            errors.append(f"Validation pack missing files: {missing_pack}")
        import shutil
        if out_dir and Path(out_dir).exists():
            shutil.rmtree(out_dir)
    except Exception as e:
        errors.append(f"Validation pack test: {e}")

    try:
        from src.daily_report import generate_daily_report
        report_path = generate_daily_report()
        assert report_path.exists(), "daily report not created"
    except Exception as e:
        errors.append(f"Daily report test: {e}")

    try:
        from src.daily_watchlist import run_daily_scan
        from src.daily_watchlist import compute_deltas, check_issue_keywords
        test_issues = [
            {"title": "Need API integration", "body": "", "labels": ["enhancement"]},
            {"title": "OOM on large model", "body": "", "labels": ["bug"]},
        ]
        kws = check_issue_keywords(test_issues, "")
        assert len(kws) > 0, "keyword check failed"
    except Exception as e:
        errors.append(f"Daily watchlist test: {e}")

    try:
        from src.mvp_brief_generator import generate_mvp_brief, select_mvp_type
        from src.config import OUTPUTS_DIR
        test_out, test_files = generate_mvp_brief(
            "test/mvp-brief-test",
            mvp_type="webui",
            issues=[{"title": "Cannot install on Windows", "body": "Help needed", "labels": ["bug"],
                      "url": "https://github.com/test/mvp-brief-test/issues/1"}],
        )
        expected_mvp = ["README.md", "product_brief.md", "user_pain_evidence.md",
                        "mvp_requirements.md", "technical_architecture.md",
                        "codex_prompt.md", "build_plan_7_days.md",
                        "landing_page.md", "pricing_experiment.md",
                        "validation_checklist.md"]
        created_mvp = [p.name for p in test_files]
        missing_mvp = [e for e in expected_mvp if e not in created_mvp]
        if missing_mvp:
            errors.append(f"MVP brief missing files: {missing_mvp}")
        codex_path = test_out / "codex_prompt.md"
        if not codex_path.exists() or codex_path.stat().st_size == 0:
            errors.append("codex_prompt.md is empty or missing")
        import sqlite3
        conn6 = sqlite3.connect(str(settings.db_path))
        conn6.row_factory = sqlite3.Row
        mvp_tables = {r["name"] for r in conn6.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn6.close()
        if "mvp_briefs" not in mvp_tables:
            errors.append("mvp_briefs table not created")
        import shutil
        if test_out and Path(test_out).exists():
            shutil.rmtree(test_out)
    except Exception as e:
        errors.append(f"MVP brief test: {e}")

    try:
        from src.database import create_experiment, get_experiments, get_experiment
        from src.database import update_experiment
        conn7 = sqlite3.connect(str(settings.db_path))
        conn7.row_factory = sqlite3.Row
        exp_tables = {r["name"] for r in conn7.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn7.close()
        if "experiments" not in exp_tables:
            errors.append("experiments table not created")
        else:
            exp_id = create_experiment(
                repo_id=1, repo_full_name="test/experiment-test",
                experiment_name="Smoke Test Experiment",
                mvp_type="webui", priority="medium",
            )
            assert exp_id > 0, "create_experiment failed"
            exps = get_experiments()
            assert any(e["id"] == exp_id for e in exps), "get_experiments missing new exp"
            update_experiment(exp_id, status="building", outreach_count=5)
            updated = get_experiment(exp_id)
            assert updated["status"] == "building", "update_experiment status failed"
            assert updated["outreach_count"] == 5, "update_experiment outreach failed"
            from src.experiment_tracker import generate_experiment_report
            from src.experiment_tracker import generate_experiment_dashboard
            from src.experiment_tracker import generate_codex_task
            from src.experiment_tracker import compute_system_suggestion
            report_path = generate_experiment_report(exp_id)
            assert report_path.exists(), "experiment report not created"
            dash_path = generate_experiment_dashboard()
            assert dash_path.exists(), "dashboard not created"
            codex_path = generate_codex_task(exp_id)
            assert codex_path.exists(), "codex task not created"
            sug, reason = compute_system_suggestion(updated)
            assert sug in ("continue", "pause", "kill", "ship"), f"unexpected suggestion: {sug}"
            import shutil
            for p in [report_path, dash_path, codex_path, report_path.parent]:
                if p.is_file():
                    p.unlink()
        conn8 = sqlite3.connect(str(settings.db_path))
        conn8.row_factory = sqlite3.Row
        conn8.execute("DELETE FROM experiments")
        conn8.commit()
        conn8.close()
    except Exception as e:
        import traceback
        errors.append(f"Experiment tracker test: {e}\n{traceback.format_exc()}")

    if errors:
        print("Smoke test FAILED:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("Smoke test passed.")
        return True


def cmd_llm_test(args):
    print("=" * 68)
    print("  LLM Connection Test")
    print("=" * 68)

    provider = args.llm_provider or "ollama"
    base_url = args.llm_base_url or "http://localhost:11434"
    model = args.llm_model or "qwen2.5:14b"
    api_key = args.llm_api_key or ""
    temperature = args.llm_temperature or 0.2
    max_tokens = args.llm_max_tokens or 1200
    timeout = args.llm_timeout or 120
    use_json_schema = args.llm_use_json_schema or False

    cfg = LLMConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        use_json_schema=use_json_schema,
    )
    print(f"  Provider: {provider}")
    print(f"  Base URL: {base_url}")
    print(f"  Model:    {model}")
    if api_key:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        print(f"  API Key:  {masked}")
    print()

    conn_result = test_connection(cfg)
    print(f"  Connection: {conn_result['status']}")
    print(f"  Detail:     {conn_result.get('detail', '')}")
    if conn_result.get("models_available"):
        models = conn_result.get("models_available", [])
        if models:
            print(f"  Models:     {len(models)} available")
            for m in models[:5]:
                print(f"    - {m}")

    if conn_result["status"] != "ok":
        print(f"\n  Test FAILED: Cannot connect to provider.")
        return False

    print(f"\n  Testing JSON schema support: {conn_result.get('supports_json_schema', False)}")
    print(f"  Testing JSON mode support:  {conn_result.get('supports_json_mode', False)}")

    print(f"\n  Sending test chat...")
    client = create_client(cfg)
    if client is None:
        print(f"  Test FAILED: Could not create client.")
        return False

    import time as _time
    test_start = _time.time()
    try:
        result = client.chat_json(LLM_TEST_PROMPT, "", None)
        elapsed = _time.time() - test_start
        print(f"  Response time: {elapsed:.1f}s")
        print(f"  JSON strategy: {result.json_mode_used}")
        print(f"  Status:        {result.status_detail}")

        if result.success and result.content:
            try:
                import json as _json
                parsed = _json.loads(result.content)
                if parsed.get("test") == "ok":
                    print(f"\n  Test PASSED: Provider is working correctly.")
                    return True
            except Exception:
                pass
            print(f"  Raw output (first 200 chars): {result.content[:200]}")
            print(f"\n  Test PARTIAL: Got response but unexpected format.")
            return True
        else:
            print(f"\n  Test FAILED: No response from provider.")
            return False
    except Exception as e:
        elapsed = _time.time() - test_start
        print(f"  Response time: {elapsed:.1f}s")
        print(f"  Error: {e}")
        print(f"\n  Test FAILED.")
        return False


def cmd_export(args):
    runs = get_latest_scan_runs(limit=1)
    if not runs:
        print("No scan data. Run a scan first.")
        return
    repos = get_repos_for_scan(runs[0]["id"])
    if not repos:
        print("No repos in latest scan.")
        return
    fmt = args.format or "csv"
    if fmt == "csv":
        export_csv(repos)
    elif fmt == "json":
        export_json(repos)
    elif fmt == "md":
        export_markdown(repos)


def cmd_web(args):
    import webbrowser
    port = args.port or 7860
    url = f"http://127.0.0.1:{port}"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    from src.webui import run_webui
    run_webui(debug=args.debug, port=port)


def cmd_daily_scan(args):
    updated, scan_run_id = run_daily_scan()
    if updated:
        generate_daily_report(updated_repos=updated)


def cmd_daily_report(args):
    generate_daily_report()


def cmd_validation_pack(args):
    repo = args.repo
    if not repo:
        print("Usage: python app.py validation-pack --repo owner/name")
        return

    llm_config = None
    if getattr(args, "enable_llm", False):
        llm_config = LLMConfig(
            provider=args.llm_provider or "none",
            base_url=args.llm_base_url or "http://localhost:11434",
            model=args.llm_model or "qwen2.5:14b",
            api_key=args.llm_api_key or "",
            temperature=args.llm_temperature or 0.2,
            max_tokens=args.llm_max_tokens or 1200,
            timeout=getattr(args, "llm_timeout", 300),
            use_json_schema=getattr(args, "llm_use_json_schema", False),
        )

    print("=" * 68)
    print(f"  Validation Pack: {repo}")
    print("=" * 68)
    print()

    from src.repo_page_scraper import scrape_repo_page
    repo_info = scrape_repo_page(repo)
    out_dir, files = generate_validation_pack(
        repo, issues=None,
        llm_config=llm_config,
        repo_info=repo_info,
    )
    print(f"\n  Validation pack generated at: {out_dir}")
    print(f"  Files created: {len(files)}")


def cmd_mvp_brief(args):
    repo = args.repo
    mvp_type = args.mvp_type or "auto"
    if not repo:
        print("Usage: python app.py mvp-brief --repo owner/name [--mvp-type TYPE]")
        return

    repo_id = get_repo_id_by_name(repo)
    if not repo_id:
        watchlist_repos = get_watchlist()
        in_wl = any(w.get("full_name", "").lower() == repo.lower() for w in watchlist_repos) if watchlist_repos else False
        if not in_wl:
            print(f"Repo not found in Watchlist. Add it first or run validation-pack first.")
            return

    from src.repo_page_scraper import scrape_repo_page
    repo_info = scrape_repo_page(repo)

    from src.repo_page_scraper import scrape_issues_direct
    issues = scrape_issues_direct(repo, max_count=20)
    for iss in (issues or []):
        iss.setdefault("body", "")

    llm_config = None
    if getattr(args, "enable_llm", False):
        llm_config = LLMConfig(
            provider=args.llm_provider or "none",
            base_url=args.llm_base_url or "http://localhost:11434",
            model=args.llm_model or "qwen2.5:14b",
            api_key=args.llm_api_key or "",
            temperature=args.llm_temperature or 0.2,
            max_tokens=args.llm_max_tokens or 1200,
            timeout=getattr(args, "llm_timeout", 300),
            use_json_schema=getattr(args, "llm_use_json_schema", False),
        )

    print("=" * 68)
    print(f"  MVP Brief: {repo}")
    print(f"  MVP Type: {mvp_type}")
    print("=" * 68)
    print()

    out_dir, files = generate_mvp_brief(
        repo, mvp_type=mvp_type,
        llm_config=llm_config,
        repo_info=repo_info,
        issues=issues,
    )

    print(f"  MVP brief generated:")
    print(f"  {out_dir}")
    print(f"  Files created ({len(files)}):")
    for f in files:
        print(f"    - {f.name}")

    repo_id = get_repo_id_by_name(repo)
    if repo_id and out_dir:
        save_mvp_brief(
            repo_id=repo_id,
            mvp_type=mvp_type,
            output_path=str(out_dir),
            used_llm=bool(llm_config and llm_config.provider != "none"),
            llm_provider=llm_config.provider if llm_config else None,
            llm_model=llm_config.model if llm_config else None,
            product_name=f"{repo.split('/')[-1]} MVP",
            target_user="",
        )


def cmd_experiment_create(args):
    repo = args.repo
    name = args.name or f"Experiment: {repo}"
    mvp_type = args.mvp_type or "auto"
    priority = args.priority or "medium"
    force = getattr(args, "force", False)

    from src.database import create_experiment, get_repo_id_by_name, get_watchlist
    from src.database import get_all_mvp_briefs
    from src.config import OUTPUTS_DIR

    repo_id = get_repo_id_by_name(repo)
    if not repo_id:
        print(f"Repo '{repo}' not found in database. Please run a scan first.")
        return

    wl = get_watchlist()
    in_wl = any(w.get("full_name", "").lower() == repo.lower() for w in (wl or []))
    if not in_wl and not force:
        print(f"Warning: '{repo}' is not in your Watchlist. Use --force to create anyway.")
        return

    val_pack_path = str(OUTPUTS_DIR / "validation_packs" / repo.replace("/", "__"))
    if not Path(val_pack_path).exists():
        val_pack_path = None
        print("  Note: No validation pack found. Run: python app.py validation-pack --repo owner/name")

    mvp_brief_path = None
    codex_path = None
    briefs = get_all_mvp_briefs()
    for b in briefs:
        if b.get("full_name", "").lower() == repo.lower():
            mvp_brief_path = b.get("output_path", "")
            if mvp_brief_path:
                codex_path = str(Path(mvp_brief_path) / "codex_prompt.md")
                if not Path(codex_path).exists():
                    codex_path = None
            break

    if not mvp_brief_path:
        print("  Note: No MVP brief found. Run: python app.py mvp-brief --repo owner/name --mvp-type auto")
    if not codex_path:
        print("  Note: No codex_prompt.md found. Generate MVP brief first.")

    exp_id = create_experiment(
        repo_id=repo_id, repo_full_name=repo,
        experiment_name=name, mvp_type=mvp_type,
        priority=priority,
        validation_pack_path=val_pack_path,
        mvp_brief_path=mvp_brief_path,
        codex_prompt_path=codex_path,
    )
    print(f"  Experiment #{exp_id} created: {name}")
    print(f"  Repo: {repo}")
    print(f"  Status: planned | Priority: {priority} | MVP Type: {mvp_type}")


def cmd_experiment_list(args):
    from src.database import get_experiments
    exps = get_experiments(limit=100)
    if not exps:
        print("No experiments found. Create one with: python app.py experiment-create --repo owner/name")
        return
    print(f"{'ID':<4} {'Repo':<28} {'Name':<30} {'Type':<20} {'Status':<14} {'Priority':<10} {'Decision':<10} {'Outreach':<10} {'Interested':<10} {'Paid':<6}")
    print("-" * 150)
    for e in exps:
        print(f"{e['id']:<4} {e.get('repo_full_name',''):<28} {str(e.get('experiment_name',''))[:28]:<30} "
              f"{e.get('mvp_type',''):<20} {e.get('status',''):<14} {e.get('priority',''):<10} "
              f"{e.get('decision',''):<10} {e.get('outreach_count',0):<10} {e.get('interested_count',0):<10} "
              f"{e.get('paid_count',0):<6}")


def cmd_experiment_update(args):
    from src.database import update_experiment, get_experiment
    exp_id = args.id
    exp = get_experiment(exp_id)
    if not exp:
        print(f"Experiment #{exp_id} not found.")
        return

    updates = {}
    for field in ["status", "priority", "external_project_path", "external_project_url",
                   "demo_url", "github_repo_url", "landing_page_url",
                   "target_user", "hypothesis", "monetization_hypothesis",
                   "success_criteria", "validation_channel", "notes",
                   "decision", "decision_reason"]:
        val = getattr(args, field.replace("-", "_"), None)
        if val is not None:
            updates[field] = val

    for field in ["outreach_count", "reply_count", "interested_count",
                   "waitlist_count", "paid_count"]:
        val = getattr(args, field.replace("-", "_"), None)
        if val is not None:
            updates[field] = int(val)

    if args.revenue_estimate is not None:
        updates["revenue_estimate"] = float(args.revenue_estimate)

    if not updates:
        print("No fields to update.")
        return

    update_experiment(exp_id, **updates)
    print(f"Experiment #{exp_id} updated.")
    for k, v in updates.items():
        print(f"  {k} = {v}")


def cmd_experiment_report(args):
    from src.experiment_tracker import generate_experiment_report
    exp_id = args.id
    path = generate_experiment_report(exp_id)
    print(f"Experiment report generated: {path}")


def cmd_experiment_dashboard(args):
    from src.experiment_tracker import generate_experiment_dashboard
    path = generate_experiment_dashboard()
    print(f"Experiment dashboard generated: {path}")


def cmd_experiment_codex_task(args):
    from src.experiment_tracker import generate_codex_task
    exp_id = args.id
    path = generate_codex_task(exp_id)
    print(f"Codex task generated: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Opportunity Radar - Live public data"
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_p = subparsers.add_parser("scan", help="Run live scan")
    scan_p.add_argument("--keywords", type=str, help="Comma-separated keywords")
    scan_p.add_argument("--target", type=int, default=15)
    scan_p.add_argument("--min-stars", type=int, default=100)
    scan_p.add_argument("--max-stars", type=int, default=50000)
    scan_p.add_argument("--min-issues", type=int, default=5)
    scan_p.add_argument("--max-issues", type=int, default=20)
    scan_p.add_argument("--trending", type=str, default="weekly",
                        choices=["daily", "weekly", "monthly", "all"])
    scan_p.add_argument("--delay", type=float, default=2.0)
    scan_p.add_argument("--no-readme", action="store_true")
    scan_p.add_argument("--no-search", action="store_true")
    scan_p.add_argument("--exclude-commercial", action="store_true")
    scan_p.add_argument("--enable-llm", action="store_true", help="Enable LLM analysis")
    scan_p.add_argument("--llm-provider", type=str, default="none",
                        choices=["none", "ollama", "openai_compatible", "litellm_proxy"])
    scan_p.add_argument("--llm-base-url", type=str, default="http://localhost:11434")
    scan_p.add_argument("--llm-model", type=str, default="qwen2.5:14b")
    scan_p.add_argument("--llm-api-key", type=str, default="")
    scan_p.add_argument("--llm-temperature", type=float, default=0.2)
    scan_p.add_argument("--llm-max-tokens", type=int, default=1200)
    scan_p.add_argument("--llm-timeout", type=int, default=300,
                        help="LLM request timeout in seconds")
    scan_p.add_argument("--llm-language", type=str, default="zh", choices=["zh", "en"])
    scan_p.add_argument("--llm-max-repos", type=int, default=10)
    scan_p.add_argument("--llm-use-json-schema", action="store_true",
                        help="Use JSON Schema structured output")
    scan_p.add_argument("--llm-force-json-mode", action="store_true",
                        help="Force json_object response_format")
    scan_p.add_argument("--llm-no-cache", action="store_true",
                        help="Disable LLM result caching")
    scan_p.add_argument("--llm-continue-on-error", action="store_true", default=True,
                        help="Continue scan on LLM error")
    scan_p.add_argument("--clear-cache", action="store_true")

    export_p = subparsers.add_parser("export", help="Export results")
    export_p.add_argument("--format", type=str, default="csv", choices=["csv", "json", "md"])

    smoke_p = subparsers.add_parser("smoke-test", help="Run smoke test (no network)")
    smoke_p.add_argument("--verbose", action="store_true", help="Show details")

    web_p = subparsers.add_parser("web", help="Start Web UI")
    web_p.add_argument("--debug", action="store_true")
    web_p.add_argument("--port", type=int, default=7860)

    llm_test_p = subparsers.add_parser("llm-test", help="Test LLM connection")
    llm_test_p.add_argument("--llm-provider", type=str, default="ollama",
                            choices=["ollama", "openai_compatible", "litellm_proxy"])
    llm_test_p.add_argument("--llm-base-url", type=str, default="http://localhost:11434")
    llm_test_p.add_argument("--llm-model", type=str, default="qwen2.5:14b")
    llm_test_p.add_argument("--llm-api-key", type=str, default="")
    llm_test_p.add_argument("--llm-temperature", type=float, default=0.2)
    llm_test_p.add_argument("--llm-max-tokens", type=int, default=1200)
    llm_test_p.add_argument("--llm-timeout", type=int, default=120)
    llm_test_p.add_argument("--llm-use-json-schema", action="store_true")

    daily_p = subparsers.add_parser("daily-scan", help="Scan watchlist repos for daily update")
    daily_p.add_argument("--delay", type=float, default=2.0)

    daily_report_p = subparsers.add_parser("daily-report", help="Generate daily watchlist report")

    val_p = subparsers.add_parser("validation-pack", help="Generate opportunity validation pack")
    val_p.add_argument("--repo", type=str, required=True,
                       help="Repo full name (owner/name)")
    val_p.add_argument("--enable-llm", action="store_true", help="Enable LLM enhancement")
    val_p.add_argument("--llm-provider", type=str, default="none",
                       choices=["none", "ollama", "openai_compatible", "litellm_proxy"])
    val_p.add_argument("--llm-base-url", type=str, default="http://localhost:11434")
    val_p.add_argument("--llm-model", type=str, default="qwen2.5:14b")
    val_p.add_argument("--llm-api-key", type=str, default="")
    val_p.add_argument("--llm-temperature", type=float, default=0.2)
    val_p.add_argument("--llm-max-tokens", type=int, default=1200)
    val_p.add_argument("--llm-timeout", type=int, default=300)
    val_p.add_argument("--llm-use-json-schema", action="store_true")

    mvp_p = subparsers.add_parser("mvp-brief", help="Generate MVP builder brief")
    mvp_p.add_argument("--repo", type=str, required=True,
                       help="Repo full name (owner/name)")
    mvp_p.add_argument("--mvp-type", type=str, default="auto",
                       choices=["auto", "one_click_installer", "webui", "plugin",
                                "mcp_server", "chrome_extension",
                                "deployment_template", "tutorial_pack"],
                       help="MVP type (default: auto-detect)")
    mvp_p.add_argument("--enable-llm", action="store_true", help="Enable LLM enhancement")
    mvp_p.add_argument("--llm-provider", type=str, default="none",
                       choices=["none", "ollama", "openai_compatible", "litellm_proxy"])
    mvp_p.add_argument("--llm-base-url", type=str, default="http://localhost:11434")
    mvp_p.add_argument("--llm-model", type=str, default="qwen2.5:14b")
    mvp_p.add_argument("--llm-api-key", type=str, default="")
    mvp_p.add_argument("--llm-temperature", type=float, default=0.2)
    mvp_p.add_argument("--llm-max-tokens", type=int, default=1200)
    mvp_p.add_argument("--llm-timeout", type=int, default=300)
    mvp_p.add_argument("--llm-use-json-schema", action="store_true")

    exp_create_p = subparsers.add_parser("experiment-create", help="Create experiment")
    exp_create_p.add_argument("--repo", type=str, required=True, help="Repo full name")
    exp_create_p.add_argument("--name", type=str, default=None, help="Experiment name")
    exp_create_p.add_argument("--mvp-type", type=str, default="auto",
                              choices=["auto", "one_click_installer", "webui", "plugin",
                                       "mcp_server", "chrome_extension",
                                       "deployment_template", "tutorial_pack"])
    exp_create_p.add_argument("--priority", type=str, default="medium",
                              choices=["high", "medium", "low"])
    exp_create_p.add_argument("--force", action="store_true", help="Create even if not in watchlist")

    exp_list_p = subparsers.add_parser("experiment-list", help="List experiments")

    exp_update_p = subparsers.add_parser("experiment-update", help="Update experiment")
    exp_update_p.add_argument("--id", type=int, required=True, help="Experiment ID")
    exp_update_p.add_argument("--status", type=str, choices=["planned", "brief_generated",
                              "building", "demo_ready", "validating", "paused", "killed", "shipped"])
    exp_update_p.add_argument("--priority", type=str, choices=["high", "medium", "low"])
    exp_update_p.add_argument("--demo-url", type=str)
    exp_update_p.add_argument("--github-repo-url", type=str)
    exp_update_p.add_argument("--landing-page-url", type=str)
    exp_update_p.add_argument("--external-project-path", type=str)
    exp_update_p.add_argument("--external-project-url", type=str)
    exp_update_p.add_argument("--target-user", type=str)
    exp_update_p.add_argument("--hypothesis", type=str)
    exp_update_p.add_argument("--monetization-hypothesis", type=str)
    exp_update_p.add_argument("--success-criteria", type=str)
    exp_update_p.add_argument("--validation-channel", type=str)
    exp_update_p.add_argument("--outreach-count", type=int)
    exp_update_p.add_argument("--reply-count", type=int)
    exp_update_p.add_argument("--interested-count", type=int)
    exp_update_p.add_argument("--waitlist-count", type=int)
    exp_update_p.add_argument("--paid-count", type=int)
    exp_update_p.add_argument("--revenue-estimate", type=float)
    exp_update_p.add_argument("--notes", type=str)
    exp_update_p.add_argument("--decision", type=str,
                              choices=["continue", "pivot", "pause", "kill", "ship", "unknown"])
    exp_update_p.add_argument("--decision-reason", type=str)

    exp_report_p = subparsers.add_parser("experiment-report", help="Generate experiment report")
    exp_report_p.add_argument("--id", type=int, required=True, help="Experiment ID")

    exp_dash_p = subparsers.add_parser("experiment-dashboard", help="Generate experiment dashboard")

    exp_codex_p = subparsers.add_parser("experiment-codex-task", help="Generate Codex task for experiment")
    exp_codex_p.add_argument("--id", type=int, required=True, help="Experiment ID")

    args = parser.parse_args()

    init_db()

    if args.command == "scan":
        if getattr(args, "clear_cache", False):
            clear_cache()
        cmd_scan(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "smoke-test":
        cmd_smoke_test(args)
    elif args.command == "web":
        cmd_web(args)
    elif args.command == "llm-test":
        cmd_llm_test(args)
    elif args.command == "daily-scan":
        cmd_daily_scan(args)
    elif args.command == "daily-report":
        cmd_daily_report(args)
    elif args.command == "validation-pack":
        cmd_validation_pack(args)
    elif args.command == "mvp-brief":
        cmd_mvp_brief(args)
    elif args.command == "experiment-create":
        cmd_experiment_create(args)
    elif args.command == "experiment-list":
        cmd_experiment_list(args)
    elif args.command == "experiment-update":
        cmd_experiment_update(args)
    elif args.command == "experiment-report":
        cmd_experiment_report(args)
    elif args.command == "experiment-dashboard":
        cmd_experiment_dashboard(args)
    elif args.command == "experiment-codex-task":
        cmd_experiment_codex_task(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
