from typing import Optional
from src.llm.base import LLMConfig, LLMClient
from src.llm.ollama_client import OllamaClient
from src.llm.openai_compatible_client import OpenAICompatibleClient


def create_client(cfg: LLMConfig) -> Optional[LLMClient]:
    if cfg.provider == "ollama":
        return OllamaClient(
            base_url=cfg.base_url,
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            timeout=cfg.timeout,
            use_json_schema=cfg.use_json_schema,
            force_json_mode=cfg.force_json_mode,
        )
    elif cfg.provider == "openai_compatible":
        return OpenAICompatibleClient(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            timeout=cfg.timeout,
            use_json_schema=cfg.use_json_schema,
            force_json_mode=cfg.force_json_mode,
        )
    elif cfg.provider == "litellm_proxy":
        return OpenAICompatibleClient(
            base_url=cfg.base_url,
            api_key=cfg.api_key or "sk-lite-proxy",
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            timeout=cfg.timeout,
            use_json_schema=cfg.use_json_schema,
            force_json_mode=cfg.force_json_mode,
            litellm_mode=True,
        )
    return None


def test_connection(cfg: LLMConfig) -> dict:
    client = create_client(cfg)
    if client is None:
        return {"status": "error", "detail": "No provider configured", "provider": cfg.provider}
    result = client.ping()
    supports_schema = client.supports_json_schema
    supports_mode = client.supports_json_mode
    provider_name = client.provider_name
    model_name = client.model_name
    return {
        "status": result.get("status", "error"),
        "provider": provider_name,
        "model": model_name,
        "supports_json_schema": supports_schema,
        "supports_json_mode": supports_mode,
        "detail": result.get("detail", ""),
    }
