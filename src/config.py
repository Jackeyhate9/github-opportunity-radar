from pathlib import Path
import os

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"
CACHE_DIR = BASE_DIR / "cache"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    db_path: Path = DATA_DIR / "radar.sqlite"

    request_delay_seconds: float = 2.0
    request_timeout: int = 30
    cache_enabled: bool = True
    cache_max_age_hours: int = 6

    default_target_count: int = 15
    default_min_stars: int = 100
    default_max_stars: int = 50000
    default_min_open_issues: int = 5
    default_max_issues_per_repo: int = 20
    default_time_range_days: int = 30
    default_trending_period: str = "weekly"

    enable_raw_readme_fetch: bool = True
    enable_github_search_fallback: bool = True
    exclude_mature_commercial: bool = False

    default_keywords: list = [
        "ai", "agent", "llm", "rag", "ollama", "comfyui",
        "gradio", "ai video", "workflow automation",
        "developer tools", "mcp", "browser automation", "local llm"
    ]

    trending_languages: list = ["python", "javascript", "typescript", "go", "rust"]

    search_fallback_keywords: list = [
        "ai agent", "ollama", "comfyui", "gradio", "mcp",
        "local llm", "workflow automation", "developer tools ai"
    ]

    enable_llm: bool = False
    llm_continue_on_error: bool = True
    llm_provider: str = "none"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:14b"
    llm_api_key: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1200
    llm_timeout: int = 300
    llm_language: str = "zh"
    llm_batch_size: int = 3
    llm_max_repos: int = 10
    llm_use_json_schema: bool = False
    llm_force_json_mode: bool = False
    llm_disable_streaming: bool = True
    llm_cache_enabled: bool = True
    llm_preload_model: bool = False

    @classmethod
    def from_env(cls):
        s = cls()
        if os.environ.get("LLM_PROVIDER"):
            s.llm_provider = os.environ["LLM_PROVIDER"]
        if os.environ.get("LLM_BASE_URL"):
            s.llm_base_url = os.environ["LLM_BASE_URL"]
        if os.environ.get("LLM_API_KEY"):
            s.llm_api_key = os.environ["LLM_API_KEY"]
        if os.environ.get("LLM_MODEL"):
            s.llm_model = os.environ["LLM_MODEL"]
        return s


settings = Settings()
