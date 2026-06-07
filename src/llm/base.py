from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    provider: str = "none"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:14b"
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout: int = 300
    language: str = "zh"
    batch_size: int = 3
    max_repos: int = 10
    use_json_schema: bool = False
    force_json_mode: bool = False
    cache_enabled: bool = True


@dataclass
class ChatResult:
    content: Optional[str] = None
    success: bool = False
    json_mode_used: str = "none"
    latency_ms: int = 0
    status_detail: str = ""


class LLMClient(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str,
             json_schema: Optional[dict] = None) -> str | None:
        ...

    def chat_json(self, system_prompt: str, user_prompt: str,
                  json_schema: Optional[dict] = None) -> ChatResult:
        return ChatResult()

    def chat_json_schema(self, system_prompt: str, user_prompt: str,
                         json_schema: dict) -> ChatResult:
        return ChatResult()

    def health_check(self) -> bool:
        return False

    def ping(self) -> dict:
        ok = self.health_check()
        return {"status": "ok" if ok else "error", "provider": self.provider_name, "model": self.model_name}

    def preload(self) -> bool:
        return False

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    def supports_json_schema(self) -> bool:
        return False

    @property
    def supports_json_mode(self) -> bool:
        return False
