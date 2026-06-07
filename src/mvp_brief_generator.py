import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.config import OUTPUTS_DIR, settings
from src.database import get_repo_id_by_name, get_latest_score_for_repo
from src.database import get_issues_for_snapshot, get_last_two_snapshots
from src.database import get_watchlist_status, get_snapshot_history
from src.llm.base import LLMConfig
from src.llm.provider_router import create_client


def _sanitize_name(name):
    return name.replace("/", "__").replace("\\", "__")


def _get_issues_text(issues, max_count=15):
    lines = []
    for i, iss in enumerate((issues or [])[:max_count], 1):
        title = iss.get("title", "")
        labels = ", ".join(iss.get("labels", [])[:3])
        comments = iss.get("comments_count", 0)
        body = (iss.get("body", "") or "")[:200].replace("\n", " ")
        lines.append(f"{i}. **{title}** (comments: {comments}, labels: {labels})")
        if body:
            lines.append(f"   {body}")
    return "\n".join(lines)


def _safe_readme_excerpt(repo_info: dict) -> str:
    text = repo_info.get("readme_text", "") or ""
    if not text:
        return "No README available."
    lines = text.split("\n")
    significant = [l for l in lines if len(l.strip()) > 20]
    return "\n".join(significant[:30])[:2000]


def _get_pain_categories(last_score: Optional[dict]) -> dict:
    if not last_score:
        return {}
    pain = last_score.get("pain_categories_json", {})
    if isinstance(pain, str):
        try:
            pain = json.loads(pain)
        except (json.JSONDecodeError, TypeError):
            pain = {}
    return pain


def _get_ranking_flags(last_score: Optional[dict]) -> list:
    if not last_score:
        return []
    flags = last_score.get("ranking_flags_json", [])
    if isinstance(flags, str):
        try:
            flags = json.loads(flags)
        except (json.JSONDecodeError, TypeError):
            flags = []
    return flags


def _get_top_pain_cluster(last_score: Optional[dict]) -> str:
    if not last_score:
        return ""
    cluster = last_score.get("top_pain_cluster", "")
    if isinstance(cluster, str):
        try:
            cluster = json.loads(cluster) if cluster.startswith("{") else {}
        except (json.JSONDecodeError, TypeError):
            cluster = {}
    return cluster


def select_mvp_type(pain_categories: dict, ranking_flags: list,
                    final_recommendation: str = "", mvp_type: str = "auto") -> str:
    if mvp_type and mvp_type != "auto":
        return mvp_type

    scores = {}
    if pain_categories:
        for k, v in pain_categories.items():
            scores.setdefault(k, 0)
            if isinstance(v, (int, float)):
                scores[k] = v

    flag_priorities = {
        "plugin_first": "plugin",
        "service_first": "tutorial_pack",
    }
    for flag in ranking_flags:
        if flag in flag_priorities:
            return flag_priorities[flag]

    if scores.get("installation_deployment", 0) >= 3:
        return "one_click_installer"
    if scores.get("performance_vram", 0) >= 3:
        return "webui"
    if scores.get("workflow_integration", 0) >= 3:
        return "plugin"
    if scores.get("documentation_beginner", 0) >= 3:
        return "tutorial_pack"
    if scores.get("enterprise_team", 0) >= 3:
        return "deployment_template"
    if scores.get("frontend_ui", 0) >= 3:
        return "webui"

    if "service_first" in ranking_flags:
        return "one_click_installer"
    if "plugin_first" in ranking_flags:
        return "plugin"

    return "webui"


def _llm_enhance_text(prompt: str, llm_client, llm_config) -> str:
    if not llm_client:
        return ""
    try:
        result = llm_client.chat_json(prompt, "", None)
        if result.success and result.content:
            try:
                data = json.loads(result.content)
                return data.get("text", "")
            except (json.JSONDecodeError, TypeError):
                pass
    except Exception:
        pass
    return ""


def _generate_product_name(repo_name: str, repo_description: str, llm_client=None, llm_config=None) -> list:
    names = [
        f"{repo_name.split('/')[-1].replace('-', ' ').title()} Manager",
        f"{repo_name.split('/')[-1].replace('-', ' ').title()} Easy",
        f"One-Click {repo_name.split('/')[-1].replace('-', ' ').title()}",
        f"{repo_name.split('/')[-1].replace('-', ' ').title()} Desktop",
        f"Quick {repo_name.split('/')[-1].replace('-', ' ').title()}",
    ]
    return names


