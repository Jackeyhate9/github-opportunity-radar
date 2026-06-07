import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional, Callable

from src.llm.base import LLMConfig, ChatResult
from src.llm.provider_router import create_client, test_connection
from src.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.llm.prompts import SYSTEM_PROMPT_EN, USER_PROMPT_TEMPLATE_EN
from src.llm.json_repair import extract_json, safe_parse_analysis
from src.llm.schemas import LLMRepoAnalysis, PainCluster

CURRENT_PROMPT_VERSION = "2.0"
CURRENT_SCHEMA_VERSION = "1.0"


def _get_client(cfg: LLMConfig):
    return create_client(cfg)


def _build_repo_data(repo: dict, issues: list, readme_excerpt: str) -> dict:
    return {
        "repo": repo.get("full_name", ""),
        "description": (repo.get("description") or "")[:500],
        "language": repo.get("language", ""),
        "stars": repo.get("stars", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "early_signals": repo.get("readme_early_signals", []),
        "commercial_signals": repo.get("readme_commercial_signals", []),
        "pain_categories": repo.get("top_pain_categories", {}),
        "rule_scores": {
            "hot_score": repo.get("hot_score", 0),
            "issue_score": repo.get("issue_score", 0),
            "early_score": repo.get("early_score", 0),
            "commercial_gap_score": repo.get("commercial_gap_score", 0),
            "mvp_feasibility_score": repo.get("mvp_feasibility_score", 0),
            "opportunity_score": repo.get("opportunity_score", 0),
        },
        "readme_excerpt": readme_excerpt[:3000],
        "issues": [
            {
                "title": i.get("title", ""),
                "labels": i.get("labels", []),
                "comments_count": i.get("comments_count", 0),
                "category": i.get("category", ""),
            }
            for i in (issues or [])[:20]
        ],
    }


def _get_readme_excerpt(repo: dict) -> str:
    text = repo.get("readme_text", "") or ""
    if not text:
        return ""
    lines = text.split("\n")
    significant = [l for l in lines if len(l.strip()) > 20]
    return "\n".join(significant[:60])[:3000]


def _get_cache_key(repo_full_name: str, readme_text: str, issues: list, model: str,
                   prompt_version: str, schema_version: str) -> str:
    h = hashlib.md5()
    h.update(repo_full_name.encode())
    if readme_text:
        h.update(readme_text[:2000].encode())
    issue_titles = "|".join(i.get("title", "") for i in (issues or [])[:20])
    h.update(issue_titles.encode())
    h.update(model.encode())
    h.update(prompt_version.encode())
    h.update(schema_version.encode())
    return h.hexdigest()


class LLMAnalyzer:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = _get_client(config)
        self.cache = {}

    @property
    def enabled(self) -> bool:
        return self.config.provider != "none" and self.client is not None

    def analyze_repo(self, repo: dict, issues: list, scan_run_id: int,
                     db_save_func: Optional[Callable] = None) -> dict:
        if not self.enabled:
            return {"llm_status": "disabled", "llm_analysis": None}

        readme_excerpt = _get_readme_excerpt(repo)
        cache_key = _get_cache_key(
            repo.get("full_name", ""),
            readme_excerpt,
            issues,
            self.config.model,
            CURRENT_PROMPT_VERSION,
            CURRENT_SCHEMA_VERSION,
        )

        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if cached.get("llm_status") == "success":
                return cached

        repo_data = _build_repo_data(repo, issues, readme_excerpt)
        prompt_schema_str = self._get_json_schema()
        prompt_data = json.dumps(repo_data, ensure_ascii=False, indent=2)

        if self.config.language == "en":
            system_prompt = SYSTEM_PROMPT_EN
            user_prompt = USER_PROMPT_TEMPLATE_EN.format(
                repo_data=prompt_data, json_schema=prompt_schema_str
            )
        else:
            system_prompt = SYSTEM_PROMPT
            user_prompt = USER_PROMPT_TEMPLATE.format(
                repo_data=prompt_data, json_schema=prompt_schema_str
            )

        openai_schema = None
        if self.config.use_json_schema:
            openai_schema = self._build_openai_schema()

        chat_result: ChatResult = self.client.chat_json(system_prompt, user_prompt, openai_schema)

        if not chat_result.success or chat_result.content is None:
            result = {
                "llm_status": "unavailable",
                "llm_analysis": None,
                "llm_raw": (chat_result.content or "")[:500],
                "status_detail": chat_result.status_detail,
                "latency_ms": chat_result.latency_ms,
            }
            self.cache[cache_key] = result
            return result

        raw_output = chat_result.content

        if openai_schema and chat_result.json_mode_used == "json_schema":
            try:
                parsed = json.loads(raw_output)
            except (json.JSONDecodeError, TypeError):
                parsed = extract_json(raw_output)
        else:
            parsed = extract_json(raw_output)

        if parsed is None:
            result = {
                "llm_status": "failed",
                "llm_analysis": None,
                "llm_raw": raw_output[:500],
                "status_detail": f"parse_failed ({chat_result.latency_ms}ms)",
                "latency_ms": chat_result.latency_ms,
            }
            self.cache[cache_key] = result
            return result

        validated = safe_parse_analysis(parsed)
        if validated is None:
            result = {
                "llm_status": "failed",
                "llm_analysis": None,
                "llm_raw": raw_output[:500],
                "status_detail": f"validation_failed ({chat_result.latency_ms}ms)",
                "latency_ms": chat_result.latency_ms,
            }
            self.cache[cache_key] = result
            return result

        analysis = {
            "llm_status": "success",
            "llm_provider": self.client.provider_name,
            "llm_model": self.client.model_name,
            "llm_analysis": validated,
            "one_sentence_summary": validated.get("one_sentence_summary", ""),
            "user_pain_summary": validated.get("user_pain_summary", ""),
            "best_mvp_idea": validated.get("best_mvp_idea", ""),
            "mvp_type": validated.get("mvp_type", ""),
            "target_customer": validated.get("target_customer", ""),
            "why_now": validated.get("why_now", ""),
            "monetization_angle": validated.get("monetization_angle", ""),
            "build_difficulty": validated.get("build_difficulty", ""),
            "first_7_day_build_plan": validated.get("first_7_day_build_plan", []),
            "risks": validated.get("risks", []),
            "confidence": validated.get("confidence", ""),
            "llm_notes": validated.get("llm_notes", ""),
            "pain_clusters": validated.get("pain_clusters", []),
            "cache_key": cache_key,
            "status_detail": chat_result.status_detail,
            "latency_ms": chat_result.latency_ms,
            "prompt_version": CURRENT_PROMPT_VERSION,
            "schema_version": CURRENT_SCHEMA_VERSION,
        }

        if db_save_func:
            try:
                db_save_func(scan_run_id, repo.get("repo_id", 0), analysis)
            except Exception as e:
                print(f"  [LLM] DB save error: {e}")

        self.cache[cache_key] = analysis
        return analysis

    def _get_json_schema(self) -> str:
        return json.dumps(LLMRepoAnalysis.model_json_schema(), indent=2, ensure_ascii=False)

    def _build_openai_schema(self) -> dict:
        raw = LLMRepoAnalysis.model_json_schema()
        defs = raw.get("$defs", {})

        def _resolve_ref(schema: dict) -> dict:
            ref = schema.get("$ref", "")
            if ref:
                ref_path = ref.replace("#/$defs/", "")
                resolved = defs.get(ref_path, {})
                result = {"type": resolved.get("type", "object")}
                if "properties" in resolved:
                    result["properties"] = {}
                    for pk, pv in resolved["properties"].items():
                        result["properties"][pk] = _resolve_ref(pv)
                if "required" in resolved:
                    result["required"] = resolved["required"]
                if result.get("type") == "object":
                    result["additionalProperties"] = False
                if result.get("type") == "array":
                    items = resolved.get("items", {})
                    result["items"] = _resolve_ref(items)
                return result
            if schema.get("type") == "array":
                result = {"type": "array"}
                items = schema.get("items", {})
                result["items"] = _resolve_ref(items)
                return result
            return {"type": schema.get("type", "string")}

        properties = {}
        for key, val in raw.get("properties", {}).items():
            properties[key] = _resolve_ref(val)

        result = {
            "type": "object",
            "properties": properties,
            "required": raw.get("required", []),
            "additionalProperties": False,
        }
        return result
