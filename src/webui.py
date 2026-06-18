import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.database import init_db, save_scan_run, get_or_create_repo, save_snapshot
from src.database import save_issues, save_score, save_llm_analysis, finish_scan_run
from src.database import get_latest_scan_runs, get_repos_for_scan
from src.database import get_issues_for_snapshot
from src.database import add_to_watchlist, remove_from_watchlist, update_watchlist_status
from src.database import get_watchlist, get_repo_id_by_name, update_watchlist_review_fields
from src.database import set_watchlist_needs_review
from src.report import export_watchlist_report
from src.repo_search import search_repos, clear_cache
from src.repo_page_scraper import scrape_issues_direct
from src.readme_analyzer import analyze_readme
from src.issue_classifier import classify_issues, CATEGORY_NAMES
from src.scorer import calculate_opportunity_score, RECOMMENDATION_MAP_CN
from src.mvp_recommender import recommend_mvp
from src.report import export_csv, export_json, export_markdown
from src.llm.base import LLMConfig
from src.llm.analyzer import LLMAnalyzer
from src.llm.provider_router import test_connection, create_client
from src.llm.prompts import LLM_TEST_PROMPT
from pathlib import Path

import pandas as pd
import gradio as gr

DEFAULT_KEYWORDS_STR = ", ".join(settings.default_keywords)

LANG = "zh"