def _write_readme(out_dir: Path, repo_full_name: str, mvp_type: str,
                  last_score: Optional[dict], repo_info: Optional[dict],
                  issues: list):
    name = repo_full_name.split("/")[-1]
    desc = repo_info.get("description", "") if repo_info else ""
    if last_score and last_score.get("why_opportunity"):
        desc = last_score["why_opportunity"][:200]
    score = last_score.get("opportunity_score", 0) if last_score else 0
    rec = last_score.get("final_recommendation", "") if last_score else ""
    target = last_score.get("best_for", "developers") if last_score else "developers"
    pain_summary = _get_pain_categories(last_score)

    lines = [
        f"# MVP Brief: {name}",
        "",
        f"> Generated from {repo_full_name} | Opportunity Score: {score}/100 | Type: {mvp_type}",
        "",
        "## Overview",
        "",
        f"This MVP brief was automatically generated by GitHub Opportunity Radar.",
        f"It analyzes the open-source project **{repo_full_name}** and produces a",
        f"structured package that can be handed to Codex to build an MVP.",
        "",
        "### Source",
        "",
        f"- **Repo**: [{repo_full_name}](https://github.com/{repo_full_name})",
        f"- **Description**: {desc}",
        f"- **Opportunity Score**: {score}/100",
        f"- **Recommendation**: {rec}",
        f"- **Target Users**: {target}",
        f"- **MVP Type**: {mvp_type}",
        "",
        "### Target User",
        "",
        f"The primary users are {target}. They are experiencing pain around:",
        "",
    ]
    for k, v in pain_summary.items():
        if isinstance(v, dict):
            name_label = v.get("name", k)
            count = v.get("count", 0)
            lines.append(f"- **{name_label}** ({count} issues)")
        elif isinstance(v, (int, float)):
            lines.append(f"- **{k}** ({v} issues)")
    lines.append("")
    lines.append("### Core Pain Point")
    opp = last_score.get("why_opportunity", "") if last_score else ""
    lines.append(f">{opp[:300]}" if opp else "> See user_pain_evidence.md for details.")
    lines.append("")
    lines.append("### Minimal Product Form")
    lines.append("")
    brief_lines = {
        "one_click_installer": "A single-click installer script for the target tool.",
        "webui": "A local WebUI for the target tool.",
        "plugin": "A plugin/integration for the target tool.",
        "mcp_server": "An MCP server wrapping the target tool's functionality.",
        "chrome_extension": "A Chrome extension that enhances the target tool's UX.",
        "deployment_template": "A deployment template for the target tool.",
        "tutorial_pack": "A tutorial pack for the target tool.",
    }
    lines.append(brief_lines.get(mvp_type, "An MVP for this opportunity."))
    lines.append("")
    lines.append("### How to Use codex_prompt.md")
    lines.append("")
    lines.append("1. Open [codex_prompt.md](codex_prompt.md)")
    lines.append("2. Copy the entire content")
    lines.append("3. Paste into Codex with: `--model claude-sonnet-4-20250514` or similar")
    lines.append("4. Codex will build the MVP from scratch")
    lines.append("5. Follow the 7-day build plan in [build_plan_7_days.md](build_plan_7_days.md)")
    lines.append("")
    lines.append("### Files in this Brief")
    lines.append("")
    lines.append("| File | Description |")
    lines.append("|------|-------------|")
    lines.append("| [README.md](README.md) | This file |")
    lines.append("| [product_brief.md](product_brief.md) | Product description, positioning, success metrics |")
    lines.append("| [user_pain_evidence.md](user_pain_evidence.md) | Evidence from real GitHub issues |")
    lines.append("| [mvp_requirements.md](mvp_requirements.md) | MVP requirements and acceptance criteria |")
    lines.append("| [technical_architecture.md](technical_architecture.md) | Tech stack, architecture, directory structure |")
    lines.append("| [codex_prompt.md](codex_prompt.md) | Ready-to-paste prompt for Codex |")
    lines.append("| [build_plan_7_days.md](build_plan_7_days.md) | 7-day build plan |")
    lines.append("| [landing_page.md](landing_page.md) | Landing page copy |")
    lines.append("| [pricing_experiment.md](pricing_experiment.md) | Pricing experiment plan |")
    lines.append("| [validation_checklist.md](validation_checklist.md) | Manual validation checklist |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*DRAFT — This is an automatically generated MVP brief. "
                 "Review all assumptions before building.*")

    out_path = out_dir / "README.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_product_brief(out_dir: Path, repo_full_name: str, mvp_type: str,
                         last_score: Optional[dict], repo_info: Optional[dict],
                         issues: list, llm_client=None, llm_config=None):
    name = repo_full_name.split("/")[-1]
    desc = repo_info.get("description", "") if repo_info else ""
    target = last_score.get("best_for", "developers") if last_score else "developers"
    why_opp = last_score.get("why_opportunity", "") if last_score else ""
    recommended_mvp = last_score.get("recommended_mvp_idea", "") if last_score else ""
    pain_summary = _get_pain_categories(last_score)

    product_names = _generate_product_name(repo_full_name, desc, llm_client, llm_config)
    pain_text = ", ".join(k for k, v in pain_summary.items()) if pain_summary else "N/A"

    lines = [
        f"# Product Brief: {name}",
        "",
        f"> DRAFT — Generated {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Suggested Product Names",
        "",
    ]
    for i, n in enumerate(product_names, 1):
        lines.append(f"{i}. **{n}**")
    lines.append("")
    lines.append("## One-Sentence Positioning")
    lines.append("")
    lines.append(f"A {mvp_type} that makes {name} accessible to {target}.")
    lines.append("")
    lines.append("## Target Users")
    lines.append("")
    lines.append(f"- **Primary**: {target}")
    lines.append(f"- **Secondary**: Developers and teams working with {name}")
    lines.append("")
    lines.append("## How Users Solve This Today")
    lines.append("")
    lines.append("- Manual setup and configuration")
    lines.append("- Reading through project documentation")
    lines.append("- Following community guides and tutorials")
    lines.append("- Trial and error with CLI flags")
    lines.append("")
    lines.append("## Why Existing Solutions Are Not Good Enough")
    lines.append("")
    reasons = [
        "Requires deep technical knowledge of the underlying tool.",
        "No standardized setup process.",
        "Documentation is scattered or incomplete.",
        "No turnkey solution exists.",
    ]
    for r in reasons:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## What This MVP Solves")
    lines.append("")
    if why_opp:
        lines.append(why_opp[:500])
        lines.append("")
    lines.append("## What This MVP Does NOT Solve")
    lines.append("")
    lines.append("- Production-grade deployment at scale")
    lines.append("- Enterprise security and compliance")
    lines.append("- Multi-team collaboration features")
    lines.append("- Integration with all possible third-party tools")
    lines.append("")
    lines.append("## Core Value Proposition")
    lines.append("")
    lines.append(f"**{recommended_mvp or f'A {mvp_type} for {name}'}** — "
                 f"so {target} can get started without pain.")
    lines.append("")
    lines.append("## Success Metrics")
    lines.append("")
    lines.append("| Metric | Target |")
    lines.append("|--------|--------|")
    lines.append("| Time to first success | < 5 minutes |")
    lines.append("| User completes setup | > 80% first attempt |")
    lines.append(f"| GitHub stars for MVP | > 100 in first month |")
    lines.append("| Active users | > 50 in first week |")
    lines.append("| Support requests | < 10 in first week |")
    lines.append("")
    lines.append("## Pain Categories Identified")
    lines.append("")
    lines.append(f"- {pain_text}")

    out_path = out_dir / "product_brief.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_user_pain_evidence(out_dir: Path, repo_full_name: str, issues: list):
    lines = [
        f"# User Pain Evidence: {repo_full_name}",
        "",
        f"> DRAFT — Generated {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Evidence from GitHub Issues",
        "",
    ]

    if not issues or len(issues) < 3:
        lines.append("**Evidence is weak. Manual validation required.**")
        lines.append("")
        lines.append(f"Only {len(issues) if issues else 0} issues were available for analysis.")
        lines.append("This is insufficient to draw reliable conclusions about user pain points.")
        lines.append("Consider running a larger scan or manually reviewing the repo's issue tracker.")
        lines.append("")

    quality_issues = [i for i in (issues or []) if len((i.get("body", "") or "")) > 50]
    if not quality_issues:
        lines.append("**No issues with sufficient detail found.**")
        lines.append("")
        lines.append("The available issues are too brief to extract meaningful pain evidence.")
        lines.append("")

    pain_categories = {
        "installation_deployment": "Setup & Installation Pain",
        "performance_vram": "Performance / Resource Pain",
        "workflow_integration": "Workflow Integration Pain",
        "documentation_beginner": "Documentation / Learning Pain",
        "enterprise_team": "Enterprise / Team Pain",
        "frontend_ui": "UI / Frontend Pain",
        "bug_report": "Bugs / Stability",
        "feature_request": "Feature Requests",
    }

    for iss in (issues or [])[:20]:
        title = iss.get("title", "")
        url = iss.get("url", "")
        labels = ", ".join(iss.get("labels", [])[:4])
        comments = iss.get("comments_count", 0)
        cat = iss.get("category", "")
        cat_name = pain_categories.get(cat, cat)
        body = (iss.get("body", "") or "")[:300].replace("\n", " ")
        lines.append(f"### [{title}]({url})")
        lines.append(f"- **Category**: {cat_name} | **Labels**: {labels} | **Comments**: {comments}")
        lines.append(f"- **Excerpt**: {body}")
        lines.append("")

    out_path = out_dir / "user_pain_evidence.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_mvp_requirements(out_dir: Path, repo_full_name: str, mvp_type: str,
                            last_score: Optional[dict], issues: list,
                            repo_info: Optional[dict]):
    name = repo_full_name.split("/")[-1]
    desc = repo_info.get("description", "") if repo_info else ""

    lines = [
        f"# MVP Requirements: {name} ({mvp_type})",
        "",
        f"> DRAFT — Generated {datetime.now(timezone.utc).isoformat()}",
        "",
        "## MVP Goal",
        "",
        f"Build a {mvp_type} that makes {desc or name} accessible to non-expert users.",
        "",
        "## User Stories",
        "",
        f"- As a {name} user, I want to {_get_mvp_primary_action(mvp_type)} so I can get value fast.",
        "- As a beginner, I want clear guidance so I don't get stuck.",
        "- As an evaluator, I want to see results quickly so I can decide if this is useful.",
        "",
        "## Core Features",
        "",
    ]

    core_features = _get_core_features(mvp_type, name)
    for f in core_features:
        lines.append(f"- {f}")
    lines.append("")

    lines.append("## Non-Core Features (Future)")
    lines.append("")
    non_core = [
        "Advanced configuration options",
        "Multi-user support",
        "Cloud deployment",
        "Analytics and usage tracking",
        "Third-party integrations beyond the essential ones",
    ]
    for f in non_core:
        lines.append(f"- {f}")
    lines.append("")

    lines.append("## Out of Scope (Won't Do)")
    lines.append("")
    wont_do = [
        "Mobile native apps (iOS/Android)",
        "Enterprise SSO / RBAC",
        "Horizontal scaling / load balancing",
        "Native desktop app (unless mvp_type requires Electron/Tauri)",
        "CI/CD integration beyond MVP scope",
    ]
    for f in wont_do:
        lines.append(f"- {f}")
    lines.append("")

    lines.append("## Inputs")
    lines.append("")
    inputs = _get_inputs(mvp_type, name)
    for i in inputs:
        lines.append(f"- {i}")
    lines.append("")

    lines.append("## Outputs")
    lines.append("")
    outputs = _get_outputs(mvp_type, name)
    for o in outputs:
        lines.append(f"- {o}")
    lines.append("")

    lines.append("## UI / CLI / API Design")
    lines.append("")
    design = _get_design(mvp_type, name)
    for d in design:
        lines.append(f"- {d}")
    lines.append("")

    lines.append("## Error Handling")
    lines.append("")
    errors = [
        "Graceful error messages for all failure modes",
        "Logging to file for debugging",
        "Network timeout handling with retry",
        "Invalid input validation and feedback",
        "Crash recovery / restart guidance",
    ]
    for e in errors:
        lines.append(f"- {e}")
    lines.append("")

    lines.append("## Acceptance Criteria")
    lines.append("")
    criteria = _get_acceptance_criteria(mvp_type, name)
    for c in criteria:
        lines.append(f"- {c}")
    lines.append("")

    out_path = out_dir / "mvp_requirements.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _get_mvp_primary_action(mvp_type: str) -> str:
    actions = {
        "one_click_installer": "install and run it with a single command",
        "webui": "upload a config and see results in the browser",
        "plugin": "add functionality without modifying the original code",
        "mcp_server": "connect AI agents to the tool's data",
        "chrome_extension": "enhance their workflow directly in the browser",
        "deployment_template": "deploy to production in under 30 minutes",
        "tutorial_pack": "learn the tool with a real project",
    }
    return actions.get(mvp_type, "get value fast")


