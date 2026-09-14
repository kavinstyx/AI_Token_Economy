# AI Token Economy — Phase 1

A **proof-of-concept AI gateway** that intelligently routes prompts across multiple LLM providers, selects a model based on configurable routing rules, and records raw token usage for analysis.

Phase 1 focuses on proving the core **routing + gateway + metering** architecture locally using Docker, FastAPI, LiteLLM, MySQL, PostgreSQL, Ollama, and multiple external LLM providers.

> **Status:** Development / Proof of Concept
> **Environment:** Local / Test Only
> **Billing:** Not implemented
> **Production Ready:** No

---

## Architecture

```text
                         ┌──────────────────────┐
                         │        Web UI        │
                         │     HTML / JS        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │       app.py         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Model Decider     │
                         │     decider.py       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │        MySQL         │
                         │ routing_rules        │
                         │ model_specs          │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Selected Model    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       LiteLLM        │
                         │       :4000          │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │          │          │          │           │
              ▼          ▼          ▼          ▼           ▼
           Ollama     Gemini       Groq     OpenRouter   Mistral
           Qwen 3B    2.5 Flash   GPT-OSS      Free        14B
              │          │          │          │           │
              └──────────┴──────────┴──────────┴───────────┘
                                    │
                                    ▼
                              LLM Response
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Metering       │
                         │     metering.py      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │        MySQL         │
                         │      usage_raw       │
                         └──────────────────────┘


                   LiteLLM Internal Database
                         ┌───────────────┐
                         │  PostgreSQL   │
                         │     :5432     │
                         └───────────────┘
```

---

## How It Works

A request follows this flow:

```text
User Prompt
    │
    ▼
Web UI
    │
    ▼
FastAPI /chat
    │
    ├── Manual model selection
    │
    └── Model Decider
             │
             ▼
        MySQL routing rules
             │
             ▼
        Selected model
             │
             ▼
           LiteLLM
             │
             ├── Local Qwen
             ├── Gemini
             ├── Groq
             ├── OpenRouter
             └── Mistral
             │
             ▼
         LLM Response
             │
             ▼
        Raw Token Usage
             │
             ▼
        MySQL usage_raw
```

---

## Supported Models

The current LiteLLM configuration exposes the following model groups:

| Model Group       | Provider      | Purpose                                |
| ----------------- | ------------- | -------------------------------------- |
| `local-qwen`      | Ollama        | Local / simple prompts                 |
| `gemini-flash`    | Google Gemini | Strong general-purpose analysis        |
| `groq-gpt-oss`    | Groq          | Fast coding / low-latency tasks        |
| `openrouter-free` | OpenRouter    | Reasoning and free-model routing       |
| `mistral-14b`     | Mistral       | Multilingual and general-purpose tasks |

Provider availability, pricing, rate limits, model availability, and usage policies may change over time.

---

# Model Routing

The project supports two routing modes:

### 1. Model Decider

The application automatically selects a model based on routing rules stored in MySQL.

The routing rules can identify task types such as:

| Task                       | Target            |
| -------------------------- | ----------------- |
| Coding                     | `groq-gpt-oss`    |
| Translation / multilingual | `mistral-14b`     |
| Reasoning                  | `openrouter-free` |
| Analytical tasks           | `gemini-flash`    |
| Long prompts               | `gemini-flash`    |
| Simple/default prompts     | `local-qwen`      |

The rules are stored in the MySQL `routing_rules` table and evaluated according to priority.

### 2. Manual Selection

The UI also allows the user to manually select a model.

Available manual routes:

```text
local
gemini
groq
mistral
openrouter
```

The manual mode bypasses the automatic decider.

---

# Database-Driven Routing

The routing engine is implemented in `decider.py`.

It attempts to load active rules from MySQL:

```text
routing_rules
      │
      ▼
Priority order
      │
      ▼
Condition matching
      │
      ▼
Target model
```

Supported condition types include:

