# AI Token Economy — Phase 1

A **proof-of-concept AI gateway** that routes prompts across multiple LLM
providers, decides which model to use per request, and meters token usage.

This is the **Phase 1 spine**: it proves the routing + metering concept on one
machine, using free-tier APIs and a small local model. It is **internal,
test-only** — free-tier keys, a CPU local model, and no billing/conversion layer
yet.

```
        ┌────────────┐
        │     UI     │   3 modes: local-qwen | gemini-api | model-decider
        └─────┬──────┘
              │  prompt + mode
        ┌─────▼──────┐
        │  Decider   │   in decider mode, rules pick the model (and say why)
        │  (Python)  │
        └─────┬──────┘
              │  chosen model name
        ┌─────▼──────┐
        │  LiteLLM   │   one unified API → Gemini (cloud) or Ollama (local)
        └─────┬──────┘
              │  answer + token usage
        ┌─────▼──────┐
        │  Metering  │   logs RAW usage to usage.db (no conversion yet)
        └────────────┘
```

---

## Before you start (each person needs their own)

1. A **Gemini API key** — free, no card — from https://aistudio.google.com
2. **Docker Desktop** installed and running
3. **Python 3.10+**

---

## 1. Start the gateway stack (Docker)

The `docker-compose.yml` runs LiteLLM + Ollama + Postgres together.

```bash
# set your own Gemini key (this is how litellm_config.yaml reads it)
export GEMINI_API_KEY="your-gemini-key-here"

# start everything
docker compose up -d

# pull the small local model into the Ollama container (one time)
docker compose exec ollama ollama pull qwen2.5:3b
```

Test the gateway directly:

```bash
curl http://localhost:4000/chat/completions \
  -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  -d '{"model":"gemini-flash","messages":[{"role":"user","content":"Hello"}]}'
```

---

## 2. Run the app (decider + UI + metering)

```bash
pip install fastapi uvicorn httpx

export LITELLM_URL=http://localhost:4000
export LITELLM_KEY=sk-1234          # the master_key in litellm_config.yaml

python -m uvicorn app:app --reload --port 8000
```

Open **http://localhost:8000**

- **local-qwen** / **gemini-api** — force that model (manual override)
- **model-decider** — the decider chooses, and the UI shows which model + why

Raw usage log: **http://localhost:8000/usage**

---

## Files

| File | What it does |
|------|--------------|
| `docker-compose.yml`   | Runs LiteLLM + Ollama + Postgres |
| `litellm_config.yaml`  | Registers the models (`gemini-flash`, `local-qwen`) |
| `app.py`               | FastAPI app: serves the UI, ties everything together |
| `decider.py`           | The routing brain — simple rules, returns model + reason |
| `metering.py`          | Writes RAW token usage to `usage.db` (SQLite) |

---

## Notes / gotchas

- **Model names must match.** `decider.py` uses `local-qwen` and `gemini-flash`;
  these must match the `model_name` values in `litellm_config.yaml`.
- **The local model is SLOW on CPU** (~50s per reply for a 3B model). That's
  expected — CPU is fine to prove the routing path, but production needs GPUs.
  If it times out, the app already allows up to 5 minutes and caps output at
  512 tokens. For snappier demos, pull a smaller model (`qwen2.5:1.5b`) or keep
  the model warm: `docker compose exec ollama ollama run qwen2.5:3b "hi"`.
- **Never commit your API key.** It lives in an environment variable, and
  `Gemini API key.txt` / `usage.db` are git-ignored on purpose.

---

## What's NOT here yet (next steps)

- **Conversion layer** — turning raw provider tokens into "our tokens" (a token
  from one provider ≠ a token from another). Metering stores RAW on purpose so
  this can be added later without losing history.
- **DB-driven decider** — rules are in code for now; later they move to a
  model/provider specs table.
- **Second provider, auth, billing** — planned for later in Phase 1 / Phase 2.