def _get_core_features(mvp_type: str, name: str) -> list:
    features = {
        "one_click_installer": [
            f"Auto-detect OS and architecture",
            f"Download required dependencies for {name}",
            f"Install {name} with sensible defaults",
            f"Display live install log",
            f"Verify installation success",
            f"Provide uninstall option",
            f"Handle common errors with fix suggestions",
        ],
        "webui": [
            f"Local web server with Gradio or FastAPI",
            f"Upload / paste configuration for {name}",
            f"Run {name} with submitted config",
            f"Display results in browser",
            f"Save and load configurations",
            f"Export results (JSON / CSV / Markdown)",
            f"Basic error display and suggestions",
        ],
        "plugin": [
            f"Plugin entry point compatible with {name}",
            f"Configuration page or file",
            f"Core integration with {name}'s API or hooks",
            f"Status display showing plugin health",
            f"Installation guide in README",
        ],
        "mcp_server": [
            f"MCP tools for {name}'s core operations",
            f"MCP resources exposing structured data from {name}",
            f"MCP prompts for common queries",
            f"JSON Schema for all tool parameters",
            f"Local startup via `uvx` or `pip install`",
            f"README with usage examples",
        ],
        "chrome_extension": [
            f"Manifest V3 compliant extension",
            f"Content script that enhances {name}'s web interface",
            f"Popup UI with quick actions",
            f"Options page for configuration",
            f"Background service worker",
            f"Storage API for user settings",
        ],
        "deployment_template": [
            f"Dockerfile for {name}",
            f"docker-compose.yml with all services",
            f".env.example with all configuration variables",
            f"Health check endpoint",
            f"Deployment guide (bare metal, Docker, cloud)",
            f"Monitoring and logging setup",
        ],
        "tutorial_pack": [
            f"Step-by-step tutorial for {name}",
            f"Example project using {name}",
            f"Common errors and solutions section",
            f"Template project structure",
            f"Paid tier with additional templates (optional)",
        ],
    }
    return features.get(mvp_type, [f"Core functionality for {name}"])