I18N = {
    "lang_switch":         {"zh": "中文", "en": "English"},
    "header_title":        {"zh": "GitHub 创业机会雷达", "en": "GitHub Opportunity Radar"},
    "header_subtitle":     {"zh": "实时抓取 GitHub Trending + Search，发现 AI / 开发者工具的早期创业机会。无需 API Token，无需 Mock 数据。", "en": "Real-time GitHub Trending + Search to discover early-stage AI / dev-tool opportunities. No API token, no mock data needed."},

    "accordion_scan":      {"zh": "扫描设置", "en": "Scan Settings"},
    "keywords":            {"zh": "关键词（逗号分隔）", "en": "Keywords (comma-separated)"},
    "target_repos":        {"zh": "目标仓库数", "en": "Target Repos"},
    "min_stars":           {"zh": "最少 Stars", "en": "Min Stars"},
    "max_stars":           {"zh": "最多 Stars", "en": "Max Stars"},
    "min_issues":          {"zh": "最少 Issues", "en": "Min Issues"},
    "max_issues":          {"zh": "最多 Issues/仓库", "en": "Max Issues / Repo"},
    "trending_period":     {"zh": "Trending 周期", "en": "Trending Period"},
    "trending_daily":      {"zh": "每日", "en": "Daily"},
    "trending_weekly":     {"zh": "每周", "en": "Weekly"},
    "trending_monthly":    {"zh": "每月", "en": "Monthly"},
    "trending_all":        {"zh": "全部", "en": "All"},
    "request_delay":       {"zh": "请求间隔（秒）", "en": "Request Delay (s)"},
    "enable_readme":       {"zh": "获取 README（raw.githubusercontent.com）", "en": "Fetch README (raw.githubusercontent.com)"},
    "enable_search":       {"zh": "搜索补充（Trending 不足时）", "en": "Search Fallback (when Trending insufficient)"},
    "exclude_commercial":  {"zh": "降低商业化仓库权重", "en": "Reduce Commercial Repo Weight"},

    "accordion_llm":       {"zh": "LLM 增强分析设置", "en": "LLM Enhancement Settings"},
    "llm_hint":            {"zh": "启用后，将对排名前 N 的仓库进行 LLM 增强分析（不覆盖规则评分）。", "en": "When enabled, top N repos will get LLM-enhanced analysis (rule scores always apply)."},
    "enable_llm":          {"zh": "启用 LLM 分析", "en": "Enable LLM Analysis"},
    "llm_provider":        {"zh": "LLM Provider", "en": "LLM Provider"},
    "provider_none":       {"zh": "不启用", "en": "Disabled"},
    "provider_ollama":     {"zh": "Ollama（本地）", "en": "Ollama (Local)"},
    "provider_openai":     {"zh": "OpenAI 兼容", "en": "OpenAI Compatible"},
    "provider_litellm":    {"zh": "LiteLLM 代理", "en": "LiteLLM Proxy"},
    "base_url":            {"zh": "Base URL", "en": "Base URL"},
    "model":               {"zh": "模型", "en": "Model"},
    "api_key":             {"zh": "API Key（可空）", "en": "API Key (optional)"},
    "api_key_ph":          {"zh": "OpenAI 兼容 / LiteLLM 需要", "en": "Required for OpenAI / LiteLLM"},
    "max_tokens":          {"zh": "最大 Token", "en": "Max Tokens"},
    "temperature":         {"zh": "Temperature", "en": "Temperature"},
    "output_lang":         {"zh": "输出语言", "en": "Output Language"},
    "output_lang_zh":      {"zh": "中文", "en": "Chinese"},
    "output_lang_en":      {"zh": "English", "en": "English"},
    "max_llm_repos":       {"zh": "最多分析仓库数", "en": "Max LLM Repos"},
    "timeout":             {"zh": "Timeout（秒）", "en": "Timeout (s)"},
    "json_schema_strict":  {"zh": "JSON Schema 严格模式", "en": "JSON Schema Strict Mode"},
    "force_json_mode":     {"zh": "强制 JSON Mode（json_object）", "en": "Force JSON Mode (json_object)"},
    "enable_llm_cache":    {"zh": "启用 LLM 缓存", "en": "Enable LLM Cache"},
    "test_llm_conn":       {"zh": "🔄 测试 LLM 连接", "en": "🔄 Test LLM Connection"},
    "preload_ollama":      {"zh": "⚡ 预加载 Ollama 模型", "en": "⚡ Preload Ollama Model"},

    "btn_scan":            {"zh": "开始实时扫描", "en": "Start Scan"},
    "btn_load":            {"zh": "加载上次扫描", "en": "Load Last Scan"},
    "scan_hint":           {"zh": "数据来自 GitHub 公开页面。受限于频率限制，扫描需要 1-3 分钟。结果缓存 6 小时。", "en": "Data from public GitHub pages. Scan takes 1-3 min due to rate limits. Results cached for 6h."},
    "summary_label":       {"zh": "扫描摘要", "en": "Scan Summary"},
    "results_label":       {"zh": "结果（按机会总分排序）", "en": "Results (sorted by opportunity score)"},
    "col_rank":            {"zh": "排名", "en": "Rank"},
    "col_repo":            {"zh": "仓库", "en": "Repo"},
    "col_stars":           {"zh": "Stars", "en": "Stars"},
    "col_weekly":          {"zh": "+/周", "en": "+/wk"},
    "col_issues":          {"zh": "Issues", "en": "Issues"},
    "col_lang":            {"zh": "语言", "en": "Language"},
    "col_data_quality":    {"zh": "数据质量", "en": "Data Quality"},
    "col_verdict":         {"zh": "决策", "en": "Verdict"},
    "col_hot":             {"zh": "热度", "en": "Hot"},
    "col_demand":          {"zh": "需求", "en": "Demand"},
    "col_early":           {"zh": "早期度", "en": "Early"},
    "col_gap":             {"zh": "商业空白", "en": "Gap"},
    "col_feasibility":     {"zh": "可行性", "en": "Feasibility"},
    "col_total":           {"zh": "总分", "en": "Total"},
    "col_rec":             {"zh": "推荐", "en": "Rec"},
    "col_llm_summary":     {"zh": "LLM 摘要", "en": "LLM Summary"},
    "col_llm_mvp":         {"zh": "LLM MVP", "en": "LLM MVP"},
    "col_llm_status":      {"zh": "LLM 状态", "en": "LLM Status"},
    "col_url":             {"zh": "URL", "en": "URL"},

    "export_csv":          {"zh": "导出 CSV", "en": "Export CSV"},
    "export_json":         {"zh": "导出 JSON", "en": "Export JSON"},
    "export_md":           {"zh": "导出 Markdown", "en": "Export Markdown"},
    "detail_label":        {"zh": "仓库详情", "en": "Repo Detail"},

    "watchlist_title":     {"zh": "📋 Watchlist 管理", "en": "📋 Watchlist Manager"},
    "wl_repo_label":       {"zh": "仓库名（格式：owner/repo）", "en": "Repo Name (format: owner/repo)"},
    "wl_repo_ph":          {"zh": "例如：chopratejas/headroom", "en": "e.g. chopratejas/headroom"},
    "wl_note_label":       {"zh": "备注（可选）", "en": "Note (optional)"},
    "wl_add_btn":          {"zh": "➕ 加入 Watchlist", "en": "➕ Add to Watchlist"},
    "wl_remove_btn":       {"zh": "🗑 移除", "en": "🗑 Remove"},
    "wl_load_btn":         {"zh": "📋 加载 Watchlist", "en": "📋 Load Watchlist"},
    "wl_export_btn":       {"zh": "📄 导出 Watchlist 报告", "en": "📄 Export Watchlist Report"},
    "wl_table_label":      {"zh": "Watchlist", "en": "Watchlist"},
    "wl_col_repo":         {"zh": "仓库", "en": "Repo"},
    "wl_col_status":       {"zh": "状态", "en": "Status"},
    "wl_col_score":        {"zh": "分数", "en": "Score"},
    "wl_col_dq":           {"zh": "数据质量", "en": "Data Quality"},
    "wl_col_verdict":      {"zh": "决策", "en": "Verdict"},
    "wl_col_rec":          {"zh": "建议", "en": "Rec"},
    "wl_col_rating":       {"zh": "评分", "en": "Rating"},
    "wl_col_weekly":       {"zh": "+/7d", "en": "+/7d"},
    "wl_col_total_delta":  {"zh": "+总", "en": "+Total"},
    "wl_col_review":       {"zh": "需Review", "en": "Review?"},
    "wl_review_title":     {"zh": "✏️ 手动复盘字段", "en": "✏️ Manual Review Fields"},
    "wl_hypothesis":       {"zh": "我认为这个机会是什么", "en": "Hypothesis"},
    "wl_target_user":      {"zh": "目标用户是谁", "en": "Target Users"},
    "wl_monetization":     {"zh": "可能怎么收钱", "en": "Monetization"},
    "wl_next_step":        {"zh": "下一步验证动作", "en": "Next Validation Step"},
    "wl_validation":       {"zh": "验证结果记录", "en": "Validation Result"},
    "wl_update_btn":       {"zh": "💾 更新复盘字段", "en": "💾 Update Fields"},

    "val_title":           {"zh": "🧪 Validation 验证包", "en": "🧪 Validation Pack"},
    "val_desc":            {"zh": "为 Watchlist 中的仓库生成结构化验证包。", "en": "Generate a structured validation pack for any watchlisted repo."},
    "val_repo_label":      {"zh": "仓库全名", "en": "Repo Full Name"},
    "val_repo_ph":         {"zh": "owner/repo（需存在于数据库）", "en": "owner/repo (must exist in database)"},
    "val_llm_label":       {"zh": "启用 LLM 增强（可选）", "en": "Enable LLM enhancement (optional)"},
    "val_gen_btn":         {"zh": "生成 Validation Pack", "en": "Generate Validation Pack"},
    "val_brief":           {"zh": "机会简报", "en": "Opportunity Brief"},
    "val_mvp":             {"zh": "MVP 范围", "en": "MVP Scope"},
    "val_replies":         {"zh": "Issue 回复草稿", "en": "Issue Reply Drafts"},
    "val_launch":          {"zh": "发布帖子草稿", "en": "Launch Post Drafts"},

    "mvp_title":           {"zh": "MVP Builder Brief", "en": "MVP Builder Brief"},
    "mvp_desc":            {"zh": "为仓库生成结构化 MVP Brief，可直接交给 Codex。", "en": "Generate a structured MVP brief that can be handed to Codex."},
    "mvp_repo_label":      {"zh": "仓库全名", "en": "Repo Full Name"},
    "mvp_repo_ph":         {"zh": "owner/repo（需存在于数据库）", "en": "owner/repo (must exist in database)"},
    "mvp_type_label":      {"zh": "MVP 类型", "en": "MVP Type"},
    "mvp_type_auto":       {"zh": "auto（自动检测）", "en": "auto (auto-detect)"},
    "mvp_llm_label":       {"zh": "启用 LLM 增强（可选）", "en": "Enable LLM enhancement (optional)"},
    "mvp_gen_btn":         {"zh": "生成 MVP Brief", "en": "Generate MVP Brief"},
    "mvp_brief_preview":   {"zh": "产品 Brief", "en": "Product Brief"},
    "mvp_req_preview":     {"zh": "MVP 需求", "en": "MVP Requirements"},
    "mvp_codex_preview":   {"zh": "Codex Prompt", "en": "Codex Prompt"},
    "mvp_landing_preview": {"zh": "落地页", "en": "Landing Page"},

    "exp_title":           {"zh": "Experiment Tracker", "en": "Experiment Tracker"},
    "exp_desc":            {"zh": "跟踪从 Watchlist 仓库到外部 MVP 项目的实验流程。", "en": "Track experiments from watchlist repo to external MVP project."},
    "exp_repo_label":      {"zh": "仓库全名", "en": "Repo Full Name"},
    "exp_repo_ph":         {"zh": "owner/repo", "en": "owner/repo"},
    "exp_name_label":      {"zh": "实验名称", "en": "Experiment Name"},
    "exp_name_ph":         {"zh": "描述此实验", "en": "Describe the experiment"},
    "exp_type_label":      {"zh": "MVP 类型", "en": "MVP Type"},
    "exp_priority_label":  {"zh": "优先级", "en": "Priority"},
    "exp_priority_high":   {"zh": "高", "en": "High"},
    "exp_priority_medium": {"zh": "中", "en": "Medium"},
    "exp_priority_low":    {"zh": "低", "en": "Low"},
    "exp_create_btn":      {"zh": "创建实验", "en": "Create Experiment"},
    "exp_load_btn":        {"zh": "加载实验", "en": "Load Experiments"},
    "exp_dash_btn":        {"zh": "生成 Dashboard", "en": "Generate Dashboard"},
    "exp_table_label":     {"zh": "实验列表", "en": "Experiments"},
    "exp_col_id":          {"zh": "ID", "en": "ID"},
    "exp_col_repo":        {"zh": "仓库", "en": "Repo"},
    "exp_col_name":        {"zh": "名称", "en": "Name"},
    "exp_col_type":        {"zh": "类型", "en": "Type"},
    "exp_col_status":      {"zh": "状态", "en": "Status"},
    "exp_col_priority":    {"zh": "优先级", "en": "Priority"},
    "exp_col_decision":    {"zh": "决策", "en": "Decision"},
    "exp_col_outreach":    {"zh": "触达", "en": "Outreach"},
    "exp_col_interested":  {"zh": "感兴趣", "en": "Interested"},
    "exp_col_paid":        {"zh": "已付费", "en": "Paid"},
    "exp_col_updated":     {"zh": "更新", "en": "Updated"},
    "exp_edit_title":      {"zh": "编辑实验", "en": "Edit Experiment"},
    "exp_edit_id":         {"zh": "实验 ID", "en": "Experiment ID"},
    "exp_edit_status":     {"zh": "状态", "en": "Status"},
    "exp_edit_decision":   {"zh": "决策", "en": "Decision"},
    "exp_demo_url":        {"zh": "Demo URL", "en": "Demo URL"},
    "exp_github_url":      {"zh": "GitHub 仓库 URL", "en": "GitHub Repo URL"},
    "exp_landing_url":     {"zh": "落地页 URL", "en": "Landing Page URL"},
    "exp_target_user":     {"zh": "目标用户", "en": "Target User"},
    "exp_target_user_ph":  {"zh": "这是给谁用的？", "en": "Who is this for?"},
    "exp_hypothesis":      {"zh": "假设", "en": "Hypothesis"},
    "exp_hypothesis_ph":   {"zh": "我相信...", "en": "I believe that..."},
    "exp_success":         {"zh": "成功标准", "en": "Success Criteria"},
    "exp_success_ph":      {"zh": "如何判断有效？", "en": "How to know it works?"},
    "exp_outreach_count":  {"zh": "触达人数", "en": "Outreach Count"},
    "exp_reply_count":     {"zh": "回复数", "en": "Reply Count"},
    "exp_interested_count":{"zh": "感兴趣数", "en": "Interested Count"},
    "exp_waitlist_count":  {"zh": "候补数", "en": "Waitlist Count"},
    "exp_paid_count":      {"zh": "已付费数", "en": "Paid Count"},
    "exp_revenue":         {"zh": "收入预估", "en": "Revenue Estimate"},
    "exp_notes":           {"zh": "备注", "en": "Notes"},
    "exp_channel":         {"zh": "验证渠道", "en": "Validation Channel"},
    "exp_channel_ph":      {"zh": "Twitter, LinkedIn, Reddit...", "en": "Twitter, LinkedIn, Reddit..."},
    "exp_save_btn":        {"zh": "保存更新", "en": "Save Update"},
    "exp_report_btn":      {"zh": "生成报告", "en": "Generate Report"},
    "exp_codex_btn":       {"zh": "生成 Codex Task", "en": "Generate Codex Task"},

    "err_val_repo_ph":    {"zh": "请输入仓库名（owner/repo）。", "en": "Please enter a repo name (owner/repo)."},
    "err_mvp_repo_ph":    {"zh": "请输入仓库名。", "en": "Please enter a repo name."},
    "err_mvp_not_found":  {"zh": "仓库 {} 未在数据库中。请先加入 Watchlist。", "en": "Repo {} not found in database. Add it to Watchlist first."},
    "err_exp_repo_name":  {"zh": "请输入仓库名和实验名称。", "en": "Please enter repo name and experiment name."},
    "err_exp_repo_db":    {"zh": "仓库 {} 未在数据库中。", "en": "Repo {} not found in database."},
    "err_exp_id":         {"zh": "请输入实验 ID。", "en": "Please enter Experiment ID."},
    "err_exp_create":     {"zh": "创建失败。", "en": "Create failed."},
    "msg_val_generated":  {"zh": "✅ Validation 包已生成在 {}（{} 个文件）", "en": "✅ Validation pack generated at {} ({} files)"},
    "msg_mvp_generated":  {"zh": "✅ MVP brief 已生成在 {}（{} 个文件）", "en": "✅ MVP brief generated at {} ({} files)"},
    "msg_exp_created":    {"zh": "实验 #{} 已创建: {}", "en": "Experiment #{} created: {}"},
    "msg_exp_loaded":     {"zh": "已加载 {} 个实验。", "en": "Loaded {} experiments."},
    "msg_exp_updated":    {"zh": "实验 #{} 已更新。", "en": "Experiment #{} updated."},
    "msg_exp_report":     {"zh": "报告已生成: {}", "en": "Report generated: {}"},
    "msg_exp_codex":      {"zh": "Codex task 已生成: {}", "en": "Codex task generated: {}"},
    "msg_no_exps":        {"zh": "未找到实验。", "en": "No experiments found."},

    "err_no_selection":     {"zh": "未选择数据。", "en": "No data selected."},
    "err_select_row":       {"zh": "请选择一行。", "en": "Please select a row."},
    "err_no_scan_data":     {"zh": "未找到扫描数据。", "en": "No scan data found."},
    "err_repo_not_found":   {"zh": "仓库 {} 未找到。", "en": "Repo {} not found."},
    "err_repo_not_in_db":   {"zh": "仓库 {} 未在数据库中。请先扫描。", "en": "Repo {} not in database. Scan first."},
    "msg_wl_added":         {"zh": "✅ {} 已加入 Watchlist", "en": "✅ {} added to Watchlist"},
    "msg_wl_add_fail":      {"zh": "❌ 添加失败", "en": "❌ Add failed"},
    "msg_wl_removed":       {"zh": "🗑 {} 已从 Watchlist 移除", "en": "🗑 {} removed from Watchlist"},
    "msg_wl_updated":       {"zh": "✅ {} 复盘字段已更新", "en": "✅ {} review fields updated"},
    "msg_wl_empty":         {"zh": "Watchlist 为空。加入仓库后这里会显示。", "en": "Watchlist is empty. Add repos to see them here."},
    "msg_wl_loaded":        {"zh": "Watchlist 共 {} 项", "en": "Watchlist: {} items"},
    "msg_wl_exported":      {"zh": "✅ 已导出: {}", "en": "✅ Exported: {}"},
    "msg_wl_empty_export":  {"zh": "Watchlist 为空，无法导出", "en": "Watchlist is empty, nothing to export"},
    "err_wl_no_input":      {"zh": "请先输入仓库名（格式：owner/repo）", "en": "Please enter repo name (format: owner/repo)"},
    "msg_no_last_scan":     {"zh": "未找到上次扫描。", "en": "No previous scan found."},
    "msg_no_repos_scan":    {"zh": "上次扫描没有仓库数据。", "en": "Last scan had no repo data."},
    "msg_scan_loaded":      {"zh": "已加载 {} 个仓库的上次扫描结果。", "en": "Loaded last scan results ({} repos)."},
    "msg_preload_ok":       {"zh": "✅ 预加载成功", "en": "✅ Preloaded successfully"},
    "msg_preload_fail":     {"zh": "❌ 预加载失败（请检查 Ollama 是否运行）", "en": "❌ Preload failed (check if Ollama is running)"},
    "msg_no_preload":       {"zh": "❌ 不支持预加载", "en": "❌ Preload not supported"},
}

