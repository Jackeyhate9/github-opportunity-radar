# LLM Providers

LLM analysis is **optional**. The core scan + score + verdict engine works without it.

| Provider | Endpoint | Key needed | JSON Schema |
|---|---|---|---|
| `ollama` | `/api/chat` + `/v1/chat/completions` | No | ❌ |
| `openai_compatible` | `/chat/completions` | Yes | ✅ (optional) |
| `litellm_proxy` | `/chat/completions` | Yes | ✅ (optional) |

## CLI usage

```bash
# Ollama
python app.py scan --enable-llm --llm-provider ollama --llm-model llama3.2

# OpenAI-compatible (e.g. Groq, DeepSeek, Together)
python app.py scan --enable-llm --llm-provider openai_compatible \
  --llm-base-url https://api.groq.com/openai/v1 \
  --llm-model llama-3.3-70b-versatile \
  --llm-api-key gsk_xxx

# LiteLLM proxy
python app.py scan --enable-llm --llm-provider litellm_proxy \
  --llm-base-url http://localhost:4000 \
  --llm-api-key sk-lite-proxy
```

## Environment variables

| Variable | Maps to |
|---|---|
| `LLM_PROVIDER` | `--llm-provider` |
| `LLM_BASE_URL` | `--llm-base-url` |
| `LLM_API_KEY` | `--llm-api-key` |
| `LLM_MODEL` | `--llm-model` |

CLI arguments take precedence over env vars.

## Fallback behavior

If LLM is unreachable or times out, the system automatically falls back to rule-based analysis. The scan continues without interruption.
