# Example Commands

## Scan

```bash
# Default scan
python app.py scan

# Custom keywords + range
python app.py scan --keywords "ollama,mcp,comfyui" --target 20 --min-stars 300

# Scan with LLM
python app.py scan --enable-llm --llm-provider ollama --llm-model llama3.2

# Clear HTTP cache before scan
python app.py scan --clear-cache
```

## Web UI

```bash
python app.py web
# → http://127.0.0.1:7860
```

## Export

```bash
python app.py export                # CSV (default)
python app.py export --format json
python app.py export --format md
```

## Validation pack

```bash
python app.py validation-pack --repo owner/repo-name
python app.py validation-pack --repo owner/repo-name --enable-llm --llm-provider ollama
```

## MVP brief

```bash
python app.py mvp-brief --repo owner/repo-name
python app.py mvp-brief --repo owner/repo-name --mvp-type webui
```

## Daily watchlist

```bash
python app.py daily-scan
python app.py daily-report
```

## Experiment tracker

```bash
python app.py experiment-create --name "My Experiment"
python app.py experiment-list
python app.py experiment-report --id 1
python app.py experiment-dashboard
```

## Diagnostics

```bash
python app.py smoke-test            # Offline health check
python app.py llm-test --llm-provider ollama  # Test LLM connection
```