import os
if "OPENCODE_LANG" in os.environ:
    LANG = os.environ["OPENCODE_LANG"]

def _(key, *args):
    val = I18N.get(key, {}).get(LANG, key)
    if args:
        return val.format(*args)
    return val

CUSTOM_CSS = """
.gradio-container { max-width: 1440px; margin: auto; }
.detail-markdown h1 { border-bottom: 2px solid #4f46e5; padding-bottom: 8px; margin-top: 0; }
.detail-markdown h2 { color: #4f46e5; margin-top: 24px; font-size: 1.15em; }
.detail-markdown table { width: 100%; border-collapse: collapse; }
.detail-markdown th { background: #4f46e5; color: white; padding: 8px 12px; text-align: left; }
.detail-markdown td { padding: 6px 12px; border: 1px solid #e5e7eb; }
.detail-markdown hr { border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }
.score-bar { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
.score-bar-label { width: 100px; font-size: 0.85em; color: #6b7280; text-align: right; }
.score-bar-fill { height: 16px; border-radius: 8px; transition: width 0.4s ease; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin: 2px; }
.tag-early { background: #fef3c7; color: #92400e; }
.tag-commercial { background: #dbeafe; color: #1e40af; }
.tag-llm { background: #ede9fe; color: #5b21b6; }
.pain-bar { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
.pain-label { width: 150px; font-size: 0.85em; }
.pain-fill { height: 10px; border-radius: 5px; background: #4f46e5; }
.llm-section { background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 8px; padding: 16px; margin: 12px 0; }
.llm-section h3 { color: #5b21b6; margin-top: 0; }
.risk-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #fce7f3; color: #9d174d; font-size: 0.85em; margin: 2px; }
.plan-step { padding: 4px 0; border-bottom: 1px solid #f3e8ff; }
"""


def _score_bar(label, value, max_val, color):
    pct = min(value / max_val * 100, 100)
    return (
        f'<div class="score-bar">'
        f'<span class="score-bar-label">{label}</span>'
        f'<div style="flex:1;background:#f3f4f6;border-radius:8px;height:16px">'
        f'<div class="score-bar-fill" style="width:{pct}%;background:{color}"></div>'
        f'</div>'
        f'<span style="min-width:50px;font-weight:600">{value}/{max_val}</span>'
        f'</div>'
    )


def run_scan_ui(keywords_str, target_count, min_stars, max_stars,
                min_open_issues, max_issues, trending_period,
                request_delay, enable_raw_readme, enable_search_fallback,
                exclude_commercial,
                enable_llm, llm_provider, llm_base_url, llm_model,
                llm_api_key, llm_temperature, llm_max_tokens,
                llm_language, llm_max_repos, llm_json_schema,
                llm_force_json, llm_timeout, llm_cache_enabled,
                progress=gr.Progress()):
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        keywords = settings.default_keywords
        keywords_str = ", ".join(keywords)

    settings.request_delay_seconds = request_delay
    settings.enable_raw_readme_fetch = enable_raw_readme
    settings.enable_github_search_fallback = enable_search_fallback
    settings.exclude_mature_commercial = exclude_commercial
    settings.llm_use_json_schema = llm_json_schema

    progress(0, desc="初始化数据库")
    init_db()

    scan_run_id = save_scan_run(
        keywords=keywords, target_repo_count=target_count,
        min_stars=min_stars, max_stars=max_stars,
        min_open_issues=min_open_issues, max_issues_per_repo=max_issues,
        trending_period=trending_period, total_repos=0,
        llm_enabled=enable_llm,
        llm_provider=llm_provider if enable_llm and llm_provider != "none" else None,
        llm_model=llm_model if enable_llm and llm_provider != "none" else None,
    )

    llm_analyzer = None
    llm_mode = "disabled"
    if enable_llm and llm_provider != "none":
        llm_config = LLMConfig(
            provider=llm_provider, base_url=llm_base_url, model=llm_model,
            api_key=llm_api_key, temperature=llm_temperature,
            max_tokens=llm_max_tokens, language=llm_language,
            max_repos=llm_max_repos, timeout=llm_timeout,
            use_json_schema=llm_json_schema,
            force_json_mode=llm_force_json,
            cache_enabled=llm_cache_enabled,
        )
        llm_analyzer = LLMAnalyzer(llm_config)
        if not llm_analyzer.enabled:
            llm_mode = "unavailable"
            print("  [LLM] Provider unavailable, fallback to rule-based analysis.")
        else:
            llm_mode = llm_provider
            print(f"  [LLM] Using {llm_provider} / {llm_model}")

    repos = search_repos(
        keywords=keywords, target_count=target_count,
        min_stars=min_stars, max_stars=max_stars,
        min_open_issues=min_open_issues, trending_period=trending_period,
    )

    if not repos:
        finish_scan_run(scan_run_id, "completed", "No repos found")
        return (None, None, None,
                "未找到仓库。GitHub 可能限制了访问频率，或页面结构已变化。"
                "请尝试不同的关键词或减少仓库数量。")

    results = []
    for idx, repo in enumerate(repos):
        fn = repo["full_name"]
        progress((idx + 1) / len(repos), desc=f"分析 {fn}")

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

    results.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

    if llm_analyzer and llm_analyzer.enabled:
        llm_target = min(len(results), llm_max_repos)
        progress(0.9, desc=f"LLM 增强分析 ({llm_target} 个仓库)")
        print(f"\n  [LLM] 分析前 {llm_target} 个仓库...")
        llm_analyzer.cache = {}
        for idx, repo in enumerate(results[:llm_target]):
            fn = repo["full_name"]
            repo["repo_id"] = get_or_create_repo(repo)
            progress(0.9 + (idx + 1) / llm_target * 0.1, desc=f"LLM: {fn}")
            issues = scrape_issues_direct(fn, max_count=max_issues)
            analysis = llm_analyzer.analyze_repo(
                repo, issues, scan_run_id,
                db_save_func=lambda sid, rid, a: save_llm_analysis(sid, rid, a)
            )
            status = analysis.get("llm_status", "failed")
            if status == "success":
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
                repo["llm_status"] = "success"
                updated = calculate_opportunity_score(
                    repo, issues, classification, data_quality,
                    llm_status="success", llm_analysis=analysis
                )
                repo.update(updated)
            elif status == "unavailable":
                print(f"    LLM 不可用，停止 LLM 分析")
                break
            else:
                repo["llm_status"] = "failed"
                updated = calculate_opportunity_score(
                    repo, issues, classification, data_quality,
                    llm_status="failed", llm_analysis=None
                )
                repo.update(updated)

    progress(1.0, desc="生成报告")
    csv_path = export_csv(results)
    json_path = export_json(results)
    md_path = export_markdown(results)

    table_data = []
    for i, r in enumerate(results, 1):
        delta = r.get("stars_delta_7d")
        llm_status = r.get("llm_status", "")
        llm_summary = r.get("llm_summary", "")[:80] if r.get("llm_summary") else ""
        llm_mvp = r.get("llm_mvp_idea", "")[:60] if r.get("llm_mvp_idea") else ""

        verdict_display = {
            "strong_candidate": "⭐ 强候选",
            "niche_candidate": "🔍 小众机会",
            "service_opportunity": "🛠 服务机会",
            "plugin_opportunity": "🔌 插件机会",
            "weak_candidate": "⚠ 弱候选",
            "avoid": "❌ 避开",
        }.get(r.get("opportunity_verdict", ""), r.get("opportunity_verdict", ""))

        table_data.append({
            "排名": i,
            "仓库": r["full_name"],
            "Stars": r.get("stars", 0),
            "+/周": delta if delta else "",
            "Issues": r.get("open_issues_count", 0),
            "语言": r.get("language", ""),
            "数据质量": f"{r.get('data_quality_score', 0)} ({r.get('data_quality_label', '')})",
            "决策": verdict_display,
            "热度": r.get("hot_score", 0),
            "需求": r.get("issue_score", 0),
            "早期度": r.get("early_score", 0),
            "商业空白": r.get("commercial_gap_score", 0),
            "可行性": r.get("mvp_feasibility_score", 0),
            "总分": r.get("opportunity_score", 0),
            "推荐": RECOMMENDATION_MAP_CN.get(r.get("final_recommendation", ""), r.get("final_recommendation", "")),
            "LLM 摘要": llm_summary,
            "LLM MVP": llm_mvp,
            "LLM 状态": "成功" if llm_status == "success" else ("失败" if llm_status == "failed" else ""),
            "URL": r.get("url", ""),
        })

    df = pd.DataFrame(table_data)

    parts = [f"## 扫描完成：{len(results)} 个仓库"]
    parts.append(f"关键词：{keywords_str}")
    dq_high = sum(1 for r in results if r.get("data_quality_label") == "high")
    dq_med = sum(1 for r in results if r.get("data_quality_label") == "medium")
    dq_low = sum(1 for r in results if r.get("data_quality_label") == "low")
    parts.append(f"数据质量：{dq_high} 高 / {dq_med} 中 / {dq_low} 低")
    verdict_counts = {}
    for r in results:
        v = r.get("opportunity_verdict", "")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    if verdict_counts:
        parts.append("决策分布：" + " / ".join(f"{k}: {v}" for k, v in verdict_counts.items()))
    if llm_mode == "disabled":
        parts.append("LLM：未启用")
    elif llm_mode == "unavailable":
        parts.append("LLM：不可用，使用规则分析")
    else:
        parts.append(f"LLM：{llm_provider} / {llm_model}")
    parts.append("")
    parts.append("### 前 5 名")
    for i, r in enumerate(results[:5], 1):
        delta = f" (+{r.get('stars_delta_7d')}/周)" if r.get("stars_delta_7d") else ""
        verdict_display = {
            "strong_candidate": "⭐",
            "niche_candidate": "🔍",
            "service_opportunity": "🛠",
            "plugin_opportunity": "🔌",
            "weak_candidate": "⚠",
            "avoid": "❌",
        }.get(r.get("opportunity_verdict", ""), "")
        dq_score = r.get("data_quality_score", 0)
        parts.append(
            f"**{i}. [{r['full_name']}]({r.get('url', '#')})"
            f"** 总分：{r['opportunity_score']}/100 | DQ：{dq_score} | {verdict_display} {r.get('opportunity_verdict', '')}{delta}"
        )
        parts.append(f"_ {r.get('description', '')[:120]}")
        mvp_text = r.get("llm_mvp_idea") or r.get("recommended_mvp_idea", "")
        parts.append(f"MVP：{mvp_text}")
        parts.append("")

    summary_md = "\n".join(parts)
    return df, summary_md, csv_path, None