* `keyword`
* `max_chars`
* `default`

This makes routing rules configurable without requiring the routing logic to be rewritten in Python.

---

## Routing Fallback

If MySQL becomes unavailable, the application does not stop routing requests.

`decider.py` switches to a simplified hardcoded fallback strategy.

The fallback considers:

* coding-related keywords
* analytical / technical keywords
* long prompts
* default short prompts

The fallback is intentionally simpler than the database-driven rule set and is designed to keep the application functional when the routing database is unavailable.

---

# Token Metering

Token usage is recorded after a successful LLM response.

The current metering implementation uses **MySQL**, not SQLite.

`metering.py` records raw usage in:

```text
usage_raw
```

Recorded information includes:

```text
timestamp
user key
mode
requested model
served model
decider rule
prompt tokens
completion tokens
total tokens
prompt character count
routing source
```

Example:

```text
User Prompt
     │
     ▼
LiteLLM Response
     │
     ▼
usage information
     │
     ▼
metering.py
     │
     ▼
MySQL usage_raw
```

The project currently records **raw provider-reported token counts**.

There is currently no:

* currency conversion
* token pricing engine
* user billing
* quota management
* charge calculation

---

# FastAPI Application

The main application is implemented in:

```text
app.py
```

FastAPI provides the main application API.

### Main Endpoint

```http
POST /chat
```

Example request:

```json
{
  "prompt": "What is Kubernetes?",
  "mode": "decider",
  "user_key": "tester-1"
}
```

Example response structure:

```json
{
  "answer": "...",
  "chosen_model": "local-qwen",
  "reason": "...",
  "rule": "db_default",
  "routing_source": "db",
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  }
}
```

The application also exposes the web interface through:

```http
GET /
```

---

# Web UI

The project includes a built-in responsive web interface.

Features include:

* Prompt input
* Manual model selection
* Automatic model decider
* Selected model display
* Routing reason display
* Token usage display
* Light / dark theme
* Keyboard shortcut support
* Responsive mobile layout
* Reduced-motion support

Keyboard shortcut:

```text
Ctrl + Enter
```

or:

```text
Cmd + Enter
```

to submit a prompt.

---

# LiteLLM Gateway

LiteLLM provides a unified OpenAI-compatible API between the FastAPI application and the different model providers.

The gateway runs on:

```text
http://localhost:4000
```

The application communicates with:

```http
POST /chat/completions
```

Example:

```bash
curl -s http://localhost:4000/chat/completions \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"openrouter-free",
    "messages":[
      {
        "role":"user",
        "content":"Say hello in one short sentence."
      }
    ]
  }' | python -m json.tool
```

---

# LiteLLM Model Configuration

The current configuration contains:

```yaml
model_list:
  - model_name: gemini-flash
    litellm_params:
      model: gemini/gemini-2.5-flash
      api_key: os.environ/GEMINI_API_KEY

  - model_name: local-qwen
    litellm_params:
      model: ollama/qwen2.5:3b
      api_base: http://ollama:11434

  - model_name: groq-gpt-oss
    litellm_params:
      model: groq/openai/gpt-oss-20b
      api_key: os.environ/GROQ_API_KEY

  - model_name: openrouter-free
    litellm_params:
      model: openrouter/openrouter/free
      api_key: os.environ/OPENROUTER_API_KEY

  - model_name: mistral-14b
    litellm_params:
      model: mistral/ministral-14b-2512
      api_key: os.environ/MISTRAL_API_KEY
```

The OpenRouter route uses:

```text
openrouter/openrouter/free
```

This allows OpenRouter to select from its available free-model routing pool rather than depending on a single hardcoded free model.

---

# Docker Services

The project uses Docker Compose to run the infrastructure.

Current services:

| Service    | Image         | Purpose                        | Port     |
| ---------- | ------------- | ------------------------------ | -------- |
| LiteLLM    | LiteLLM       | Unified LLM gateway            | `4000`   |
| Ollama     | Ollama        | Local Qwen model               | `11434`  |
| PostgreSQL | PostgreSQL 15 | LiteLLM database               | Internal |
| MySQL      | MySQL 8       | Application routing + metering | `3308`   |

---

# Database Responsibilities

There are two databases in the current architecture.

### MySQL

Used by the application for:

```text
model_specs
routing_rules
usage_raw
```

MySQL is therefore responsible for:

* model metadata
* routing configuration
* application usage metering

### PostgreSQL

Used internally by LiteLLM.

It stores LiteLLM gateway-related database information.

This separation keeps the application database independent from LiteLLM's internal database.

---

# Project Structure

```text
AI Token Economy Project/
│
├── app.py
├── decider.py
├── metering.py
├── docker-compose.yml
├── litellm_config.yaml
├── schema.sql
│
├── .gitignore
│
├── README.md
│
└── Docker volumes
    ├── ollama-data
    ├── pg-data
    └── mysql-data
```

Local-only files such as API keys, logs, backups, SQLite files, Python caches, and virtual environments are excluded through `.gitignore`.

---

# Environment Variables

The application requires provider API keys for external model routes.

Example:

```bash
export GEMINI_API_KEY="your-key"
export GROQ_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
export MISTRAL_API_KEY="your-key"
```

The FastAPI application uses:

```bash
export LITELLM_URL="http://localhost:4000"
export LITELLM_KEY="sk-1234"
```

Database settings can be configured through:

```bash
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

The default application database configuration is:

```text
Host: localhost
Port: 3308
Database: token_economy
User: appuser
```

---

# Getting Started

## Requirements

Install:

* Docker Desktop
* Python 3.10+
* Git

---

## 1. Clone the repository

```bash
git clone https://github.com/kavinstyx/AI_Token_Economy.git
cd AI_Token_Economy
```

---

## 2. Configure API Keys

Set the provider keys in your local environment:

```bash
export GEMINI_API_KEY="your-key"
export GROQ_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
export MISTRAL_API_KEY="your-key"
```

Never commit API keys to Git.

---

## 3. Start Docker Services

```bash
docker compose up -d
```

Check the services:

```bash
docker compose ps
```

---

## 4. Download the Local Model

```bash
docker compose exec ollama ollama pull qwen2.5:3b
```

Verify:

```bash
docker compose exec ollama ollama list
```

---

## 5. Install Python Dependencies

```bash
pip install fastapi uvicorn httpx mysql-connector-python
```

---

## 6. Start the FastAPI Application

```bash
export LITELLM_URL=http://localhost:4000
export LITELLM_KEY=sk-1234

python -m uvicorn app:app --reload --port 8000
```

Open:

```text
http://localhost:8000
```

---

# Testing Routing

The following prompts can be used to verify the routing engine.

### Coding

```text
Write a Python function that removes duplicate values from a list while preserving the original order.
```

Expected:

```text
groq-gpt-oss
```

### Translation

```text
Translate the following sentence into French, Spanish, and German: "Our network monitoring system detects alarms in real time."
```

Expected:

```text
mistral-14b
```

### Reasoning

```text
Reason step by step about the following problem: A system has 3 independent servers with availability of 99.9% each. Calculate the probability that at least one server is available.
```

Expected:

```text
openrouter-free
```

### Analysis

```text
Analyze the advantages and disadvantages of using Kafka for a large-scale telecommunications alarm monitoring system.
```

Expected:

```text
gemini-flash
```

### Simple Prompt

```text
What is the capital of France?
```

Expected:

```text
local-qwen
```

The exact selected model can change if the routing rules in MySQL are modified.

---

# Direct Provider Testing

You can also test individual routes directly through LiteLLM.

Example:

```bash
curl -s http://localhost:4000/chat/completions \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"gemini-flash",
    "messages":[
      {
        "role":"user",
        "content":"Hello"
      }
    ]
  }' | python -m json.tool