def _get_inputs(mvp_type: str, name: str) -> list:
    inputs = {
        "one_click_installer": [f"Target OS / architecture", "Optional install path"],
        "webui": [f"Configuration file or form inputs for {name}"],
        "plugin": [f"{name} installation path", "Configuration options"],
        "mcp_server": [f"{name} API endpoint or data source", "Configuration"],
        "chrome_extension": [f"Target website URL", "User preferences"],
        "deployment_template": [f"Environment variables", "Deployment target config"],
        "tutorial_pack": ["User's existing knowledge level"],
    }
    return inputs.get(mvp_type, [f"Configuration for {name}"])


def _get_outputs(mvp_type: str, name: str) -> list:
    outputs = {
        "one_click_installer": [f"Installed {name}", "Installation log"],
        "webui": [f"Processed results from {name}", "Export files"],
        "plugin": [f"Plugin working with {name}"],
        "mcp_server": [f"Running MCP server", "Tool responses"],
        "chrome_extension": [f"Enhanced web interface"],
        "deployment_template": [f"Running {name} deployment", "Health check OK"],
        "tutorial_pack": [f"Completed tutorial", "Learning progress"],
    }
    return outputs.get(mvp_type, [f"Running MVP for {name}"])


def _get_design(mvp_type: str, name: str) -> list:
    designs = {
        "one_click_installer": [
            "CLI interface: single command to install",
            "Real-time progress display in terminal",
            "Colored output for success/warning/error states",
            "Log file written alongside installation",
        ],
        "webui": [
            "Gradio-based web interface",
            "Input area for configuration",
            "Run button with progress indicator",
            "Result display area",
            "Export buttons for results",
            "Dark/light mode support",
        ],
        "plugin": [
            "Plugin class with standard lifecycle hooks",
            "Configuration via YAML/JSON file",
            "Integration via {name}'s plugin system",
        ],
        "mcp_server": [
            "Python FastMCP server",
            "Tool definitions with JSON Schema",
            "Resource definitions with URI templates",
            "Prompt templates",
        ],
        "chrome_extension": [
            "Popup with action buttons",
            "Content script injecting UI elements",
            "Options page with settings",
            "Background script for persistent state",
        ],
        "deployment_template": [
            "Docker multi-stage build",
            "docker-compose with services",
            "Health check endpoint at /health",
            "Prometheus metrics endpoint /metrics (optional)",
        ],
        "tutorial_pack": [
            "Markdown tutorial files organized by chapter",
            "Example project code",
            "Exercise files with solutions",
        ],
    }
    return designs.get(mvp_type, ["See technical_architecture.md"])


def _get_acceptance_criteria(mvp_type: str, name: str) -> list:
    criteria = {
        "one_click_installer": [
            "Install completes on macOS, Linux, Windows",
            "Dependencies are auto-detected and installed",
            "User sees clear success/failure feedback",
            "Uninstalled cleanly",
            "Total time < 5 minutes on standard hardware",
        ],
        "webui": [
            "Server starts with a single command",
            "User can upload config and see results",
            "Results are accurate (matches CLI behavior)",
            "Export produces valid files",
            "Non-technical user can complete flow without help",
        ],
        "plugin": [
            "Plugin is discoverable by {name}",
            "Plugin configuration can be modified at runtime",
            "Plugin loads without errors",
            "Plugin unloads cleanly",
        ],
        "mcp_server": [
            "Server starts and connects to MCP client",
            "All tool definitions are valid JSON Schema",
            "Each tool executes and returns results",
            "Error responses are informative",
        ],
        "chrome_extension": [
            "Extension loads in Chrome without warnings",
            "Content script runs on target pages",
            "Popup displays correctly",
            "Settings persist across browser sessions",
        ],
        "deployment_template": [
            "Docker build succeeds",
            "docker-compose up starts all services",
            "Health check returns 200",
            "Configuration via .env works correctly",
            "Deployment guide is complete and testable",
        ],
        "tutorial_pack": [
            "Tutorial covers setup to advanced usage",
            "Example project builds and runs",
            "All commands in tutorial are copy-pasteable",
            "Common errors documented with solutions",
        ],
    }
    return criteria.get(mvp_type, ["MVP is functional and usable"])