def view_repo_detail(evt: gr.SelectData | None = None):
    if evt is None:
        return _("err_no_selection")
    try:
        row_idx = evt.index[0]
    except (IndexError, TypeError):
        return _("err_select_row")

    runs = get_latest_scan_runs(limit=1)
    if not runs:
        return _("err_no_scan_data")
    repos = get_repos_for_scan(runs[0]["id"])
    if not repos or row_idx >= len(repos):
        return _("err_no_selection")
    repo = repos[row_idx]
    repo_name = repo.get("full_name", "")

    sid = repo.get("id", 0)
    issues = []
    if sid:
        issues = get_issues_for_snapshot(sid)

    dq_score = repo.get("data_quality_score", 0)
    dq_label = repo.get("data_quality_label", "未知")
    dq_reasons = repo.get("data_quality_reasons", [])
    dq_color = "#10b981" if dq_label == "high" else ("#f59e0b" if dq_label == "medium" else "#ef4444")
    verdict = repo.get("opportunity_verdict", "")
    verdict_reason = repo.get("verdict_reason", "")
    final_rec = repo.get("final_recommendation", "")
    llm_status = repo.get("llm_status", "")

    verdict_display = {
        "strong_candidate": "⭐ 强候选",
        "niche_candidate": "🔍 小众机会",
        "service_opportunity": "🛠 服务机会",
        "plugin_opportunity": "🔌 插件机会",
        "weak_candidate": "⚠ 弱候选",
        "avoid": "❌ 避开",
    }.get(verdict, verdict)

    delta_str = f" +{repo.get('stars_delta_7d')}/周" if repo.get("stars_delta_7d") else ""

    lines = [
        f"# {repo['full_name']}{delta_str}",
        "",
        f"[在 GitHub 上查看]({repo.get('url', '')}) | "
        f"**Stars**：{repo.get('stars', 0)} | "
        f"**Forks**：{repo.get('forks', 0)} | "
        f"**Issues**：{repo.get('open_issues_count', 0)}",
        f"**语言**：{repo.get('language', 'N/A')} | "
        f"**许可证**：{repo.get('license_name', 'N/A')} | "
        f"**描述**：{repo.get('description', '')[:200]}",
        "",
        "---",
        "",
    ]

    lines.append(f"## 决策：{verdict_display}")
    lines.append("")
    lines.append(f"**最终建议**：{final_rec}")
    if verdict_reason:
        lines.append(f"**理由**：{verdict_reason}")
    lines.append("")

    lines.append(_score_bar("数据质量评分", dq_score, 100, dq_color))
    lines.append("")
    if dq_reasons:
        reasons_str = " | ".join(dq_reasons)
        lines.append(f"_ {reasons_str} _")
        lines.append("")

    lines.append("## 规则评分")
    lines.append("")
    score_map = [
        ("热度（近期增长）", "hot_score", 25, "#ef4444"),
        ("Issue 需求强度", "issue_score", 25, "#f59e0b"),
        ("早期阶段", "early_score", 20, "#10b981"),
        ("商业空白", "commercial_gap_score", 20, "#3b82f6"),
        ("MVP 可行性", "mvp_feasibility_score", 10, "#8b5cf6"),
    ]
    for label, key, mx, color in score_map:
        val = repo.get(key, 0)
        lines.append(_score_bar(label, val, mx, color))
    lines.append("")
    lines.append(_score_bar("总分", repo.get("opportunity_score", 0), 100, "#4f46e5"))
    lines.append("")

    # Forecast panel
    lines.append("## 趋势预测 (v0.5 Forecast Layer)")
    lines.append("")
    repo_name = repo.get("full_name", "")
    import os as _os
    from src.forecast.models import SeriesBatch
    from src.forecast.features import compute_forecast_features, compute_forecast_signal
    from src.forecast.database import get_historical_metrics, get_latest_forecasts
    import sqlite3 as _sqlite3

    _enable_tfm = _os.environ.get("ENABLE_TIMESFM", "").lower() in ("true", "1", "yes")
    if _enable_tfm:
        from src.forecast.timesfm_adapter import TimesFMAdapter
        _adapter = TimesFMAdapter()
        _adapter_name_display = "TimesFM"
    else:
        from src.forecast.baseline import BaselineForecastAdapter
        _adapter = BaselineForecastAdapter()
        _adapter_name_display = "Baseline"

    _conn_f = _sqlite3.connect(str(Path(__file__).parent.parent / "data" / "radar.sqlite"))
    _conn_f.row_factory = _sqlite3.Row
    _ts, _vs = get_historical_metrics(_conn_f, "repo", repo_name, "stars_count", limit=60)
    if _ts:
        _batch = SeriesBatch("repo", repo_name, "stars_count", _ts, _vs)
        _fresults = _adapter.forecast([_batch], horizon=30)
        _features = compute_forecast_features([_batch], _fresults)
        _signal = compute_forecast_signal(_features)

        _label_cn = {
            "heating_up": "🔥 热度上升",
            "cooling_down": "❄ 热度下降",
            "stable": "✅ 稳定",
            "noisy": "⚠ 波动较大",
            "insufficient_data": "📭 数据不足",
        }

        def _sparkline(vals, width=20):
            if not vals:
                return ""
            mn, mx = min(vals), max(vals)
            rng = mx - mn if mx != mn else 1
            blocks = "▁▂▃▄▅▆▇█"
            step = len(vals) / max(width, 1)
            sampled = [vals[int(i * step)] for i in range(min(width, len(vals)))]
            bars = [blocks[min(int((v - mn) / rng * (len(blocks) - 1)), len(blocks) - 1)] for v in sampled]
            return "`" + "".join(bars) + "`"

        _adapter_tag = "🤖 TimesFM" if _enable_tfm else "📐 Baseline"
        if _fresults and _fresults[0].was_fallback:
            _adapter_tag += " → Baseline (降级)"
        hist_spark = _sparkline(_vs)
        fc_spark = _sparkline(_fresults[0].point_forecast[:14]) if _fresults else ""
        lines.append(f'**趋势标签**：{_label_cn.get(_features.trend_label.value, _features.trend_label.value)}')
        lines.append(f'**预测置信度**：{int(_features.forecast_confidence * 100)}%')
        lines.append(f'**预测增速**：7d={_features.forecast_growth_7d:+.1f}% | 14d={_features.forecast_growth_14d:+.1f}% | 30d={_features.forecast_growth_30d:+.1f}%')
        if _features.forecast_acceleration != 0:
            lines.append(f'**加速度**：{_features.forecast_acceleration:+.2f}')
        lines.append(f'**Signal Score**：{_signal.forecast_signal_score:.0f}/100')
        lines.append(f'**模型**：{_adapter_tag}')
        if hist_spark:
            lines.append(f'**历史趋势**：{hist_spark}')
        if fc_spark:
            lines.append(f'**预测趋势(14d)**：{fc_spark}')
        lines.append(f'**说明**：{_features.explanation}')
    else:
        lines.append("暂无可用的历史 Stars 数据。运行扫描积累数据后，趋势预测将自动生效。")
    _conn_f.close()
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 核心痛点")
    lines.append("")
    top_cluster_name = repo.get("top_pain_cluster_name", "")
    top_cluster_count = repo.get("top_pain_cluster_count", 0)
    evidence = repo.get("pain_cluster_evidence", [])
    monetization_hint = repo.get("pain_cluster_monetization_hint", "")
    if top_cluster_name:
        lines.append(f"**{top_cluster_name}**（{top_cluster_count} 条 Issue）")
    if evidence:
        lines.append("痛点证据：")
        for e in evidence[:5]:
            lines.append(f"- {e}")
    lines.append("")
    if monetization_hint:
        lines.append(f"**变现路径**：{monetization_hint}")
    lines.append("")
    cat_summary = repo.get("category_summary", {})
    if cat_summary:
        max_count = max(cat_summary.values()) or 1
        for k, v in cat_summary.items():
            pct = v / max_count * 100
            lines.append(
                f'<div class="pain-bar">'
                f'<span class="pain-label">{k}</span>'
                f'<div style="flex:1;background:#f3f4f6;border-radius:5px;height:10px">'
                f'<div class="pain-fill" style="width:{pct}%"></div>'
                f'</div>'
                f'<span style="min-width:30px;font-size:0.85em">{v}</span>'
                f'</div>'
            )
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## README 信号")
    lines.append("")
    early = repo.get("readme_early_signals", [])[:8]
    commercial = repo.get("readme_commercial_signals", [])[:8]
    if early:
        tags = " ".join(f'<span class="tag tag-early">{s}</span>' for s in early)
        lines.append(f"**早期信号**：{tags}")
    if commercial:
        tags = " ".join(f'<span class="tag tag-commercial">{s}</span>' for s in commercial)
        lines.append(f"**商业化信号**：{tags}")
    if not early and not commercial:
        lines.append("未检测到 README 信号。")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 为什么可能是机会")
    lines.append("")
    why_opp = repo.get("why_opportunity", "")
    if why_opp:
        for p in why_opp.split("\n\n"):
            lines.append(p)
            lines.append("")
    else:
        lines.append("暂无充足数据。")
    lines.append("---")
    lines.append("")

    lines.append("## 为什么可能不值得做")
    lines.append("")
    why_not = repo.get("why_not_worth", "")
    if why_not:
        for p in why_not.split("\n\n"):
            lines.append(p)
            lines.append("")
    else:
        lines.append("暂无充足数据。")
    lines.append("---")
    lines.append("")

    lines.append(f"## 规则推荐 MVP")
    lines.append("")
    lines.append(f"**{repo.get('recommended_mvp_idea', 'N/A')}**")
    lines.append(f"适合：{repo.get('best_for', 'N/A')} | 类型：{repo.get('mvp_type', 'N/A')}")
    lines.append("")

    lines.append("## 7 天 MVP 验证计划")
    lines.append("")
    plan = repo.get("seven_day_mvp_plan", [])
    if plan:
        for step in plan:
            lines.append(f"- {step}")
        lines.append("")
    lines.append("## 排名诊断")
    lines.append("")
    flags = repo.get("ranking_flags", [])
    if flags:
        for f in flags:
            f_labels = {
                "score_may_be_unreliable": "⚠️ 分数可能不可靠（高分低数据质量）",
                "commercial_risk": "⚠️ 存在商业化风险（高商业化信号）",
                "weak_issue_evidence": "⚠️ Issue 需求证据不足（少 issue 高分数）",
                "hype_without_pain": "🔥 热度虚高（有热度无痛点）",
                "niche_but_painful": "🎯 小而痛（痛点强但热度低）",
                "service_first": "🛠 服务优先（安装/文档类痛点集中）",
                "plugin_first": "🔌 插件优先（工作流/API 类痛点集中）",
            }
            lines.append(f"- {f_labels.get(f, f)}")
        warn = repo.get("ranking_warning", "")
        if warn:
            lines.append(f"**预警**：{warn}")
        next_action = repo.get("suggested_next_action", "")
        if next_action:
            lines.append(f"**建议行为**：{next_action}")
    else:
        lines.append("未检测到异常信号。")
    lines.append("")
    lines.append("---")
    lines.append("")

    if llm_status == "success":
        lines.append('<div class="llm-section">')
        lines.append("<h2>LLM 增强分析</h2>")
        lines.append("")

        summary = repo.get("llm_summary", "")
        if summary:
            lines.append(f"**一句话总结**：{summary}")
            lines.append("")

        pain_summary = repo.get("llm_user_pain_summary", "")
        if pain_summary:
            lines.append(f"**用户痛点总结**：{pain_summary}")
            lines.append("")

        pain_clusters = repo.get("llm_pain_clusters", [])
        if isinstance(pain_clusters, list) and pain_clusters:
            lines.append("**痛点聚类**：")
            lines.append("<ul>")
            for pc in pain_clusters:
                if isinstance(pc, dict):
                    name = pc.get("name", "")
                    sev = pc.get("severity", "")
                    mon = pc.get("monetization_potential", "")
                    evidence_items = pc.get("evidence_issue_titles", [])
                    lines.append(f"<li><strong>{name}</strong>"
                                 f"（严重度：{sev}，变现潜力：{mon}）")
                    if evidence_items:
                        lines.append("<ul>")
                        for t in evidence_items[:3]:
                            lines.append(f"<li>{t}</li>")
                        lines.append("</ul>")
                    lines.append("</li>")
            lines.append("</ul>")

        best_mvp = repo.get("llm_mvp_idea", "")
        if best_mvp:
            lines.append(f"**推荐 MVP**：{best_mvp}")
            lines.append("")

        customer = repo.get("llm_target_customer", "")
        if customer:
            lines.append(f"**目标客户**：{customer}")
            lines.append("")

        why_now = repo.get("llm_why_now", "")
        if why_now:
            lines.append(f"**为什么现在做**：{why_now}")
            lines.append("")

        monetization = repo.get("llm_monetization_angle", "")
        if monetization:
            lines.append(f"**变现角度**：{monetization}")
            lines.append("")

        latency = repo.get("latency_ms", 0)
        status_detail = repo.get("status_detail", "")
        if latency:
            lines.append(f"**延迟**：{latency}ms | **状态详情**：{status_detail}")
            lines.append("")

        difficulty = repo.get("llm_build_difficulty", "")
        if difficulty:
            lines.append(f"**开发难度**：{difficulty}")

        confidence = repo.get("llm_confidence", "")
        if confidence:
            lines.append(f"**置信度**：{confidence}")
        lines.append("")

        build_plan = repo.get("llm_build_plan", None)
        if isinstance(build_plan, list) and build_plan:
            lines.append("**7 天 MVP 开发计划**：")
            lines.append("<ol>")
            for step in build_plan:
                lines.append(f'<li class="plan-step">{step}</li>')
            lines.append("</ol>")

        risks = repo.get("llm_risks", None)
        if isinstance(risks, list) and risks:
            lines.append("**风险提醒**：")
            for risk in risks:
                lines.append(f'<span class="risk-tag">{risk}</span>')
            lines.append("")

        notes = repo.get("llm_notes", "")
        if notes:
            lines.append(f"**备注**：{notes}")

        lines.append("</div>")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Issues（前 5 条）")
    lines.append("")
    for iss in issues[:5]:
        labels = ", ".join(iss.get("labels", [])[:4])
        cat = CATEGORY_NAMES.get(iss.get("category", ""), iss.get("category", ""))
        lines.append(f"### [{iss['title']}]({iss.get('url', '#')})")
        lines.append(f"分类：{cat} | 评论：{iss.get('comments_count', 0)} | 标签：{labels}")
        lines.append("---")

    return "\n".join(lines)


