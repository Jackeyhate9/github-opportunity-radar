import sqlite3
import json
from datetime import datetime, timezone
from src.config import settings


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS scan_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            mode TEXT DEFAULT 'live_public',
            keywords TEXT,
            target_repo_count INTEGER DEFAULT 15,
            min_stars INTEGER DEFAULT 100,
            max_stars INTEGER DEFAULT 50000,
            min_open_issues INTEGER DEFAULT 5,
            max_issues_per_repo INTEGER DEFAULT 20,
            trending_period TEXT DEFAULT 'weekly',
            time_range_days INTEGER DEFAULT 30,
            total_repos INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',
            error_message TEXT,
            llm_enabled INTEGER DEFAULT 0,
            llm_provider TEXT,
            llm_model TEXT
        );

        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT UNIQUE NOT NULL,
            owner TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT,
            language TEXT,
            stars INTEGER DEFAULT 0,
            forks INTEGER DEFAULT 0,
            open_issues INTEGER DEFAULT 0,
            homepage TEXT,
            topics_json TEXT,
            license_name TEXT,
            created_at TEXT,
            updated_at TEXT,
            pushed_at TEXT,
            has_discussions INTEGER DEFAULT 0,
            has_releases INTEGER DEFAULT 0,
            readme_text TEXT,
            readme_fetch_status TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT
        );

        CREATE TABLE IF NOT EXISTS repo_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_run_id INTEGER NOT NULL,
            repo_id INTEGER NOT NULL,
            captured_at TEXT NOT NULL,
            stars INTEGER DEFAULT 0,
            forks INTEGER DEFAULT 0,
            open_issues INTEGER DEFAULT 0,
            stars_delta_1d INTEGER DEFAULT NULL,
            stars_delta_7d INTEGER DEFAULT NULL,
            stars_delta_30d INTEGER DEFAULT NULL,
            stars_delta_source TEXT,
            data_quality TEXT DEFAULT 'medium',
            FOREIGN KEY (scan_run_id) REFERENCES scan_runs(id),
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE IF NOT EXISTS star_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            captured_at TEXT NOT NULL,
            stars INTEGER NOT NULL,
            source TEXT DEFAULT 'snapshot',
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_snapshot_id INTEGER NOT NULL,
            title TEXT,
            url TEXT,
            labels_json TEXT,
            comments_count INTEGER DEFAULT 0,
            updated_at TEXT,
            snippet TEXT,
            category TEXT,
            captured_at TEXT,
            FOREIGN KEY (repo_snapshot_id) REFERENCES repo_snapshots(id)
        );

        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_run_id INTEGER NOT NULL,
            repo_snapshot_id INTEGER NOT NULL,
            hot_score REAL DEFAULT 0,
            issue_score REAL DEFAULT 0,
            early_score REAL DEFAULT 0,
            commercial_gap_score REAL DEFAULT 0,
            mvp_feasibility_score REAL DEFAULT 0,
            opportunity_score REAL DEFAULT 0,
            early_signals_json TEXT,
            commercial_signals_json TEXT,
            pain_categories_json TEXT,
            top_pain_categories_json TEXT,
            recommended_mvp_idea TEXT,
            mvp_type TEXT,
            best_for TEXT,
            all_ideas_json TEXT,
            alternative_ideas_json TEXT,
            reasoning_text TEXT,
            FOREIGN KEY (scan_run_id) REFERENCES scan_runs(id),
            FOREIGN KEY (repo_snapshot_id) REFERENCES repo_snapshots(id)
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            added_at TEXT NOT NULL,
            note TEXT,
            status TEXT DEFAULT 'watching',
            user_rating INTEGER DEFAULT 0,
            user_hypothesis TEXT,
            target_user_guess TEXT,
            monetization_guess TEXT,
            validation_next_step TEXT,
            validation_result TEXT,
            needs_review INTEGER DEFAULT 0,
            review_reason TEXT,
            FOREIGN KEY (repo_id) REFERENCES repos(id),
            UNIQUE(repo_id)
        );

        CREATE TABLE IF NOT EXISTS llm_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_run_id INTEGER NOT NULL,
            repo_id INTEGER NOT NULL,
            provider TEXT,
            model TEXT,
            prompt_tokens_estimate INTEGER DEFAULT 0,
            completion_tokens_estimate INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            analysis_json TEXT,
            one_sentence_summary TEXT,
            user_pain_summary TEXT,
            best_mvp_idea TEXT,
            mvp_type TEXT,
            target_customer TEXT,
            why_now TEXT,
            monetization_angle TEXT,
            build_difficulty TEXT,
            confidence TEXT,
            first_7_day_build_plan TEXT,
            risks TEXT,
            pain_clusters TEXT,
            llm_notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (scan_run_id) REFERENCES scan_runs(id),
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE INDEX IF NOT EXISTS idx_repo_full_name ON repos(full_name);
        CREATE INDEX IF NOT EXISTS idx_snapshot_run ON repo_snapshots(scan_run_id);
        CREATE INDEX IF NOT EXISTS idx_snapshot_repo ON repo_snapshots(repo_id);
        CREATE INDEX IF NOT EXISTS idx_issue_snapshot ON issues(repo_snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_score_run ON scores(scan_run_id);
        CREATE INDEX IF NOT EXISTS idx_score_snapshot ON scores(repo_snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_star_history_repo ON star_history(repo_id);
        CREATE INDEX IF NOT EXISTS idx_llm_scan_run ON llm_analyses(scan_run_id);
        CREATE INDEX IF NOT EXISTS idx_llm_repo ON llm_analyses(repo_id);

        CREATE TABLE IF NOT EXISTS mvp_briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            mvp_type TEXT NOT NULL,
            output_path TEXT,
            generated_at TEXT NOT NULL,
            used_llm INTEGER DEFAULT 0,
            llm_provider TEXT,
            llm_model TEXT,
            product_name TEXT,
            one_sentence_positioning TEXT,
            target_user TEXT,
            status TEXT DEFAULT 'generated',
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            repo_full_name TEXT NOT NULL,
            experiment_name TEXT NOT NULL,
            mvp_type TEXT DEFAULT 'auto',
            status TEXT DEFAULT 'planned',
            priority TEXT DEFAULT 'medium',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            validation_pack_path TEXT,
            mvp_brief_path TEXT,
            external_project_path TEXT,
            external_project_url TEXT,
            codex_prompt_path TEXT,
            landing_page_url TEXT,
            demo_url TEXT,
            github_repo_url TEXT,
            target_user TEXT,
            hypothesis TEXT,
            monetization_hypothesis TEXT,
            success_criteria TEXT,
            validation_channel TEXT,
            outreach_count INTEGER DEFAULT 0,
            reply_count INTEGER DEFAULT 0,
            interested_count INTEGER DEFAULT 0,
            waitlist_count INTEGER DEFAULT 0,
            paid_count INTEGER DEFAULT 0,
            revenue_estimate REAL DEFAULT 0,
            notes TEXT,
            decision TEXT DEFAULT 'unknown',
            decision_reason TEXT,
            system_suggestion TEXT,
            system_suggestion_reason TEXT,
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );
    """)
    _add_score_columns(conn)
    _add_watchlist_columns(conn)
    _add_llm_columns(conn)
    conn.commit()
    conn.close()
    from src.forecast.database import init_forecast_tables
    init_forecast_tables()


def _add_score_columns(conn):
    cur = conn.cursor()
    new_cols = [
        "data_quality_score INTEGER DEFAULT 0",
        "data_quality_label TEXT DEFAULT 'medium'",
        "data_quality_reasons_json TEXT",
        "opportunity_verdict TEXT",
        "verdict_reason TEXT",
        "top_pain_cluster TEXT DEFAULT ''",
        "top_pain_cluster_name TEXT DEFAULT ''",
        "top_pain_cluster_count INTEGER DEFAULT 0",
        "pain_cluster_evidence_json TEXT",
        "pain_cluster_monetization_hint TEXT",
        "why_opportunity TEXT",
        "why_not_worth TEXT",
        "seven_day_mvp_plan_json TEXT",
        "final_recommendation TEXT",
        "ranking_flags_json TEXT",
        "ranking_warning TEXT",
        "suggested_next_action TEXT",
        "forecast_signal_score REAL DEFAULT 50.0",
    ]
    for col_def in new_cols:
        col_name = col_def.split()[0]
        cur.execute(
            "SELECT COUNT(*) FROM pragma_table_info('scores') WHERE name=?",
            (col_name,)
        )
        if cur.fetchone()[0] == 0:
            cur.execute(f"ALTER TABLE scores ADD COLUMN {col_def}")


def get_all_mvp_briefs(limit=20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT mb.*, r.full_name
           FROM mvp_briefs mb
           JOIN repos r ON r.id = mb.repo_id
           ORDER BY mb.generated_at DESC
           LIMIT ?""",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_mvp_brief_for_repo(repo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM mvp_briefs
           WHERE repo_id = ?
           ORDER BY generated_at DESC
           LIMIT 1""",
        (repo_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_validation_pack_for_repo(repo_full_name):
    from src.config import OUTPUTS_DIR
    sanitized = repo_full_name.replace("/", "__").replace("\\", "__")
    path = OUTPUTS_DIR / "validation_packs" / sanitized
    if path.exists():
        return str(path)
    return None


def get_latest_mvp_brief_for_repo_name(repo_full_name):
    rid = get_repo_id_by_name(repo_full_name)
    if rid:
        return get_latest_mvp_brief_for_repo(rid)
    return None


def create_experiment(repo_id, repo_full_name, experiment_name, mvp_type="auto",
                      priority="medium", validation_pack_path=None,
                      mvp_brief_path=None, codex_prompt_path=None):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """INSERT INTO experiments
           (repo_id, repo_full_name, experiment_name, mvp_type, status, priority,
            created_at, updated_at, validation_pack_path, mvp_brief_path,
            codex_prompt_path, decision)
           VALUES (?, ?, ?, ?, 'planned', ?, ?, ?, ?, ?, ?, 'unknown')""",
        (repo_id, repo_full_name, experiment_name, mvp_type,
         priority, now, now, validation_pack_path, mvp_brief_path,
         codex_prompt_path)
    )
    exp_id = cur.lastrowid
    conn.commit()
    conn.close()
    return exp_id


def update_experiment(experiment_id, **kwargs):
    valid_fields = {
        "status", "priority", "validation_pack_path", "mvp_brief_path",
        "external_project_path", "external_project_url", "codex_prompt_path",
        "landing_page_url", "demo_url", "github_repo_url", "target_user",
        "hypothesis", "monetization_hypothesis", "success_criteria",
        "validation_channel", "outreach_count", "reply_count",
        "interested_count", "waitlist_count", "paid_count",
        "revenue_estimate", "notes", "decision", "decision_reason",
        "system_suggestion", "system_suggestion_reason",
    }
    conn = get_conn()
    cur = conn.cursor()
    parts = []
    params = []
    for k, v in kwargs.items():
        if k in valid_fields and v is not None:
            parts.append(f"{k} = ?")
            params.append(v)
    if parts:
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(experiment_id)
        cur.execute(
            f"UPDATE experiments SET {', '.join(parts)}, updated_at = ? WHERE id = ?",
            params
        )
        conn.commit()
    conn.close()


def get_experiments(limit=50, status=None):
    conn = get_conn()
    cur = conn.cursor()
    if status:
        cur.execute(
            """SELECT e.*, rp.stars,
                      sc.opportunity_score, sc.data_quality_score,
                      sc.final_recommendation
               FROM experiments e
               LEFT JOIN repos rp ON rp.id = e.repo_id
               LEFT JOIN (
                   SELECT sc.*, sn.repo_id
                   FROM scores sc
                   JOIN repo_snapshots sn ON sn.id = sc.repo_snapshot_id
                   AND sc.id IN (SELECT MAX(id) FROM scores GROUP BY repo_snapshot_id)
               ) sc ON sc.repo_id = e.repo_id
               WHERE e.status = ?
               ORDER BY e.updated_at DESC
               LIMIT ?""",
            (status, limit)
        )
    else:
        cur.execute(
            """SELECT e.*, rp.stars,
                      sc.opportunity_score, sc.data_quality_score,
                      sc.final_recommendation
               FROM experiments e
               LEFT JOIN repos rp ON rp.id = e.repo_id
               LEFT JOIN (
                   SELECT sc.*, sn.repo_id
                   FROM scores sc
                   JOIN repo_snapshots sn ON sn.id = sc.repo_snapshot_id
                   AND sc.id IN (SELECT MAX(id) FROM scores GROUP BY repo_snapshot_id)
               ) sc ON sc.repo_id = e.repo_id
               ORDER BY e.updated_at DESC
               LIMIT ?""",
            (limit,)
        )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_experiment(experiment_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT e.*, rp.stars,
                  sc.opportunity_score, sc.data_quality_score,
                  sc.final_recommendation
           FROM experiments e
           LEFT JOIN repos rp ON rp.id = e.repo_id
           LEFT JOIN (
               SELECT sc.*, sn.repo_id
               FROM scores sc
               JOIN repo_snapshots sn ON sn.id = sc.repo_snapshot_id
               AND sc.id IN (SELECT MAX(id) FROM scores GROUP BY repo_snapshot_id)
           ) sc ON sc.repo_id = e.repo_id
           WHERE e.id = ?""",
        (experiment_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def save_scan_run(keywords, target_repo_count=15, min_stars=100, max_stars=50000,
                  min_open_issues=5, max_issues_per_repo=20, trending_period='weekly',
                  time_range_days=30, total_repos=0,
                  llm_enabled=False, llm_provider=None, llm_model=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO scan_runs
           (started_at, keywords, target_repo_count, min_stars, max_stars,
            min_open_issues, max_issues_per_repo, trending_period,
            time_range_days, total_repos, status,
            llm_enabled, llm_provider, llm_model)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)""",
        (datetime.now(timezone.utc).isoformat(),
         json.dumps(keywords), target_repo_count,
         min_stars, max_stars, min_open_issues,
         max_issues_per_repo, trending_period,
         time_range_days, total_repos,
         1 if llm_enabled else 0, llm_provider, llm_model)
    )
    scan_run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return scan_run_id


def finish_scan_run(scan_run_id, status='completed', error_message=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE scan_runs SET finished_at = ?, status = ?, error_message = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), status, error_message, scan_run_id)
    )
    conn.commit()
    conn.close()


def save_mvp_brief(repo_id, mvp_type, output_path, used_llm=False,
                   llm_provider=None, llm_model=None,
                   product_name=None, one_sentence_positioning=None,
                   target_user=None):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """INSERT INTO mvp_briefs
           (repo_id, mvp_type, output_path, generated_at, used_llm,
            llm_provider, llm_model, product_name,
            one_sentence_positioning, target_user, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')""",
        (repo_id, mvp_type, str(output_path), now,
         1 if used_llm else 0, llm_provider, llm_model,
         product_name, one_sentence_positioning, target_user)
    )
    brief_id = cur.lastrowid
    conn.commit()
    conn.close()
    return brief_id


def get_mvp_briefs(limit=20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT mb.*, r.full_name
           FROM mvp_briefs mb
           JOIN repos r ON r.id = mb.repo_id
           ORDER BY mb.generated_at DESC
           LIMIT ?""",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_or_create_repo(repo):
    conn = get_conn()
    cur = conn.cursor()
    fn = repo.get("full_name", "")
    cur.execute("SELECT id FROM repos WHERE full_name = ?", (fn,))
    row = cur.fetchone()
    if row:
        repo_id = row["id"]
        cur.execute(
            """UPDATE repos SET stars=?, forks=?, open_issues=?,
               description=?, language=?, topics_json=?, license_name=?,
               homepage=?, pushed_at=?, updated_at=?, last_seen_at=?
               WHERE id=?""",
            (repo.get("stars", 0), repo.get("forks", 0),
             repo.get("open_issues", 0) or repo.get("open_issues_count", 0),
             repo.get("description", ""), repo.get("language", ""),
             json.dumps(repo.get("topics", [])),
             repo.get("license_name", ""), repo.get("homepage", ""),
             repo.get("pushed_at", ""), repo.get("updated_at", ""),
             datetime.now(timezone.utc).isoformat(), repo_id)
        )
    else:
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            """INSERT INTO repos
               (full_name, owner, name, url, description, language,
                stars, forks, open_issues, homepage, topics_json,
                license_name, created_at, updated_at, pushed_at,
                first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fn, repo.get("owner", ""), repo.get("name", ""),
             repo.get("url", ""), repo.get("description", ""),
             repo.get("language", ""), repo.get("stars", 0),
             repo.get("forks", 0),
             repo.get("open_issues", 0) or repo.get("open_issues_count", 0),
             repo.get("homepage", ""),
             json.dumps(repo.get("topics", [])),
             repo.get("license_name", ""),
             repo.get("created_at", ""), repo.get("updated_at", ""),
             repo.get("pushed_at", ""), now, now)
        )
        repo_id = cur.lastrowid

    conn.commit()
    conn.close()
    return repo_id


def save_snapshot(scan_run_id, repo_id, repo):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cur = conn.cursor()

    dq = repo.get("data_quality", "medium")
    if repo.get("readme_text") and len(repo.get("readme_text", "")) > 100:
        dq = "high"
    elif not repo.get("readme_text") or len(repo.get("readme_text", "")) < 50:
        if repo.get("open_issues_count", 0) > 0:
            dq = "medium"
        else:
            dq = "low"

    cur.execute(
        """INSERT INTO repo_snapshots
           (scan_run_id, repo_id, captured_at, stars, forks, open_issues,
            stars_delta_1d, stars_delta_7d, stars_delta_30d,
            stars_delta_source, data_quality)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (scan_run_id, repo_id, now,
         repo.get("stars", 0), repo.get("forks", 0),
         repo.get("open_issues_count") if "open_issues_count" in repo else repo.get("open_issues", 0),
         repo.get("stars_delta_1d"), repo.get("stars_delta_7d"),
         repo.get("stars_delta_30d"),
         repo.get("stars_delta_source", ""), dq)
    )
    snapshot_id = cur.lastrowid

    cur.execute(
        "INSERT INTO star_history (repo_id, captured_at, stars, source) VALUES (?, ?, ?, ?)",
        (repo_id, now, repo.get("stars", 0), "snapshot")
    )

    conn.commit()
    conn.close()
    return snapshot_id, dq


def save_issues(snapshot_id, issues):
    if not issues:
        return
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    for iss in issues:
        cur.execute(
            """INSERT INTO issues
               (repo_snapshot_id, title, url, labels_json, comments_count,
                updated_at, snippet, category, captured_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (snapshot_id, iss.get("title", ""), iss.get("url", ""),
             json.dumps(iss.get("labels", [])),
             iss.get("comments_count", 0),
             iss.get("updated_at", ""), iss.get("snippet", ""),
             iss.get("category", ""), now)
        )
    conn.commit()
    conn.close()


def save_score(scan_run_id, snapshot_id, repo, mvp, classification):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO scores
           (scan_run_id, repo_snapshot_id,
            hot_score, issue_score, early_score,
            commercial_gap_score, mvp_feasibility_score,
            opportunity_score,
            early_signals_json, commercial_signals_json,
            pain_categories_json, top_pain_categories_json,
            recommended_mvp_idea, mvp_type, best_for,
            all_ideas_json, alternative_ideas_json,
            data_quality_score, data_quality_label,
            data_quality_reasons_json,
            opportunity_verdict, verdict_reason,
            top_pain_cluster, top_pain_cluster_name,
            top_pain_cluster_count,
            pain_cluster_evidence_json,
            pain_cluster_monetization_hint,
            why_opportunity, why_not_worth,
            seven_day_mvp_plan_json,
            final_recommendation,
            ranking_flags_json, ranking_warning, suggested_next_action)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?)""",
        (scan_run_id, snapshot_id,
         repo.get("hot_score", 0), repo.get("issue_score", 0),
         repo.get("early_score", 0),
         repo.get("commercial_gap_score", 0),
         repo.get("mvp_feasibility_score", 0),
         repo.get("opportunity_score", 0),
         json.dumps(repo.get("readme_early_signals", [])),
         json.dumps(repo.get("readme_commercial_signals", [])),
         json.dumps(classification.get("category_counts", {})),
         json.dumps(repo.get("top_pain_categories", {})),
         repo.get("recommended_mvp_idea", ""),
         repo.get("mvp_type", ""), repo.get("best_for", ""),
         json.dumps(mvp.get("all_ideas", [])),
         json.dumps(mvp.get("alternative_ideas", [])),
         repo.get("data_quality_score", 0),
         repo.get("data_quality_label", "medium"),
         json.dumps(repo.get("data_quality_reasons", [])),
         repo.get("opportunity_verdict", ""),
         repo.get("verdict_reason", ""),
         repo.get("top_pain_cluster", ""),
         repo.get("top_pain_cluster_name", ""),
         repo.get("top_pain_cluster_count", 0),
         json.dumps(repo.get("pain_cluster_evidence", [])),
         repo.get("pain_cluster_monetization_hint", ""),
         repo.get("why_opportunity", ""),
         repo.get("why_not_worth", ""),
         json.dumps(repo.get("seven_day_mvp_plan", [])),
         repo.get("final_recommendation", ""),
         json.dumps(repo.get("ranking_flags", [])),
         repo.get("ranking_warning", ""),
         repo.get("suggested_next_action", ""))
    )
    conn.commit()
    conn.close()


def save_llm_analysis(scan_run_id, repo_id, analysis: dict):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """INSERT INTO llm_analyses
           (scan_run_id, repo_id, provider, model, status,
            error_message, analysis_json,
            one_sentence_summary, user_pain_summary,
            best_mvp_idea, mvp_type, target_customer, why_now,
            monetization_angle, build_difficulty, confidence,
            first_7_day_build_plan, risks, pain_clusters, llm_notes,
            cache_key, prompt_version, schema_version, latency_ms, status_detail,
            created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?)""",
        (scan_run_id, repo_id,
         analysis.get("llm_provider", ""),
         analysis.get("llm_model", ""),
         analysis.get("llm_status", "pending"),
         analysis.get("error_message", ""),
         json.dumps(analysis.get("llm_analysis", {}), ensure_ascii=False),
         analysis.get("one_sentence_summary", ""),
         analysis.get("user_pain_summary", ""),
         analysis.get("best_mvp_idea", ""),
         analysis.get("mvp_type", ""),
         analysis.get("target_customer", ""),
         analysis.get("why_now", ""),
         analysis.get("monetization_angle", ""),
         analysis.get("build_difficulty", ""),
         analysis.get("confidence", ""),
         json.dumps(analysis.get("first_7_day_build_plan", []), ensure_ascii=False),
         json.dumps(analysis.get("risks", []), ensure_ascii=False),
         json.dumps(analysis.get("pain_clusters", []), ensure_ascii=False),
         analysis.get("llm_notes", ""),
         analysis.get("cache_key", ""),
         analysis.get("prompt_version", ""),
         analysis.get("schema_version", ""),
         analysis.get("latency_ms", 0),
         analysis.get("status_detail", ""),
         now)
    )
    conn.commit()
    conn.close()


def get_cached_llm_analysis(cache_key: str) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM llm_analyses WHERE cache_key = ? AND status = 'success' ORDER BY created_at DESC LIMIT 1",
        (cache_key,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        d = dict(row)
        for field in ["analysis_json", "first_7_day_build_plan", "risks", "pain_clusters"]:
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return d
    return None


def get_latest_scan_runs(limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT ?", (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_repos_for_scan(scan_run_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """            SELECT r.*, sn.*, sc.opportunity_score, sc.hot_score, sc.issue_score,
                  sc.early_score, sc.commercial_gap_score, sc.mvp_feasibility_score,
                  sc.early_signals_json, sc.commercial_signals_json,
                  sc.pain_categories_json, sc.top_pain_categories_json,
                  sc.recommended_mvp_idea, sc.mvp_type, sc.best_for,
                  sc.all_ideas_json, sc.alternative_ideas_json,
                  sc.data_quality_score, sc.data_quality_label,
                  sc.data_quality_reasons_json,
                  sc.opportunity_verdict, sc.verdict_reason,
                  sc.top_pain_cluster, sc.top_pain_cluster_name,
                  sc.top_pain_cluster_count,
                  sc.pain_cluster_evidence_json,
                  sc.pain_cluster_monetization_hint,
                  sc.why_opportunity, sc.why_not_worth,
                  sc.seven_day_mvp_plan_json,
                  sc.final_recommendation,
                  sc.ranking_flags_json, sc.ranking_warning, sc.suggested_next_action,
                  sn.data_quality, sn.stars_delta_1d, sn.stars_delta_7d, sn.stars_delta_30d,
                  la.one_sentence_summary as llm_summary,
                  la.best_mvp_idea as llm_mvp_idea,
                  la.target_customer as llm_target_customer,
                  la.monetization_angle as llm_monetization_angle,
                  la.build_difficulty as llm_build_difficulty,
                  la.confidence as llm_confidence,
                  la.user_pain_summary as llm_user_pain_summary,
                  la.why_now as llm_why_now,
                  la.status as llm_status,
                  la.analysis_json as llm_analysis_json,
                  la.first_7_day_build_plan as llm_build_plan,
                  la.risks as llm_risks,
                  la.pain_clusters as llm_pain_clusters
           FROM repos r
           JOIN repo_snapshots sn ON sn.repo_id = r.id
           JOIN scores sc ON sc.repo_snapshot_id = sn.id
           LEFT JOIN llm_analyses la ON la.repo_id = r.id AND la.scan_run_id = ?
           WHERE sn.scan_run_id = ?
           ORDER BY sc.opportunity_score DESC""",
        (scan_run_id, scan_run_id)
    )
    rows = cur.fetchall()
    conn.close()
    return [_row_to_repo(r) for r in rows]


def get_issues_for_snapshot(snapshot_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM issues WHERE repo_snapshot_id = ? ORDER BY comments_count DESC",
        (snapshot_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [_row_to_issue(r) for r in rows]


def _row_to_repo(row):
    d = dict(row)
    for field in ["topics_json", "early_signals_json", "commercial_signals_json",
                   "pain_categories_json", "top_pain_categories_json",
                   "all_ideas_json", "alternative_ideas_json"]:
        if isinstance(d.get(field), str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = {}
    if "topics_json" in d and isinstance(d["topics_json"], (list, dict)):
        d["topics"] = d["topics_json"] if isinstance(d["topics_json"], list) else list(d["topics_json"].values())
    if "early_signals_json" in d:
        d["readme_early_signals"] = d["early_signals_json"] if isinstance(d["early_signals_json"], list) else []
    if "commercial_signals_json" in d:
        d["readme_commercial_signals"] = d["commercial_signals_json"] if isinstance(d["commercial_signals_json"], list) else []
    if "pain_categories_json" in d:
        d["pain_categories"] = d["pain_categories_json"]
    if "top_pain_categories_json" in d:
        d["top_pain_categories"] = d["top_pain_categories_json"]
    if "all_ideas_json" in d:
        d["all_ideas"] = d["all_ideas_json"] if isinstance(d["all_ideas_json"], list) else []
    if "alternative_ideas_json" in d:
        d["alternative_ideas"] = d["alternative_ideas_json"] if isinstance(d["alternative_ideas_json"], list) else []

    for field in ["llm_analysis_json", "llm_build_plan", "llm_risks", "llm_pain_clusters"]:
        if isinstance(d.get(field), str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = field in ("llm_build_plan", "llm_risks", "llm_pain_clusters") and [] or {}

    for field in ["data_quality_reasons_json", "pain_cluster_evidence_json",
                   "seven_day_mvp_plan_json", "ranking_flags_json"]:
        if isinstance(d.get(field), str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = [] if field in ("pain_cluster_evidence_json", "seven_day_mvp_plan_json",
                                            "ranking_flags_json") else {}

    if "data_quality_reasons_json" in d:
        d["data_quality_reasons"] = d["data_quality_reasons_json"]
    if "pain_cluster_evidence_json" in d:
        d["pain_cluster_evidence"] = d["pain_cluster_evidence_json"]
    if "seven_day_mvp_plan_json" in d:
        d["seven_day_mvp_plan"] = d["seven_day_mvp_plan_json"]
    if "ranking_flags_json" in d:
        d["ranking_flags"] = d["ranking_flags_json"] if isinstance(d["ranking_flags_json"], list) else []
    if "ranking_warning" in d:
        d["ranking_warning"] = d.get("ranking_warning", "")
    if "suggested_next_action" in d:
        d["suggested_next_action"] = d.get("suggested_next_action", "")

    d["open_issues_count"] = d.get("open_issues", 0)
    return d


def _row_to_issue(row):
    d = dict(row)
    if isinstance(d.get("labels_json"), str):
        try:
            d["labels"] = json.loads(d["labels_json"])
        except (json.JSONDecodeError, TypeError):
            d["labels"] = []
    return d


def _add_llm_columns(conn):
    cur = conn.cursor()
    new_cols = [
        "cache_key TEXT DEFAULT ''",
        "prompt_version TEXT DEFAULT ''",
        "schema_version TEXT DEFAULT ''",
        "latency_ms INTEGER DEFAULT 0",
        "status_detail TEXT DEFAULT ''",
    ]
    for col_def in new_cols:
        col_name = col_def.split()[0]
        cur.execute(
            "SELECT COUNT(*) FROM pragma_table_info('llm_analyses') WHERE name=?",
            (col_name,)
        )
        if cur.fetchone()[0] == 0:
            cur.execute(f"ALTER TABLE llm_analyses ADD COLUMN {col_def}")


def _add_watchlist_columns(conn):
    cur = conn.cursor()
    new_cols = [
        "user_hypothesis TEXT",
        "target_user_guess TEXT",
        "monetization_guess TEXT",
        "validation_next_step TEXT",
        "validation_result TEXT",
        "needs_review INTEGER DEFAULT 0",
        "review_reason TEXT",
    ]
    for col_def in new_cols:
        col_name = col_def.split()[0]
        cur.execute(
            "SELECT COUNT(*) FROM pragma_table_info('watchlist') WHERE name=?",
            (col_name,)
        )
        if cur.fetchone()[0] == 0:
            cur.execute(f"ALTER TABLE watchlist ADD COLUMN {col_def}")


def add_to_watchlist(repo_id, note=""):
    conn = get_conn()
    cur = conn.cursor()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    try:
        cur.execute(
            """INSERT OR REPLACE INTO watchlist
               (repo_id, added_at, note, status)
               VALUES (?, ?, ?, 'watching')""",
            (repo_id, now, note)
        )
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()


def remove_from_watchlist(repo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM watchlist WHERE repo_id = ?", (repo_id,))
    conn.commit()
    conn.close()


def update_watchlist_status(repo_id, status=None, note=None, rating=None,
                             user_hypothesis=None, target_user_guess=None,
                             monetization_guess=None, validation_next_step=None,
                             validation_result=None):
    conn = get_conn()
    cur = conn.cursor()
    parts = []
    params = []
    if status:
        parts.append("status = ?")
        params.append(status)
    if note is not None:
        parts.append("note = ?")
        params.append(note)
    if rating is not None:
        parts.append("user_rating = ?")
        params.append(rating)
    if user_hypothesis is not None:
        parts.append("user_hypothesis = ?")
        params.append(user_hypothesis)
    if target_user_guess is not None:
        parts.append("target_user_guess = ?")
        params.append(target_user_guess)
    if monetization_guess is not None:
        parts.append("monetization_guess = ?")
        params.append(monetization_guess)
    if validation_next_step is not None:
        parts.append("validation_next_step = ?")
        params.append(validation_next_step)
    if validation_result is not None:
        parts.append("validation_result = ?")
        params.append(validation_result)
    if parts:
        params.append(repo_id)
        cur.execute(
            f"UPDATE watchlist SET {', '.join(parts)} WHERE repo_id = ?",
            params
        )
        conn.commit()
    conn.close()


def get_watchlist(scan_run_id=None, compute_deltas=True):
    conn = get_conn()
    cur = conn.cursor()
    if scan_run_id:
        cur.execute(
            """SELECT w.*, r.full_name, r.stars, r.url, r.language, r.id as repo_id,
                      sc.opportunity_score, sc.data_quality_score,
                      sc.opportunity_verdict, sc.final_recommendation,
                      sc.recommended_mvp_idea, sc.hot_score, sc.issue_score,
                      sc.ranking_flags_json, sc.ranking_warning, sc.suggested_next_action,
                      sn.captured_at as last_seen_at,
                      sn.stars_delta_7d, sn.stars_delta_1d, sn.stars_delta_30d
               FROM watchlist w
               JOIN repos r ON r.id = w.repo_id
               LEFT JOIN repo_snapshots sn ON sn.repo_id = r.id AND sn.scan_run_id = ?
               LEFT JOIN scores sc ON sc.repo_snapshot_id = sn.id
               ORDER BY w.added_at DESC""",
            (scan_run_id,)
        )
    else:
        cur.execute(
            """SELECT w.*, r.full_name, r.stars, r.url, r.language, r.id as repo_id,
                      null as opportunity_score, null as data_quality_score,
                      null as opportunity_verdict, null as final_recommendation,
                      null as recommended_mvp_idea, null as hot_score, null as issue_score,
                      null as ranking_flags_json, null as ranking_warning, null as suggested_next_action,
                      r.last_seen_at,
                      null as stars_delta_7d, null as stars_delta_1d, null as stars_delta_30d
               FROM watchlist w
               JOIN repos r ON r.id = w.repo_id
               ORDER BY w.added_at DESC"""
        )
    rows = cur.fetchall()
    conn.close()
    result = [dict(r) for r in rows]

    if compute_deltas and result:
        for w in result:
            rid = w.get("repo_id")
            if rid:
                snapshots = get_snapshot_history(rid, limit=2)
                if len(snapshots) >= 2:
                    w["stars_delta_since_first_seen"] = snapshots[-1].get("stars", 0) - snapshots[0].get("stars", 0)
                    prev_opp = None
                    prev_dq = None
                    for sn in snapshots:
                        if sn.get("id") and sn["id"] != w.get("last_seen_at"):
                            pass
                if len(snapshots) >= 1:
                    current_stars = w.get("stars", 0)
                    first_stars = snapshots[-1].get("stars", current_stars) if snapshots else current_stars
                    w["stars_delta_since_first_seen"] = current_stars - first_stars
    return result


def update_watchlist_review_fields(repo_id, **kwargs):
    valid_fields = {"user_hypothesis", "target_user_guess", "monetization_guess",
                     "validation_next_step", "validation_result"}
    conn = get_conn()
    cur = conn.cursor()
    parts = []
    params = []
    for k, v in kwargs.items():
        if k in valid_fields and v is not None:
            parts.append(f"{k} = ?")
            params.append(v)
    if parts:
        params.append(repo_id)
        cur.execute(
            f"UPDATE watchlist SET {', '.join(parts)} WHERE repo_id = ?",
            params
        )
        conn.commit()
    conn.close()


def set_watchlist_needs_review(repo_id, needs_review=True, reason=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE watchlist SET needs_review = ?, review_reason = ? WHERE repo_id = ?",
        (1 if needs_review else 0, reason, repo_id)
    )
    conn.commit()
    conn.close()


def get_repo_id_by_name(full_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM repos WHERE full_name = ?", (full_name,))
    row = cur.fetchone()
    conn.close()
    return row["id"] if row else None


def get_watchlist_status(repo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM watchlist WHERE repo_id = ?", (repo_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_snapshot_history(repo_id, limit=20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT sn.*, sr.started_at as scan_time
           FROM repo_snapshots sn
           JOIN scan_runs sr ON sr.id = sn.scan_run_id
           WHERE sn.repo_id = ?
           ORDER BY sn.captured_at DESC
           LIMIT ?""",
        (repo_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_watchlist_repos():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT w.*, r.full_name, r.stars, r.url, r.language, r.description, r.id as repo_id,
                  r.open_issues as open_issues_count, r.topics_json, r.license_name
           FROM watchlist w
           JOIN repos r ON r.id = w.repo_id
           ORDER BY w.added_at DESC"""
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_two_snapshots(repo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT sn.*, sr.started_at as scan_time, sr.id as scan_run_id
           FROM repo_snapshots sn
           JOIN scan_runs sr ON sr.id = sn.scan_run_id
           WHERE sn.repo_id = ?
           ORDER BY sn.captured_at DESC
           LIMIT 2""",
        (repo_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_score_for_repo(repo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT sc.*
           FROM scores sc
           JOIN repo_snapshots sn ON sn.id = sc.repo_snapshot_id
           WHERE sn.repo_id = ?
           ORDER BY sn.captured_at DESC
           LIMIT 1""",
        (repo_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_repo_snapshot_by_scan(repo_id, scan_run_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM repo_snapshots WHERE repo_id = ? AND scan_run_id = ? LIMIT 1",
        (repo_id, scan_run_id)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def save_daily_scan_run():
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """INSERT INTO scan_runs (started_at, mode, status)
           VALUES (?, 'daily_watchlist', 'running')""",
        (now,)
    )
    scan_run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return scan_run_id