def _write_technical_architecture(out_dir, repo_full_name, mvp_type, repo_info=None):
    name = repo_full_name.split("/")[-1]
    short = name.replace("-", "_").lower()

    tech_stacks = {
        "one_click_installer": {
            "language": "Python 3.10+",
            "framework": "Click / argparse CLI",
            "deps": ["requests", "rich (terminal formatting)", "psutil"],
        },
        "webui": {
            "language": "Python 3.10+",
            "framework": "Gradio 4+",
            "deps": ["gradio", "pydantic", "httpx"],
        },
        "plugin": {
            "language": "Python 3.10+",
            "framework": f"setuptools / {name} plugin API",
            "deps": [f"{name}-sdk (if available)", "pydantic"],
        },
        "mcp_server": {
            "language": "Python 3.10+",
            "framework": "FastMCP (MCP Python SDK)",
            "deps": ["mcp", "httpx", "pydantic"],
        },
        "chrome_extension": {
            "language": "JavaScript / TypeScript",
            "framework": "Manifest V3, vanilla JS or React",
            "deps": ["webextension-polyfill (optional)"],
        },
        "deployment_template": {
            "language": "Docker / YAML",
            "framework": "Docker Compose",
            "deps": ["Docker 24+", "Docker Compose v2+"],
        },
        "tutorial_pack": {
            "language": "Markdown + Python/TypeScript examples",
            "framework": "MkDocs or plain Markdown",
            "deps": ["mkdocs (optional)", "example project deps"],
        },
    }

    ts = tech_stacks.get(mvp_type, tech_stacks["webui"])

    lines = [
        f"# Technical Architecture: {name}",
        "",
        f"> DRAFT — MVP Type: {mvp_type}",
        "",
        "## Recommended Tech Stack",
        "",
        f"- **Language**: {ts['language']}",
        f"- **Framework**: {ts['framework']}",
        f"- **Key Dependencies**:",
    ]
    for d in ts["deps"]:
        lines.append(f"  - {d}")
    lines.append("")

    lines.append("## Project Directory Structure")
    lines.append("")
    lines.append("```")
    lines.append(f"{short}/")
    lines.append(f"├── {short}/")
    lines.append("│   ├── __init__.py")
    lines.append("│   ├── main.py")
    lines.append("│   ├── config.py")
    lines.append("│   ├── utils.py")
    lines.append("│   └── errors.py")
    lines.append("├── tests/")
    lines.append("│   ├── __init__.py")
    lines.append("│   ├── test_main.py")
    lines.append("│   └── test_utils.py")
    lines.append("├── outputs/")
    lines.append("├── .env.example")
    lines.append("├── requirements.txt")
    lines.append("├── README.md")
    lines.append("├── smoke_test.py")
    lines.append("└── .gitignore")
    lines.append("```")
    lines.append("")

    lines.append("## Data Flow")
    lines.append("")
    flows = {
        "one_click_installer": "User runs CLI -> Script detects OS -> Downloads deps -> Installs -> Verifies -> Outputs log",
        "webui": "User opens browser -> Uploads config or fills form -> Backend processes -> Displays results -> User exports",
        "plugin": f"User installs plugin -> {name} loads plugin -> Plugin hooks into events -> Provides functionality",
        "mcp_server": "MCP client connects -> Discovers tools via listTools() -> Calls tool() -> Server processes -> Returns result",
        "chrome_extension": "User browses webpage -> Content script runs -> Injects UI -> User interacts -> BG script handles state",
        "deployment_template": "User runs docker-compose up -> Services start -> Health check passes -> App is accessible",
        "tutorial_pack": "User reads tutorial -> Follows examples -> Builds project -> References solutions",
    }
    lines.append(flows.get(mvp_type, "See codex_prompt.md for details."))
    lines.append("")

    lines.append("## Module Breakdown")
    lines.append("")
    modules = {
        "one_click_installer": [
            "main.py — CLI entry point, argument parsing",
            "config.py — Default paths, OS detection, dependency list",
            "utils.py — Download, checksum verification, shell commands",
            "errors.py — Error types, recovery suggestions",
        ],
        "webui": [
            "main.py — Gradio app, route definitions, event handlers",
            "config.py — Configuration model, defaults, validation",
            "utils.py — Core processing logic, data transformation",
            "errors.py — Error display formatting",
        ],
    }
    mod_list = modules.get(mvp_type, [
        "main.py — Entry point, CLI or server setup",
        "config.py — Configuration management",
        "utils.py — Core business logic",
        "errors.py — Error handling",
    ])
    for m in mod_list:
        lines.append(f"- {m}")
    lines.append("")

    lines.append("## Configuration")
    lines.append("")
    lines.append("- All configuration via `.env` file or CLI flags")
    lines.append("- Sensible defaults for first-time users")
    lines.append("- Configuration validation on startup")
    lines.append("")

    lines.append("## Dependencies")
    lines.append("")
    lines.append("- Minimal dependencies, prefer stdlib where possible")
    lines.append("- Pin major versions in requirements.txt")
    lines.append("- Vendored deps only when absolutely necessary")
    lines.append("")

    lines.append("## Risk Points")
    lines.append("")
    lines.append(f"- {name} API may change without notice")
    lines.append(f"- {name} may have undocumented dependencies")
    lines.append("- Platform-specific behavior differences")
    lines.append("- Error messages from underlying tool may be opaque")
    lines.append("")

    lines.append("## Future Extensions")
    lines.append("")
    lines.append("- Cloud deployment option")
    lines.append("- Team collaboration features")
    lines.append("- Plugin system for extensibility")
    lines.append("- Analytics to track usage patterns")

    out_path = out_dir / "technical_architecture.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_codex_prompt(out_dir, repo_full_name, mvp_type, issues, last_score, repo_info):
    name = repo_full_name.split("/")[-1]
    short = name.replace("-", "_").lower()
    desc = repo_info.get("description", "") if repo_info else ""
    target = last_score.get("best_for", "developers") if last_score else "developers"

    issue_titles = "\n".join(
        f"- {i.get('title', '')}" for i in (issues or [])[:10]
    ) if issues else "- No specific issues available"

    lines = [
        "# Codex Prompt: Build MVP",
        "",
        "请使用以下提示词创建一个完整的 MVP 项目。",
        "",
        "---",
        "",
        f"## 项目名: {name}-{mvp_type}",
        "",
        f"## 项目描述",
        "",
        f"创建一个 {mvp_type}，解决 {repo_full_name} 用户的核心痛点。",
        f"原始仓库描述: {desc}",
        f"目标用户: {target}",
        "",
        "## 技术栈要求",
        "",
    ]

    tech_reqs = _get_tech_requirements(mvp_type)
    for t in tech_reqs:
        lines.append(f"- {t}")
    lines.append("")

    lines.append("## 目录结构")
    lines.append("")
    lines.append("```")
    lines.append(f"{short}/")
    lines.append("├── src/")
    lines.append("│   ├── __init__.py")
    lines.append("│   ├── main.py")
    lines.append("│   ├── config.py")
    lines.append("│   └── utils.py")
    lines.append("├── tests/")
    lines.append("│   ├── __init__.py")
    lines.append("│   └── test_main.py")
    lines.append("├── .env.example")
    lines.append("├── requirements.txt")
    lines.append("├── README.md")
    lines.append("└── smoke_test.py")
    lines.append("```")
    lines.append("")

    lines.append("## 功能要求")
    lines.append("")
    core = _get_core_features(mvp_type, name)
    for f in core:
        lines.append(f"- [ ] {f}")
    lines.append("")

    lines.append("## 运行命令")
    lines.append("")
    run_cmds = _get_run_commands(mvp_type, short)
    for c in run_cmds:
        lines.append(f"- `{c}`")
    lines.append("")

    lines.append("## 验收标准")
    lines.append("")
    criteria = _get_acceptance_criteria(mvp_type, name)
    for c in criteria:
        lines.append(f"- [ ] {c}")
    lines.append("")

    lines.append("## 不要做的事")
    lines.append("")
    donts = [
        "不要添加用户认证系统（MVP 阶段不需要）",
        "不要添加数据库（优先使用文件存储）",
        "不要添加分析/遥测功能",
        "不要过度工程化（优先可读代码而非抽象）",
        "不要使用需要注册的外部 API 服务",
        "不要假设网络环境（支持离线使用）",
    ]
    for d in donts:
        lines.append(f"- {d}")
    lines.append("")

    lines.append("## 工作要求")
    lines.append("")
    lines.append("- 第一版必须可运行，不能有未实现的占位代码")
    lines.append("- 如果外部依赖不可用，提供 mock / fixture，不能冒充真实数据")
    lines.append("- 生成 README.md，包含安装和运行说明")
    lines.append("- 生成 requirements.txt / package.json")
    lines.append("- 生成 .env.example")
    lines.append("- 生成 smoke_test.py，验证核心功能")
    lines.append("")

    lines.append("## 参考 Issues（真实用户反馈）")
    lines.append("")
    lines.append(issue_titles)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated by GitHub Opportunity Radar*")

    out_path = out_dir / "codex_prompt.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _get_tech_requirements(mvp_type: str) -> list:
    reqs = {
        "one_click_installer": [
            "Python 3.10+",
            "Click/argparse CLI",
            "subprocess 调用系统命令",
            "requests 下载依赖",
            "rich 终端输出格式化",
        ],
        "webui": [
            "Python 3.10+",
            "Gradio 4+ 作为 Web 框架",
            "pydantic 配置验证",
            "httpx / aiohttp API 调用",
        ],
        "plugin": [
            "Python 3.10+",
            "setuptools 打包",
            f"兼容 {mvp_type} 的插件 API",
        ],
        "mcp_server": [
            "Python 3.10+",
            "MCP Python SDK (mcp>=1.0)",
            "pydantic 数据验证",
            "httpx 外部 API 调用",
        ],
        "chrome_extension": [
            "Manifest V3",
            "Vanilla JS 或 React",
            "Chrome Storage API",
        ],
        "deployment_template": [
            "Docker 24+",
            "Docker Compose v2+",
        ],
        "tutorial_pack": [
            "Markdown 文档",
            "Python / TypeScript 示例代码",
            "MkDocs（可选）",
        ],
    }
    return reqs.get(mvp_type, ["Python 3.10+"])


