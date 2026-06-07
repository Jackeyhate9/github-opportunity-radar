import json
import time
import requests
from typing import Optional
from src.llm.base import LLMClient, ChatResult


class OpenAICompatibleClient(LLMClient):
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.2, max_tokens: int = 1200,
                 timeout: int = 300,
                 use_json_schema: bool = False,
                 force_json_mode: bool = False,
                 litellm_mode: bool = False):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._use_json_schema = use_json_schema
        self._force_json_mode = force_json_mode
        self._litellm_mode = litellm_mode

    @property
    def provider_name(self) -> str:
        return "litellm_proxy" if self._litellm_mode else "openai_compatible"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def supports_json_schema(self) -> bool:
        return self._use_json_schema

    @property
    def supports_json_mode(self) -> bool:
        return not self._use_json_schema

    def health_check(self) -> bool:
        try:
            url = f"{self._base_url}/models"
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            resp = requests.get(url, headers=headers, timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def ping(self) -> dict:
        try:
            url = f"{self._base_url}/models"
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                models_data = resp.json()
                models_list = models_data.get("data", [])
                model_ids = [m.get("id", "") for m in models_list]
                available = any(self._model in m for m in model_ids)
                return {
                    "status": "ok",
                    "detail": f"Provider reachable, model '{self._model}' {'available' if available else 'not in listed models'}",
                    "models_available": model_ids[:20],
                }
            return {"status": "error", "detail": f"Provider returned {resp.status_code}: {resp.text[:200]}"}
        except requests.ConnectionError:
            return {"status": "error", "detail": f"Cannot connect to {self._base_url}"}
        except requests.RequestException as e:
            return {"status": "error", "detail": str(e)}

    def chat(self, system_prompt: str, user_prompt: str,
             json_schema: Optional[dict] = None) -> str | None:
        url = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

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

        if json_schema and self._use_json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "repo_analysis",
                    "strict": True,
                    "schema": json_schema,
                },
            }
        elif json_schema and self._force_json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self._timeout)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
            else:
                resp_body = resp.text[:300]
                if "api key" in resp_body.lower() or "unauthorized" in resp_body.lower() or "auth" in resp_body.lower():
                    print(f"  [LLM] Authentication error ({resp.status_code}). Check API key.")
                elif resp.status_code == 404:
                    print(f"  [LLM] Model '{self._model}' not found at provider ({resp.status_code})")
                else:
                    print(f"  [LLM] API error {resp.status_code}: {resp_body}")
        except requests.Timeout:
            print(f"  [LLM] Request timeout after {self._timeout}s")
        except requests.ConnectionError:
            print(f"  [LLM] Connection error: cannot reach {self._base_url}")
        except requests.RequestException as e:
            print(f"  [LLM] Request failed: {e}")
        return None

    def chat_json(self, system_prompt: str, user_prompt: str,
                  json_schema: Optional[dict] = None) -> ChatResult:
        start = time.time()
        result = ChatResult()

        strategies = []

        if json_schema and self._use_json_schema:
            strategies.append(("json_schema", json_schema))
        if json_schema and self._force_json_mode:
            strategies.append(("json_object", json_schema))

        strategies.append(("text", json_schema))

        for mode_name, schema in strategies:
            raw = None
            if mode_name == "json_schema":
                raw = self._chat_with_json_schema(system_prompt, user_prompt, schema)
            elif mode_name == "json_object":
                raw = self._chat_with_json_object(system_prompt, user_prompt, schema)
            else:
                raw = self._chat_text(system_prompt, user_prompt)
            if raw is not None:
                latency = int((time.time() - start) * 1000)
                result.content = raw
                result.success = True
                result.json_mode_used = mode_name
                result.latency_ms = latency
                result.status_detail = f"ok ({latency}ms, {mode_name})"
                return result

        latency = int((time.time() - start) * 1000)
        result.latency_ms = latency
        result.status_detail = f"all_strategies_failed ({latency}ms)"
        return result

    def chat_json_schema(self, system_prompt: str, user_prompt: str,
                         json_schema: dict) -> ChatResult:
        return self.chat_json(system_prompt, user_prompt, json_schema)

    def _chat_with_json_schema(self, system_prompt: str, user_prompt: str,
                                schema: dict) -> str | None:
        url = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "repo_analysis",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self._timeout)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
        except requests.RequestException:
            pass
        return None

    def _chat_with_json_object(self, system_prompt: str, user_prompt: str,
                                schema: dict) -> str | None:
        url = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        system_content = system_prompt + "\n\nYou MUST output valid JSON. No markdown, no explanation."

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self._timeout)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    try:
                        json.loads(content)
                        return content
                    except (json.JSONDecodeError, TypeError):
                        pass
        except requests.RequestException:
            pass
        return None

    def _chat_text(self, system_prompt: str, user_prompt: str) -> str | None:
        return self.chat(system_prompt, user_prompt)