```

Change the `model` field to:

```text
local-qwen
gemini-flash
groq-gpt-oss
openrouter-free
mistral-14b
```

---

# Error Handling

The application includes basic failure handling.

### LiteLLM timeout

If a request times out, FastAPI returns an HTTP `504` response.

This is particularly relevant for the local Qwen model when running on CPU.

### LiteLLM failure

If LiteLLM cannot process the request, the application returns an HTTP `502` response.

### Routing database failure

If MySQL is unavailable, `decider.py` switches to its fallback routing logic.

### Metering database failure

If the usage database write fails, the application logs the failure instead of crashing the successful LLM request.

---

# Security

This project is currently intended for local development and testing.

### Never commit secrets

The following files are intentionally ignored:

```text
Gemini API key.txt
.env
*.env
usage.db
*.log
*.bak
```

API keys should always be supplied through environment variables.

### Local LiteLLM key

The current configuration uses:

```text
sk-1234
```

as the LiteLLM master key.

This is suitable only for local development and testing.

A production deployment should use:

* strong authentication
* secret management
* HTTPS
* access controls
* proper API key management
* network restrictions
* provider-specific security controls

---

# Current Limitations

Phase 1 intentionally has a limited scope.

Currently not implemented:

* Billing
* Token-to-currency conversion
* User quotas
* Budget enforcement
* Production authentication
* Multi-user authorization
* Advanced analytics
* Distributed deployment
* High availability
* Automatic failover between providers
* Production-grade observability
* Production security hardening

The local Qwen model can also be slow when running on CPU.

---

# Phase 1 Goals

The current implementation demonstrates the core architecture required for an AI token economy:

```text
                 ┌──────────────────┐
                 │     User         │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │   FastAPI UI     │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ Model Decider    │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │    LiteLLM       │
                 └────────┬─────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
           Local       External     External
           Models       Models       Models
              │           │           │
              └───────────┼───────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ Raw Token Usage  │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │      MySQL       │
                 └──────────────────┘
```

---

# Roadmap

Future phases can build on this foundation.

### Phase 2 — Token Economy

* Token normalization
* Provider-specific pricing
* Cost calculation
* User budgets
* Usage dashboards
* Token quotas

### Phase 3 — Intelligent Routing

* More advanced task classification
* Model quality scoring
* Latency-aware routing
* Cost-aware routing
* Provider health checks
* Automatic fallback between providers

### Phase 4 — Production Platform

* Authentication and authorization
* Multi-user support
* API key management
* Persistent configuration management
* Monitoring and alerting
* High availability
* Distributed deployment
* Kubernetes support

---

# Technology Stack

| Layer                | Technology                        |
| -------------------- | --------------------------------- |
| Frontend             | HTML / CSS / JavaScript           |
| API                  | FastAPI                           |
| Language             | Python                            |
| AI Gateway           | LiteLLM                           |
| Local Inference      | Ollama                            |
| Local Model          | Qwen 2.5 3B                       |
| External Models      | Gemini, Groq, OpenRouter, Mistral |
| Application Database | MySQL 8                           |
| LiteLLM Database     | PostgreSQL 15                     |
| Containerization     | Docker Compose                    |
| Version Control      | Git / GitHub                      |

---

# Project Status

**Phase 1 — Core Architecture: Active Development**

Current capabilities:

* [x] FastAPI application
* [x] Web-based chat interface
* [x] LiteLLM gateway
* [x] Local Ollama model
* [x] Gemini integration
* [x] Groq integration
* [x] OpenRouter integration
* [x] Mistral integration
* [x] Database-driven routing
* [x] Routing fallback
* [x] Raw token metering
* [x] MySQL application database
* [x] PostgreSQL LiteLLM database
* [x] Docker Compose infrastructure
* [ ] Billing / cost calculation
* [ ] User quotas
* [ ] Production authentication
* [ ] Production deployment

---

## License

This project is currently a private/internal proof of concept.