def _get_run_commands(mvp_type: str, short: str) -> list:
    cmds = {
        "one_click_installer": [
            f"python {short}/main.py install",
            f"python {short}/main.py uninstall",
            f"python -m pytest tests/",
            f"python smoke_test.py",
        ],
        "webui": [
            f"pip install -r requirements.txt",
            f"python -m {short}.main",
            f"# Opens http://localhost:7860",
            f"python -m pytest tests/",
            f"python smoke_test.py",
        ],
        "plugin": [
            f"pip install -e .",
            f"python smoke_test.py",
        ],
        "mcp_server": [
            f"pip install -r requirements.txt",
            f"python -m {short}.main",
            f"# Connect via MCP client",
            f"python smoke_test.py",
        ],
        "chrome_extension": [
            f"# Load unpacked in Chrome: chrome://extensions",
            f"# Enable Developer Mode -> Load unpacked -> src/",
            f"npm test",
        ],
        "deployment_template": [
            f"docker compose up -d",
            f"curl http://localhost:8080/health",
            f"docker compose down",
        ],
        "tutorial_pack": [
            f"# Follow tutorials/01-getting-started.md",
            f"cd examples/basic && python main.py",
        ],
    }
    return cmds.get(mvp_type, [f"python -m {short}.main"])


def _write_build_plan(out_dir, repo_full_name, mvp_type, last_score=None):
    name = repo_full_name.split("/")[-1]

    day_plans = {
        "Day 1": f"Scaffold project, set up virtual environment, install dependencies, create project structure, implement CLI entry point, verify that `--help` works.",
        "Day 2": f"Implement core features: detect environment, download/setup dependencies, verify installation.",
        "Day 3": f"Enhance UI output with colors and progress bars, add error handling with fix suggestions, implement uninstall.",
        "Day 4": f"Test on macOS, Linux, Windows. Fix platform-specific issues. Handle edge cases (network failure, permission denied, disk space).",
        "Day 5": f"Finalize packaging, write README with screenshots, add smoke_test.py, create demo GIF.",
        "Day 6": f"Find 3 real users from the GitHub issues, ask them to test, collect feedback.",
        "Day 7": f"Review feedback. Decide: continue (fix issues) / stop (no demand) / pivot to service.",
    }

    if mvp_type == "webui":
        day_plans = {
            "Day 1": f"Scaffold project, create Gradio app skeleton, define input components, verify server starts.",
            "Day 2": f"Implement core processing logic, connect frontend to backend, display results.",
            "Day 3": f"Add configuration management, export functionality, error handling.",
            "Day 4": f"Test with real {name} data. Fix edge cases. Optimize response time.",
            "Day 5": f"Add docs, README, smoke_test.py. Package as pip-installable.",
            "Day 6": f"Share with 3 target users. Collect feedback on UX and missing features.",
            "Day 7": f"Review feedback. Ship v0.1 or pivot.",
        }
    elif mvp_type == "plugin":
        day_plans = {
            "Day 1": f"Study {name}'s plugin API. Create plugin skeleton. Implement lifecycle hooks.",
            "Day 2": f"Implement core plugin functionality. Connect to {name}'s events.",
            "Day 3": f"Add configuration, error handling, logging.",
            "Day 4": f"Test with real {name} installation. Fix compatibility issues.",
            "Day 5": f"Write installation guide, README, example config.",
            "Day 6": f"Publish to PyPI or plugin marketplace. Share with community.",
            "Day 7": f"Collect feedback. Fix bugs. Decide on maintenance plan.",
        }
    elif mvp_type == "mcp_server":
        day_plans = {
            "Day 1": f"Scaffold FastMCP server, define first tool, test with MCP Inspector.",
            "Day 2": f"Implement all required tools with JSON Schema validation.",
            "Day 3": f"Add MCP resources and prompts. Handle errors gracefully.",
            "Day 4": f"Test with real MCP client. Fix edge cases.",
            "Day 5": f"Package as pip-installable. Add README with usage examples.",
            "Day 6": f"Publish to PyPI. Share with developer communities.",
            "Day 7": f"Review usage patterns. Iterate on most-used tools.",
        }

    lines = [
        f"# Build Plan: 7 Days to {mvp_type.capitalize()} MVP for {name}",
        "",
        f"> DRAFT — Adjust based on actual availability and complexity.",
        "",
    ]
    for day, plan in day_plans.items():
        lines.append(f"## {day}")
        lines.append("")
        lines.append(plan)
        lines.append("")

    lines.append("## Decision Framework After Day 7")
    lines.append("")
    lines.append("| Signal | Decision |")
    lines.append("|--------|----------|")
    lines.append("| >5 users testing, positive feedback | **Continue**: Fix issues, ship v0.2 |")
    lines.append("| 2-5 users, mixed feedback | **Refine**: Address top complaints, retest |")
    lines.append("| <2 users, no engagement | **Stop**: Not enough demand, document learnings |")
    lines.append("| Clear paying customer signal | **Pivot to Service**: Offer setup/consulting |")
    lines.append("| Plugin/extension request from users | **Pivot**: Build plugin for existing platform |")

    out_path = out_dir / "build_plan_7_days.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_landing_page(out_dir, repo_full_name, mvp_type, last_score,
                        repo_info, llm_client=None, llm_config=None):
    name = repo_full_name.split("/")[-1]
    desc = repo_info.get("description", "") if repo_info else ""
    target = last_score.get("best_for", "developers") if last_score else "developers"
    why_opp = last_score.get("why_opportunity", "") if last_score else ""

    tagline = {
        "one_click_installer": f"Install {name} in One Click",
        "webui": f"Your {name} Dashboard, No Terminal Required",
        "plugin": f"Supercharge {name} with One Plugin",
        "mcp_server": f"Connect {name} to the AI Agent Ecosystem",
        "chrome_extension": f"Enhance {name} Right in Your Browser",
        "deployment_template": f"Deploy {name} in Under 30 Minutes",
        "tutorial_pack": f"Master {name} in One Weekend",
    }

    lines = [
        f"# Landing Page Copy: {name}",
        "",
        f"> DRAFT — MVP Type: {mvp_type}",
        "",
        "## Hero Section",
        "",
        f"### Headline: {tagline.get(mvp_type, f'Get Started with {name}')}",
        f"",
        f"### Subheadline: Stop wrestling with setup. Start using {name}.",
        "",
        "## User Pain Points",
        "",
        f"- Setting up {name} takes hours, not minutes",
        f"- Documentation assumes you already know the stack",
        f"- One typo in a config file breaks everything",
        f"- No easy way to evaluate {name} before committing",
        "",
        "## Solution",
        "",
        f"Our {mvp_type} makes {name} accessible to {target}.",
    ]
    if why_opp:
        lines.append(why_opp[:400])
    lines.append("")
    lines.append("## Features")
    lines.append("")

    features = {
        "one_click_installer": [
            "Auto-detect your OS and architecture",
            "One command installs everything",
            "Real-time progress in your terminal",
            "Smart error recovery",
            "Clean uninstall when you're done",
        ],
        "webui": [
            "Upload config, see results instantly",
            "No command line needed",
            "Save and restore configurations",
            "Export results in your preferred format",
            "Dark mode included",
        ],
    }
    feat_list = features.get(mvp_type, ["See mvp_requirements.md"])
    for f in feat_list:
        lines.append(f"- {f}")
    lines.append("")

    lines.append("## Call to Action")
    lines.append("")
    lines.append(f"> **Get {tagline.get(mvp_type, f'{name} Easy')}**")
    lines.append(">")
    lines.append("> Copy the codex_prompt.md → Paste into Codex → Build in 7 days.")
    lines.append("")
    lines.append("## FAQ")
    lines.append("")
    lines.append("**Q: Do I need to know how to use {name}?**")
    lines.append("A: No. Our MVP handles the complexity for you.")
    lines.append("")
    lines.append("**Q: Is this free?**")
    lines.append("A: The MVP template is free. "
                 "Premium features like deployment and customization are available.")
    lines.append("")
    lines.append("**Q: How long does it take to get started?**")
    lines.append(f"A: The {mvp_type} can be built in 7 days using the codex_prompt.md.")
    lines.append("")
    lines.append("## Waitlist Copy")
    lines.append("")
    lines.append(f"> **Join the waitlist for {name} {mvp_type.capitalize()}**")
    lines.append(">")
    lines.append("> Be the first to know when the MVP is ready.")
    lines.append("> Early access users get 50% off the premium version.")
    lines.append(">")
    lines.append("> [your-waitlist-link.com]")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*DRAFT — This is an automatically generated landing page. "
                 "Review and customize before publishing.*")

    out_path = out_dir / "landing_page.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_pricing_experiment(out_dir, repo_full_name, mvp_type, last_score=None):
    name = repo_full_name.split("/")[-1]

    lines = [
        f"# Pricing Experiment: {name}",
        "",
        f"> DRAFT — MVP Type: {mvp_type}",
        "",
        "## Tiers",
        "",
        "### Free Tier",
        "",
        f"- The {mvp_type} itself (open source)",
        "- Community support (GitHub Issues)",
        "- Basic documentation",
        "",
        "### Paid Tier — Template Pack ($19-$49 one-time)",
        "",
        f"- Premium {mvp_type} template with advanced features",
        "- Ready-to-deploy configuration",
        "- Email support",
        "- Example projects and tutorials",
        "",
        "### Deployment Service ($99-$299)",
        "",
        "- We deploy the MVP for you",
        "- Custom configuration",
        "- 30-minute setup call",
        "- 1 week of support",
        "",
        "### Consulting ($150-$250/hour)",
        "",
        f"- Custom {mvp_type} development",
        "- Integration with existing workflows",
        "- Performance optimization",
        "- Training session for your team",
        "",
        "### Small Team License ($99-$199/year)",
        "",
        "- Up to 5 team members",
        "- Priority support",
        "- Advanced features",
        "- Regular updates",
        "",
        "## Suggested Prices",
        "",
        "| Tier | Price | Target Audience |",
        "|------|-------|-----------------|",
        "| Free | $0 | Individual developers |",
        "| Template Pack | $29 one-time | Indie developers |",
        "| Deployment Service | $149 | Small teams |",
        "| Consulting | $200/hr | Companies needing custom work |",
        "| Team License | $149/year | Small dev teams |",
        "",
        "## How to Validate Willingness to Pay",
        "",
        "1. **Pre-sell the Template Pack** — Put a \"Buy Now\" button on the landing page"
        " before building. If 5 people buy, build it.",
        "2. **Ask in issues** — Reply to relevant GitHub issues:"
        " \"Would you pay $29 for a one-click installer?\"",
        "3. **LinkedIn/Twitter poll** — Run a poll asking what people would pay.",
        "4. **Build in public** — Share the MVP build process on social media,"
        " ask followers what they'd pay.",
        "",
        "## Pricing Principles",
        "",
        "- Start free. Add paid tiers after validation.",
        f"- The {mvp_type} template is the entry drug — charge for convenience and support.",
        "- One-time purchases > subscriptions for indie developer tools.",
        "- Price in USD. Adjust for local markets if needed.",
    ]

    out_path = out_dir / "pricing_experiment.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_validation_checklist(out_dir, repo_full_name, mvp_type, last_score, issues):
    score = last_score.get("opportunity_score", 0) if last_score else 0
    flags = _get_ranking_flags(last_score)

    issue_count = len(issues) if issues else 0
    strong_issues = sum(1 for i in (issues or []) if
                        i.get("comments_count", 0) >= 3 or len((i.get("body", "") or "")) > 100)
    has_paying_signal = any("pricing" in (i.get("body", "") or "").lower() or
                           "$" in (i.get("body", "") or "") for i in (issues or []))

    lines = [
        f"# Validation Checklist: {repo_full_name}",
        "",
        f"> DRAFT — MVP Type: {mvp_type}",
        "",
        "## Pre-Build Validation",
        "",
        "Check each item before starting development:",
        "",
    ]

    checks = [
        ("10+ similar issues found", issue_count >= 10,
         f"Found {issue_count} issues. {'Sufficient' if issue_count >= 10 else 'Insufficient'} evidence."),
        ("Strong demand expressed in issues", strong_issues >= 3,
         f"{strong_issues} issues with detailed descriptions. {'Good signal' if strong_issues >= 3 else 'Weak signal'}."),
        ("Someone willing to try a demo", False,
         "Check by replying to issues. Manual step."),
        ("Can build working version in 7 days", True,
         f"{mvp_type} is typically buildable in 7 days by one developer."),
        ("Clear distribution channel", False,
         f"GitHub community around {repo_full_name} is the primary channel. Consider Twitter/X, Hacker News, Reddit."),
        ("Obvious commercial competitor", False,
         "Research if paid alternatives exist. If yes, differentiate."),
        ("Suitable for solo developer", True,
         f"{mvp_type.capitalize()} is feasible for one full-time developer."),
        ("Worth continuing", score >= 50,
         f"Opportunity score: {score}/100. {'Continue' if score >= 50 else 'Review carefully'}."),
    ]

    lines.append("| Criterion | Status | Evidence |")
    lines.append("|-----------|--------|----------|")
    for name, status, evidence in checks:
        status_str = "✅ Pass" if status else "❌ Fail" if status is False else "❓ Manual check"
        lines.append(f"| {name} | {status_str} | {evidence} |")
    lines.append("")

    lines.append("## Risk Flags")
    lines.append("")
    if flags:
        for f in flags:
            lines.append(f"- ⚠️ {f}")
        lines.append("")
    else:
        lines.append("No risk flags detected.")
        lines.append("")

    lines.append("## Final Verdict")
    lines.append("")
    if score >= 70 and issue_count >= 10:
        verdict = "✅ **Strong candidate**. Build the MVP."
    elif score >= 50 and issue_count >= 5:
        verdict = "⚠️ **Moderate candidate**. Validate manually before building."
    else:
        verdict = "❌ **Weak candidate**. Consider other opportunities."
    lines.append(verdict)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*DRAFT — This is an automatically generated checklist. "
                 "Review each item before making a build decision.*")

    out_path = out_dir / "validation_checklist.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def generate_mvp_brief(repo_full_name: str, mvp_type: str = "auto",
                       llm_config: Optional[LLMConfig] = None,
                       repo_info: Optional[dict] = None,
                       issues: list = None) -> tuple:
    out_dir = OUTPUTS_DIR / "mvp_briefs" / _sanitize_name(repo_full_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_id = get_repo_id_by_name(repo_full_name)
    last_score = get_latest_score_for_repo(repo_id) if repo_id else None
    watch_status = get_watchlist_status(repo_id) if repo_id else None
    snapshots = get_last_two_snapshots(repo_id) if repo_id else []

    if issues is None and repo_id:
        snap = snapshots[0] if snapshots else None
        if snap:
            issues = get_issues_for_snapshot(snap.get("repo_snapshot_id", snap["id"]))

    repo_info = repo_info or {}
    stars_current = repo_info.get("stars", 0) or (snapshots[0].get("stars", 0) if snapshots else 0)
    open_issues_count = repo_info.get("open_issues_count", 0) or len(issues or [])

    pain_categories = _get_pain_categories(last_score)
    ranking_flags = _get_ranking_flags(last_score)
    final_rec = last_score.get("final_recommendation", "") if last_score else ""

    mvp_type = select_mvp_type(pain_categories, ranking_flags, final_rec, mvp_type)

    llm_client = None
    if llm_config and llm_config.provider != "none":
        llm_client = create_client(llm_config)

    files_created = []

    files_created.append(_write_readme(out_dir, repo_full_name, mvp_type,
                                        last_score, repo_info, issues or []))
    files_created.append(_write_product_brief(out_dir, repo_full_name, mvp_type,
                                               last_score, repo_info, issues or [],
                                               llm_client, llm_config))
    files_created.append(_write_user_pain_evidence(out_dir, repo_full_name, issues or []))
    files_created.append(_write_mvp_requirements(out_dir, repo_full_name, mvp_type,
                                                  last_score, issues or [], repo_info))
    files_created.append(_write_technical_architecture(out_dir, repo_full_name, mvp_type, repo_info))
    files_created.append(_write_codex_prompt(out_dir, repo_full_name, mvp_type,
                                              issues or [], last_score, repo_info))
    files_created.append(_write_build_plan(out_dir, repo_full_name, mvp_type, last_score))
    files_created.append(_write_landing_page(out_dir, repo_full_name, mvp_type,
                                              last_score, repo_info, llm_client, llm_config))
    files_created.append(_write_pricing_experiment(out_dir, repo_full_name, mvp_type, last_score))
    files_created.append(_write_validation_checklist(out_dir, repo_full_name, mvp_type,
                                                      last_score, issues or []))

    return out_dir, files_created