def load_last_scan():
    runs = get_latest_scan_runs(limit=1)
    if not runs:
        return None, _("msg_no_last_scan"), None
    repos = get_repos_for_scan(runs[0]["id"])
    if not repos:
        return None, _("msg_no_repos_scan"), None

    table_data = []
    for i, r in enumerate(repos, 1):
        delta = r.get("stars_delta_7d")
        llm_status = r.get("llm_status", "")
        llm_summary = r.get("llm_summary", "")[:80] if r.get("llm_summary") else ""
        llm_mvp = r.get("llm_mvp_idea", "")[:60] if r.get("llm_mvp_idea") else ""
        dq_score = r.get("data_quality_score", 0)
        dq_label = r.get("data_quality_label", r.get("data_quality", ""))
        dq_display = f"{dq_score}/{dq_label}" if dq_label else str(dq_score)
        verdict = r.get("opportunity_verdict", "")
        verdict_display = {
            "strong_candidate": "⭐ 强候选",
            "niche_candidate": "🔍 小众机会",
            "service_opportunity": "🛠 服务机会",
            "plugin_opportunity": "🔌 插件机会",
            "weak_candidate": "⚠ 弱候选",
            "avoid": "❌ 避开",
        }.get(verdict, verdict)
        final_rec = RECOMMENDATION_MAP_CN.get(r.get("final_recommendation", ""), r.get("final_recommendation", ""))[:40]
        table_data.append({
            "排名": i,
            "仓库": r["full_name"],
            "Stars": r.get("stars", 0),
            "+/周": delta if delta else "",
            "Issues": r.get("open_issues_count", 0),
            "语言": r.get("language", ""),
            "数据质量": dq_display,
            "决策": verdict_display,
            "热度": r.get("hot_score", 0),
            "需求": r.get("issue_score", 0),
            "早期度": r.get("early_score", 0),
            "商业空白": r.get("commercial_gap_score", 0),
            "可行性": r.get("mvp_feasibility_score", 0),
            "总分": r.get("opportunity_score", 0),
            "推荐": final_rec,
            "LLM 摘要": llm_summary,
            "LLM MVP": llm_mvp,
            "LLM 状态": "成功" if llm_status == "success" else ("失败" if llm_status == "failed" else ""),
            "URL": r.get("url", ""),
        })
    return pd.DataFrame(table_data), _("msg_scan_loaded", len(repos)), None


def get_latest_file(ext):
    import glob
    from src.config import OUTPUTS_DIR
    files = sorted(glob.glob(str(OUTPUTS_DIR / f"*{ext}")))
    return files[-1] if files else None


