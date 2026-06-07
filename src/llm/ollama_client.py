import json
import time
import requests
from typing import Optional
from src.llm.base import LLMClient, ChatResult


class OllamaClient(LLMClient):
    def __init__(self, base_url: str, model: str,
                 temperature: float = 0.2, max_tokens: int = 1200,
                 timeout: int = 300,
                 use_json_schema: bool = False,
                 force_json_mode: bool = False):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._use_json_schema = use_json_schema
        self._force_json_mode = force_json_mode

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def supports_json_schema(self) -> bool:
        return False

    @property
    def supports_json_mode(self) -> bool:
        return False

    def health_check(self) -> bool:
        try:
            url = f"{self._base_url}/api/tags"
            resp = requests.get(url, timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def ping(self) -> dict:
        try:
            url = f"{self._base_url}/api/tags"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]
                available = any(self._model in n for n in model_names)
                if available:
                    detail = f"Ollama running, model '{self._model}' available"
                else:
                    detail = f"Ollama running, model '{self._model}' not pulled yet, need: ollama pull {self._model}"
                return {
                    "status": "ok",
                    "detail": detail,
                    "models_available": model_names,
                }
            return {"status": "error", "detail": f"Ollama returned {resp.status_code}"}
        except requests.ConnectionError:
            return {"status": "error", "detail": "Cannot connect to Ollama. Is it running? Try: ollama serve"}
        except requests.RequestException as e:
            return {"status": "error", "detail": str(e)}

    def preload(self) -> bool:
        try:
            url = f"{self._base_url}/api/generate"
            payload = {"model": self._model, "prompt": "", "keep_alive": "5m"}
            resp = requests.post(url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def chat(self, system_prompt: str, user_prompt: str,
             json_schema: Optional[dict] = None) -> str | None:
        result = self._try_openai_compat(system_prompt, user_prompt)
        if result is not None:
            return result
        result = self._try_native_api(system_prompt, user_prompt)
        return result

    def _try_openai_compat(self, system_prompt: str, user_prompt: str) -> str | None:
        url = f"{self._base_url}/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        try:
            resp = requests.post(url, json=payload, timeout=self._timeout)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
            else:
                if resp.status_code != 404:
                    pass
        except requests.RequestException:
            pass
        return None

    def _try_native_api(self, system_prompt: str, user_prompt: str) -> str | None:
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self._temperature,
                "num_predict": self._max_tokens,
            },
            "stream": False,
        }
        try:
            resp = requests.post(url, json=payload, timeout=self._timeout)
            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("message", {})
                return msg.get("content", "")
            else:
                print(f"  [LLM] Ollama native API error {resp.status_code}")
                body = resp.text[:200]
                if "no keep_alive" in body.lower():
                    print(f"  [LLM]   Consider preloading: ollama run {self._model} (then Ctrl+D)")
        except requests.Timeout:
            print(f"  [LLM] Ollama timeout after {self._timeout}s. Model may still be loading. Try: ollama run {self._model}")
        except requests.ConnectionError:
            print(f"  [LLM] Cannot connect to Ollama at {self._base_url}. Is ollama serve running?")
        except requests.RequestException as e:
            print(f"  [LLM] Ollama request failed: {e}")
        return None

    def chat_json(self, system_prompt: str, user_prompt: str,
                  json_schema: Optional[dict] = None) -> ChatResult:
        start = time.time()
        result = ChatResult()
        raw = self.chat(system_prompt, user_prompt, json_schema)
        latency = int((time.time() - start) * 1000)
        result.latency_ms = latency
        if raw is not None:
            result.content = raw
            result.success = True
            result.json_mode_used = "text"
            result.status_detail = f"ok ({latency}ms)"
        else:
            result.status_detail = f"failed ({latency}ms)"
        return result

    def chat_json_schema(self, system_prompt: str, user_prompt: str,
                         json_schema: dict) -> ChatResult:
        return self.chat_json(system_prompt, user_prompt, json_schema)