def add_to_watchlist_ui(repo_name, note):
    if not repo_name:
        return _("err_wl_no_input")
    rid = get_repo_id_by_name(repo_name)
    if not rid:
        return _("err_repo_not_in_db", repo_name)
    ok = add_to_watchlist(rid, note)
    return _("msg_wl_added", repo_name) if ok else _("msg_wl_add_fail")


def remove_from_watchlist_ui(repo_name):
    if not repo_name:
        return _("err_wl_no_input")
    rid = get_repo_id_by_name(repo_name)
    if not rid:
        return _("err_repo_not_found", repo_name)
    remove_from_watchlist(rid)
    return _("msg_wl_removed", repo_name)


def update_review_fields_ui(repo_name, hypothesis, target_user, monetization, next_step, validation_result):
    if not repo_name:
        return _("err_wl_no_input")
    rid = get_repo_id_by_name(repo_name)
    if not rid:
        return _("err_repo_not_found", repo_name)
    update_watchlist_review_fields(
        rid,
        user_hypothesis=hypothesis or None,
        target_user_guess=target_user or None,
        monetization_guess=monetization or None,
        validation_next_step=next_step or None,
        validation_result=validation_result or None,
    )
    return _("msg_wl_updated", repo_name)


def load_watchlist_data():
    runs = get_latest_scan_runs(limit=1)
    scan_run_id = runs[0]["id"] if runs else None
    wl = get_watchlist(scan_run_id=scan_run_id, compute_deltas=True)
    if not wl:
        return None, _("msg_wl_empty")
    rows = []
    for w in wl:
        rec_key = w.get("final_recommendation", "")
        rows.append([
            w.get("full_name", ""),
            w.get("status", ""),
            w.get("opportunity_score", "N/A"),
            w.get("data_quality_score", "N/A"),
            w.get("opportunity_verdict", ""),
            RECOMMENDATION_MAP_CN.get(rec_key, rec_key),
            w.get("user_rating", 0),
            w.get("stars_delta_7d", ""),
            w.get("stars_delta_since_first_seen", ""),
            "⚠" if w.get("needs_review") else "",
        ])
    headers = [_("wl_col_repo"), _("wl_col_status"), _("wl_col_score"), _("wl_col_dq"), _("wl_col_verdict"), _("wl_col_rec"), _("wl_col_rating"), _("wl_col_weekly"), _("wl_col_total_delta"), _("wl_col_review")]
    return rows, _("msg_wl_loaded", len(wl))


def export_watchlist_ui():
    runs = get_latest_scan_runs(limit=1)
    scan_run_id = runs[0]["id"] if runs else None
    wl = get_watchlist(scan_run_id=scan_run_id, compute_deltas=True)
    if not wl:
        return _("msg_wl_empty_export")
    path = export_watchlist_report(wl)
    return _("msg_wl_exported", path)


def run_webui(debug=False, port=7860):
    init_db()

    with gr.Blocks(
        title="GitHub 创业机会雷达",
        theme=gr.themes.Soft(
            primary_hue="indigo",
            neutral_hue="slate",
            font=gr.themes.GoogleFont("Inter"),
        ),
        css=CUSTOM_CSS,
    ) as demo:
        with gr.Row():
            lang_dropdown = gr.Dropdown(
                choices=[("中文", "zh"), ("English", "en")],
                value=LANG, label=_("lang_switch"), scale=0, min_width=120
            )
        gr.HTML(
            f'<div style="padding:16px 0">'
            f'<h1 style="margin:0;font-size:1.8em;font-weight:700">{_("header_title")}</h1>'
            f'<p style="margin:4px 0 0;color:#6b7280">'
            f'{_("header_subtitle")}</p>'
            f"</div>"
        )

        def set_lang_global(lang):
            global LANG
            LANG = lang
            import os
            os.environ["OPENCODE_LANG"] = lang

        lang_dropdown.change(
            fn=set_lang_global,
            inputs=[lang_dropdown],
            js="() => window.location.reload()",
        )

        with gr.Accordion(_("accordion_scan"), open=False):
            with gr.Row():
                with gr.Column(scale=2):
                    keywords_input = gr.Textbox(
                        label=_("keywords"),
                        value=DEFAULT_KEYWORDS_STR,
                        lines=1,
                    )
                with gr.Column(scale=1):
                    target_count_input = gr.Number(
                        label=_("target_repos"), value=15, minimum=5, maximum=50
                    )

            with gr.Row():
                min_stars_input = gr.Number(label=_("min_stars"), value=100, minimum=0)
                max_stars_input = gr.Number(label=_("max_stars"), value=50000, minimum=0)
                min_issues_input = gr.Number(label=_("min_issues"), value=5, minimum=0)
                max_issues_input = gr.Number(label=_("max_issues"), value=20, minimum=5, maximum=50)

            with gr.Row():
                trending_period_input = gr.Dropdown(
                    label=_("trending_period"),
                    choices=[(_("trending_daily"), "daily"), (_("trending_weekly"), "weekly"), (_("trending_monthly"), "monthly"), (_("trending_all"), "all")],
                    value="weekly",
                )
                request_delay_input = gr.Slider(
                    label=_("request_delay"), minimum=0.5, maximum=5.0, value=2.0, step=0.5
                )

            with gr.Row():
                enable_readme_input = gr.Checkbox(label=_("enable_readme"), value=True)
                enable_search_input = gr.Checkbox(label=_("enable_search"), value=True)
                exclude_commercial_input = gr.Checkbox(label=_("exclude_commercial"), value=True)

        with gr.Accordion(_("accordion_llm"), open=False):
            gr.Markdown(_("llm_hint"))
            with gr.Row():
                enable_llm_input = gr.Checkbox(label=_("enable_llm"), value=False)
                llm_provider_input = gr.Dropdown(
                    label=_("llm_provider"),
                    choices=[(_("provider_none"), "none"), (_("provider_ollama"), "ollama"), (_("provider_openai"), "openai_compatible"), (_("provider_litellm"), "litellm_proxy")],
                    value="none",
                )
            with gr.Row():
                llm_base_url_input = gr.Textbox(
                    label=_("base_url"), value="http://localhost:11434",
                    placeholder="http://localhost:11434",
                )
                llm_model_input = gr.Textbox(
                    label=_("model"), value="qwen2.5:14b",
                    placeholder="qwen2.5:14b",
                )
            with gr.Row():
                llm_api_key_input = gr.Textbox(
                    label=_("api_key"), type="password", value="",
                    placeholder=_("api_key_ph"),
                )
                llm_max_tokens_input = gr.Number(
                    label=_("max_tokens"), value=1200, minimum=256, maximum=4096
                )
            with gr.Row():
                llm_temperature_input = gr.Slider(
                    label=_("temperature"), minimum=0.0, maximum=1.0, value=0.2, step=0.1
                )
                llm_language_input = gr.Dropdown(
                    label=_("output_lang"), choices=[(_("output_lang_zh"), "zh"), (_("output_lang_en"), "en")], value="zh"
                )
                llm_max_repos_input = gr.Number(
                    label=_("max_llm_repos"), value=10, minimum=1, maximum=30
                )
                llm_timeout_input = gr.Number(
                    label=_("timeout"), value=300, minimum=30, maximum=600
                )
            with gr.Row():
                llm_json_schema_input = gr.Checkbox(
                    label=_("json_schema_strict"), value=False
                )
                llm_force_json_input = gr.Checkbox(
                    label=_("force_json_mode"), value=False
                )
                llm_cache_input = gr.Checkbox(
                    label=_("enable_llm_cache"), value=True
                )
            with gr.Row():
                llm_test_btn = gr.Button(_("test_llm_conn"), variant="secondary", size="sm")
                llm_preload_btn = gr.Button(_("preload_ollama"), variant="secondary", size="sm")
            llm_test_result = gr.Markdown("")

        def test_llm_connection(provider, base_url, model, api_key, temperature, max_tokens, timeout, use_schema, force_json):
            cfg = LLMConfig(
                provider=provider, base_url=base_url, model=model,
                api_key=api_key, temperature=temperature, max_tokens=max_tokens,
                timeout=timeout, use_json_schema=use_schema, force_json_mode=force_json,
            )
            result = test_connection(cfg)
            lines = [f"**状态**: {result['status']}", f"**详情**: {result.get('detail', '')}"]
            if result.get("status") == "ok":
                client = create_client(cfg)
                if client:
                    import time
                    start = time.time()
                    chat_result = client.chat_json(LLM_TEST_PROMPT, "", None)
                    elapsed = time.time() - start
                    lines.append(f"**Ping 延迟**: {elapsed:.1f}s")
                    lines.append(f"**JSON 策略**: {chat_result.json_mode_used}")
                    if chat_result.success:
                        lines.append("**测试结果**: ✅ 成功")
                    else:
                        lines.append("**测试结果**: ❌ 失败")
            return "\n".join(lines)

        def preload_ollama(base_url, model):
            client = create_client(LLMConfig(provider="ollama", base_url=base_url, model=model))
            if client and hasattr(client, "preload"):
                ok = client.preload()
                return _("msg_preload_ok") if ok else _("msg_preload_fail")
            return _("msg_no_preload")

        llm_test_btn.click(
            fn=test_llm_connection,
            inputs=[llm_provider_input, llm_base_url_input, llm_model_input,
                    llm_api_key_input, llm_temperature_input, llm_max_tokens_input,
                    llm_timeout_input, llm_json_schema_input, llm_force_json_input],
            outputs=[llm_test_result],
        )

        llm_preload_btn.click(
            fn=preload_ollama,
            inputs=[llm_base_url_input, llm_model_input],
            outputs=[llm_test_result],
        )

        scan_btn = gr.Button(_("btn_scan"), variant="primary", size="lg")
        load_btn = gr.Button(_("btn_load"), variant="secondary")

        gr.Markdown(_("scan_hint"))

        summary_out = gr.Markdown(label=_("summary_label"))
        result_df = gr.Dataframe(
            label=_("results_label"),
            headers=[
                _("col_rank"), _("col_repo"), _("col_stars"), _("col_weekly"), _("col_issues"), _("col_lang"),
                _("col_data_quality"), _("col_verdict"), _("col_hot"), _("col_demand"), _("col_early"), _("col_gap"), _("col_feasibility"),
                _("col_total"), _("col_rec"), _("col_llm_summary"), _("col_llm_mvp"), _("col_llm_status"), _("col_url")
            ],
            wrap=True,
            column_widths=[
                "40px", "160px", "50px", "45px", "40px", "40px",
                "60px", "80px", "30px", "30px", "30px", "30px", "30px",
                "45px", "90px", "120px", "120px", "40px", "160px"
            ],
        )

        with gr.Row():
            csv_out = gr.File(label=_("export_csv"))
            json_out = gr.File(label=_("export_json"))
            md_out = gr.File(label=_("export_md"))

        detail_out = gr.Markdown(label=_("detail_label"), elem_classes="detail-markdown")

        gr.Markdown("---")
        with gr.Row():
            wl_repo_input = gr.Textbox(label=_("wl_repo_label"), scale=2, placeholder=_("wl_repo_ph"))
            wl_note_input = gr.Textbox(label=_("wl_note_label"), scale=1)
        with gr.Row():
            wl_add_btn = gr.Button(_("wl_add_btn"), variant="primary", size="sm")
            wl_remove_btn = gr.Button(_("wl_remove_btn"), variant="secondary", size="sm")
            wl_load_btn = gr.Button(_("wl_load_btn"), variant="secondary", size="sm")
            wl_export_btn = gr.Button(_("wl_export_btn"), variant="secondary", size="sm")
        wl_status = gr.Markdown("")
        wl_table = gr.Dataframe(label=_("wl_table_label"), headers=[_("wl_col_repo"), _("wl_col_status"), _("wl_col_score"), _("wl_col_dq"), _("wl_col_verdict"), _("wl_col_rec"), _("wl_col_rating"), _("wl_col_weekly"), _("wl_col_total_delta"), _("wl_col_review")])
        gr.Markdown(f"### {_('wl_review_title')}")
        with gr.Row():
            wl_hypothesis = gr.Textbox(label=_("wl_hypothesis"), lines=2)
            wl_target_user = gr.Textbox(label=_("wl_target_user"), lines=2)
        with gr.Row():
            wl_monetization = gr.Textbox(label=_("wl_monetization"), lines=2)
            wl_next_step = gr.Textbox(label=_("wl_next_step"), lines=2)
        with gr.Row():
            wl_validation_result = gr.Textbox(label=_("wl_validation"), lines=2)
        wl_update_btn = gr.Button(_("wl_update_btn"), variant="primary", size="sm")
        wl_update_status = gr.Markdown("")

        def run_and_refresh(*args):
            print(f"  [WebUI] Starting scan (JSON Schema: {args[-3]}, Timeout: {args[-2]}, Cache: {args[-1]})")
            df, summary, csv_path, detail = run_scan_ui(*args)
            json_path = get_latest_file(".json")
            md_path = get_latest_file(".md")
            return df, summary, str(csv_path) if csv_path else None, \
                str(json_path) if json_path else None, \
                str(md_path) if md_path else None, detail

        scan_btn.click(
            fn=run_and_refresh,
            inputs=[
                keywords_input, target_count_input,
                min_stars_input, max_stars_input,
                min_issues_input, max_issues_input,
                trending_period_input, request_delay_input,
                enable_readme_input, enable_search_input,
                exclude_commercial_input,
                enable_llm_input, llm_provider_input,
                llm_base_url_input, llm_model_input,
                llm_api_key_input, llm_temperature_input,
                llm_max_tokens_input, llm_language_input,
                llm_max_repos_input, llm_json_schema_input,
                llm_force_json_input, llm_timeout_input, llm_cache_input,
            ],
            outputs=[result_df, summary_out, csv_out, json_out, md_out, detail_out],
        )

        load_btn.click(
            fn=load_last_scan,
            outputs=[result_df, summary_out, csv_out],
        )

        result_df.select(
            fn=view_repo_detail,
            outputs=[detail_out],
        )

        wl_add_btn.click(
            fn=add_to_watchlist_ui,
            inputs=[wl_repo_input, wl_note_input],
            outputs=[wl_status],
        )
        wl_remove_btn.click(
            fn=remove_from_watchlist_ui,
            inputs=[wl_repo_input],
            outputs=[wl_status],
        )
        wl_load_btn.click(
            fn=load_watchlist_data,
            outputs=[wl_table, wl_status],
        )
        wl_export_btn.click(
            fn=export_watchlist_ui,
            outputs=[wl_status],
        )
        wl_update_btn.click(
            fn=update_review_fields_ui,
            inputs=[wl_repo_input, wl_hypothesis, wl_target_user, wl_monetization, wl_next_step, wl_validation_result],
            outputs=[wl_update_status],
        )

        gr.Markdown("---")
        gr.Markdown(f"## {_('val_title')}")
        gr.Markdown(_("val_desc"))
        with gr.Row():
            val_repo_input = gr.Textbox(
                label=_("val_repo_label"), scale=2,
                placeholder=_("val_repo_ph")
            )
        with gr.Row():
            val_llm_checkbox = gr.Checkbox(label=_("val_llm_label"), value=False)
            val_gen_btn = gr.Button(_("val_gen_btn"), variant="primary", size="lg")
        val_output = gr.Markdown("")
        with gr.Row():
            val_brief = gr.Markdown(label=_("val_brief"))
            val_mvp = gr.Markdown(label=_("val_mvp"))
        with gr.Row():
            val_replies = gr.Markdown(label=_("val_replies"))
            val_launch = gr.Markdown(label=_("val_launch"))

        def generate_val_pack(repo_name, enable_llm):
            if not repo_name:
                return _("err_val_repo_ph"), "", "", "", ""
            from src.repo_page_scraper import scrape_issues_direct
            from src.validation_pack import generate_validation_pack
            issues = scrape_issues_direct(repo_name, max_count=10)
            llm_config = None
            if enable_llm and settings.llm_provider != "none":
                llm_config = LLMConfig(
                    provider=settings.llm_provider,
                    base_url=settings.llm_base_url,
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                )
            out_dir, files = generate_validation_pack(
                repo_name, issues=issues, llm_config=llm_config
            )
            brief_md = ""
            mvp_md = ""
            replies_md = ""
            launch_md = ""
            for f in files:
                content = f.read_text(encoding="utf-8")[:2000]
                name = f.name
                if name == "opportunity_brief.md":
                    brief_md = content
                elif name == "mvp_scope.md":
                    mvp_md = content
                elif name == "issue_reply_drafts.md":
                    replies_md = content
                elif name == "launch_post_drafts.md":
                    launch_md = content
            return (_("msg_val_generated", out_dir, len(files)),
                    brief_md, mvp_md, replies_md, launch_md)

        val_gen_btn.click(
            fn=generate_val_pack,
            inputs=[val_repo_input, val_llm_checkbox],
            outputs=[val_output, val_brief, val_mvp, val_replies, val_launch],
        )

        gr.Markdown("---")
        gr.Markdown(f"## {_('mvp_title')}")
        gr.Markdown(_("mvp_desc"))
        with gr.Row():
            mvp_repo_input = gr.Textbox(
                label=_("mvp_repo_label"), scale=2,
                placeholder=_("mvp_repo_ph")
            )
        with gr.Row():
            mvp_type_input = gr.Dropdown(
                label=_("mvp_type_label"),
                choices=[(_("mvp_type_auto"), "auto"),
                         ("one_click_installer", "one_click_installer"),
                         ("webui", "webui"),
                         ("plugin", "plugin"),
                         ("mcp_server", "mcp_server"),
                         ("chrome_extension", "chrome_extension"),
                         ("deployment_template", "deployment_template"),
                         ("tutorial_pack", "tutorial_pack")],
                value="auto",
            )
        with gr.Row():
            mvp_llm_checkbox = gr.Checkbox(label=_("mvp_llm_label"), value=False)
            mvp_gen_btn = gr.Button(_("mvp_gen_btn"), variant="primary", size="lg")
        mvp_output = gr.Markdown("")
        with gr.Row():
            mvp_brief_preview = gr.Markdown(label=_("mvp_brief_preview"))
            mvp_req_preview = gr.Markdown(label=_("mvp_req_preview"))
        with gr.Row():
            mvp_codex_preview = gr.Markdown(label=_("mvp_codex_preview"))
            mvp_landing_preview = gr.Markdown(label=_("mvp_landing_preview"))

        def generate_mvp_brief_ui(repo_name, mvp_type_val, enable_llm):
            if not repo_name:
                return _("err_mvp_repo_ph"), "", "", "", ""
            from src.mvp_brief_generator import generate_mvp_brief
            from src.database import get_repo_id_by_name
            rid = get_repo_id_by_name(repo_name)
            if not rid:
                return _("err_mvp_not_found", repo_name), "", "", "", ""
            from src.repo_page_scraper import scrape_issues_direct
            issues = scrape_issues_direct(repo_name, max_count=10)
            llm_config = None
            if enable_llm and settings.llm_provider != "none":
                from src.llm.base import LLMConfig
                llm_config = LLMConfig(
                    provider=settings.llm_provider,
                    base_url=settings.llm_base_url,
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                )
            out_dir, files = generate_mvp_brief(
                repo_name, mvp_type=mvp_type_val,
                llm_config=llm_config,
                issues=issues,
            )
            from src.database import save_mvp_brief
            save_mvp_brief(
                repo_id=rid, mvp_type=mvp_type_val,
                output_path=str(out_dir),
                used_llm=bool(llm_config and llm_config.provider != "none"),
                llm_provider=llm_config.provider if llm_config else None,
                llm_model=llm_config.model if llm_config else None,
            )
            brief_md = ""
            req_md = ""
            codex_md = ""
            landing_md = ""
            for f in files:
                content = f.read_text(encoding="utf-8")[:2000]
                name = f.name
                if name == "product_brief.md":
                    brief_md = content
                elif name == "mvp_requirements.md":
                    req_md = content
                elif name == "codex_prompt.md":
                    codex_md = content
                elif name == "landing_page.md":
                    landing_md = content
            return (_("msg_mvp_generated", out_dir, len(files)),
                    brief_md, req_md, codex_md, landing_md)

        mvp_gen_btn.click(
            fn=generate_mvp_brief_ui,
            inputs=[mvp_repo_input, mvp_type_input, mvp_llm_checkbox],
            outputs=[mvp_output, mvp_brief_preview, mvp_req_preview, mvp_codex_preview, mvp_landing_preview],
        )

        gr.Markdown("---")
        gr.Markdown(f"## {_('exp_title')}")
        gr.Markdown(_("exp_desc"))
        with gr.Row():
            exp_repo_input = gr.Textbox(label=_("exp_repo_label"), scale=2, placeholder=_("exp_repo_ph"))
            exp_name_input = gr.Textbox(label=_("exp_name_label"), scale=2, placeholder=_("exp_name_ph"))
        with gr.Row():
            exp_type_input = gr.Dropdown(
                label=_("exp_type_label"),
                choices=[("auto", "auto"), ("one_click_installer", "one_click_installer"),
                         ("webui", "webui"), ("plugin", "plugin"), ("mcp_server", "mcp_server"),
                         ("chrome_extension", "chrome_extension"),
                         ("deployment_template", "deployment_template"),
                         ("tutorial_pack", "tutorial_pack")],
                value="auto",
            )
            exp_priority_input = gr.Dropdown(
                label=_("exp_priority_label"),
                choices=[(_("exp_priority_high"), "high"), (_("exp_priority_medium"), "medium"), (_("exp_priority_low"), "low")],
                value="medium",
            )
        with gr.Row():
            exp_create_btn = gr.Button(_("exp_create_btn"), variant="primary", size="sm")
            exp_load_btn = gr.Button(_("exp_load_btn"), variant="secondary", size="sm")
            exp_dash_btn = gr.Button(_("exp_dash_btn"), variant="secondary", size="sm")
        exp_status = gr.Markdown("")
        exp_table = gr.Dataframe(label=_("exp_table_label"),
            headers=[_("exp_col_id"), _("exp_col_repo"), _("exp_col_name"), _("exp_col_type"), _("exp_col_status"), _("exp_col_priority"), _("exp_col_decision"),
                     _("exp_col_outreach"), _("exp_col_interested"), _("exp_col_paid"), _("exp_col_updated")])
        gr.Markdown(f"### {_('exp_edit_title')}")
        with gr.Row():
            exp_edit_id = gr.Number(label=_("exp_edit_id"), precision=0)
            exp_edit_status = gr.Dropdown(
                label=_("exp_edit_status"),
                choices=["planned", "brief_generated", "building", "demo_ready",
                         "validating", "paused", "killed", "shipped"],
                value="planned",
            )
            exp_edit_decision = gr.Dropdown(
                label=_("exp_edit_decision"),
                choices=["continue", "pivot", "pause", "kill", "ship", "unknown"],
                value="unknown",
            )
        with gr.Row():
            exp_edit_demo_url = gr.Textbox(label=_("exp_demo_url"), placeholder="https://")
            exp_edit_github_url = gr.Textbox(label=_("exp_github_url"), placeholder="https://")
            exp_edit_landing_url = gr.Textbox(label=_("exp_landing_url"), placeholder="https://")
        with gr.Row():
            exp_edit_target_user = gr.Textbox(label=_("exp_target_user"), placeholder=_("exp_target_user_ph"))
            exp_edit_hypothesis = gr.Textbox(label=_("exp_hypothesis"), placeholder=_("exp_hypothesis_ph"))
            exp_edit_success = gr.Textbox(label=_("exp_success"), placeholder=_("exp_success_ph"))
        with gr.Row():
            exp_edit_outreach = gr.Number(label=_("exp_outreach_count"), precision=0, value=0)
            exp_edit_replies = gr.Number(label=_("exp_reply_count"), precision=0, value=0)
            exp_edit_interested = gr.Number(label=_("exp_interested_count"), precision=0, value=0)
        with gr.Row():
            exp_edit_waitlist = gr.Number(label=_("exp_waitlist_count"), precision=0, value=0)
            exp_edit_paid = gr.Number(label=_("exp_paid_count"), precision=0, value=0)
            exp_edit_revenue = gr.Number(label=_("exp_revenue"), value=0)
        with gr.Row():
            exp_edit_notes = gr.Textbox(label=_("exp_notes"), lines=2)
            exp_edit_channel = gr.Textbox(label=_("exp_channel"), placeholder=_("exp_channel_ph"))
        with gr.Row():
            exp_save_btn = gr.Button(_("exp_save_btn"), variant="primary", size="sm")
            exp_report_btn = gr.Button(_("exp_report_btn"), variant="secondary", size="sm")
            exp_codex_btn = gr.Button(_("exp_codex_btn"), variant="secondary", size="sm")
        exp_update_status = gr.Markdown("")

        def create_experiment_ui(repo_name, exp_name, mvp_type, priority):
            if not repo_name or not exp_name:
                return _("err_exp_repo_name")
            from src.database import get_repo_id_by_name, create_experiment
            rid = get_repo_id_by_name(repo_name)
            if not rid:
                return _("err_exp_repo_db", repo_name)
            from src.database import get_all_mvp_briefs
            from src.config import OUTPUTS_DIR
            val_pack_path = str(OUTPUTS_DIR / "validation_packs" / repo_name.replace("/", "__"))
            if not Path(val_pack_path).exists():
                val_pack_path = None
            mvp_brief_path = None
            codex_path = None
            for b in (get_all_mvp_briefs() or []):
                if b.get("full_name", "").lower() == repo_name.lower():
                    mvp_brief_path = b.get("output_path", "")
                    if mvp_brief_path:
                        cp = Path(mvp_brief_path) / "codex_prompt.md"
                        if cp.exists():
                            codex_path = str(cp)
                    break
            exp_id = create_experiment(
                repo_id=rid, repo_full_name=repo_name,
                experiment_name=exp_name, mvp_type=mvp_type,
                priority=priority,
                validation_pack_path=val_pack_path,
                mvp_brief_path=mvp_brief_path,
                codex_prompt_path=codex_path,
            )
            return _("msg_exp_created", exp_id, exp_name)

        def load_experiments_ui():
            from src.database import get_experiments
            exps = get_experiments(limit=50)
            if not exps:
                return [], _("msg_no_exps")
            rows = []
            for e in exps:
                rows.append([
                    e["id"], e.get("repo_full_name", ""),
                    (e.get("experiment_name", "") or "")[:30],
                    e.get("mvp_type", ""), e.get("status", ""),
                    e.get("priority", ""), e.get("decision", ""),
                    e.get("outreach_count", 0), e.get("interested_count", 0),
                    e.get("paid_count", 0),
                    (e.get("updated_at", "") or "")[:10],
                ])
            return rows, _("msg_exp_loaded", len(exps))

        def save_experiment_ui(exp_id, status, decision, demo_url, github_url, landing_url,
                               target_user, hypothesis, success_criteria,
                               outreach, replies, interested, waitlist, paid, revenue,
                               notes, channel):
            if not exp_id:
                return _("err_exp_id")
            from src.database import update_experiment
            updates = {
                "status": status, "decision": decision,
                "demo_url": demo_url or None, "github_repo_url": github_url or None,
                "landing_page_url": landing_url or None,
                "target_user": target_user or None, "hypothesis": hypothesis or None,
                "success_criteria": success_criteria or None,
                "outreach_count": int(outreach), "reply_count": int(replies),
                "interested_count": int(interested), "waitlist_count": int(waitlist),
                "paid_count": int(paid), "revenue_estimate": float(revenue),
                "notes": notes or None, "validation_channel": channel or None,
            }
            update_experiment(int(exp_id), **updates)
            return _("msg_exp_updated", exp_id)

        def gen_report_ui(exp_id):
            if not exp_id:
                return _("err_exp_id")
            from src.experiment_tracker import generate_experiment_report
            path = generate_experiment_report(int(exp_id))
            return _("msg_exp_report", path)

        def gen_codex_ui(exp_id):
            if not exp_id:
                return _("err_exp_id")
            from src.experiment_tracker import generate_codex_task
            path = generate_codex_task(int(exp_id))
            return _("msg_exp_codex", path)

        exp_create_btn.click(
            fn=create_experiment_ui,
            inputs=[exp_repo_input, exp_name_input, exp_type_input, exp_priority_input],
            outputs=[exp_status],
        )
        exp_load_btn.click(
            fn=load_experiments_ui,
            outputs=[exp_table, exp_status],
        )
        exp_save_btn.click(
            fn=save_experiment_ui,
            inputs=[exp_edit_id, exp_edit_status, exp_edit_decision,
                    exp_edit_demo_url, exp_edit_github_url, exp_edit_landing_url,
                    exp_edit_target_user, exp_edit_hypothesis, exp_edit_success,
                    exp_edit_outreach, exp_edit_replies, exp_edit_interested,
                    exp_edit_waitlist, exp_edit_paid, exp_edit_revenue,
                    exp_edit_notes, exp_edit_channel],
            outputs=[exp_update_status],
        )
        exp_report_btn.click(
            fn=gen_report_ui,
            inputs=[exp_edit_id],
            outputs=[exp_update_status],
        )
        exp_codex_btn.click(
            fn=gen_codex_ui,
            inputs=[exp_edit_id],
            outputs=[exp_update_status],
        )

    demo.queue()
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        share=False,
        debug=debug,
    )
