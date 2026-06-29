# Maybach

A multi-agent system with four virtual employees — Data Analyst, Product Manager,
Software Engineer, and Data Scientist — coordinated by a hand-rolled supervisor.
Comes with a modern chat UI.

**Built from scratch.** No LangChain, no LangGraph, no agent framework. The whole
harness is ~400 lines of plain Python over a local [Ollama](https://ollama.com)
server: a tiny HTTP client, a `@tool` decorator, a ReAct loop, and an explicit
orchestrator. No API keys, no cloud account, no cost.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) (runs models locally)

---

## 1. Install Ollama and pull a model

The model must support **tool calling**. `llama3.2` does and runs well on most machines.

```bash
# macOS
brew install ollama

# Start the server (leave running in a terminal, or `ollama serve &`)
ollama serve

# Pull a tool-capable model (~2GB)
ollama pull llama3.2
```

> Other tool-capable options: `llama3.1:8b` (stronger), `qwen2.5`, `mistral-nemo`.
> Small models without tool support (e.g. `gemma2:2b`) will route and chat but
> cannot drive the worker tools.

---

## 2. Configure (optional)

Defaults work out of the box. To override, copy the template:

```bash
cp config.yaml.example config.yaml
```

```yaml
ollama:
  model: llama3.2
  base_url: http://localhost:11434
  # router_model: llama3.2   # optional — a smaller model is fine for routing
```

Environment variables take precedence over `config.yaml` (`.env.example` lists them).

---

## 3. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

uvicorn server:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## 4. Frontend

```bash
cd ui
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## CLI (optional)

```bash
python main.py "Write a PRD for a user notification system"
```

---

## Tests

A smoke test fakes the Ollama client and exercises the entire harness — tool
schema generation, the agent ReAct loop, routing, worker streaming, and the
summarizer — with no model or network required:

```bash
python3 tests/test_smoke.py
```

---

## How It Works

Every turn runs a single, loop-free pass:

```
router ─┬─ DIRECT ───────────────► stream reply
        └─ one or more workers ──► summarizer ──► stream reply
```

1. **Router** (`orchestrator.py`) — one LLM call in JSON mode classifies the
   request into `DIRECT` (just answer) or one/more workers.
2. **Workers** — each runs a **ReAct loop** (`core/agent.py`): the model is
   given its tools, calls them, reads the results, and loops until it produces a
   final answer. Output is written to `workspace/` and the path returned.
3. **Summarizer** — reads the workers' files and streams a synthesised reply
   token-by-token to the UI.

| Worker | Role | Tools |
|--------|------|-------|
| vDA | Data Analyst | SQL, Python, workspace |
| vPM | Product Manager | document/spec generators, workspace |
| vSWE | Software Engineer | Python, bash, workspace |
| vDS | Data Scientist | Python, SQL, summarise, workspace |

Workers can write **deliverable** files (`write_file`, kept and shown as
download/preview links in the UI) and **scratch checkpoints** (`save_checkpoint`,
auto-deleted when the task ends). Each worker can also be called directly via
`POST /agents/{name}`.

### The core harness

```
core/
├── llm.py     # Ollama HTTP client — chat() (tool-calling) + stream() (tokens)
├── tools.py   # @tool decorator: typed function → JSON-schema tool spec
└── agent.py   # ReAct loop: call model → run tools → repeat → final answer
```

---

## Project Structure

```
maybach/
├── config.py             # loads config.yaml → OLLAMA_* env vars
├── config.yaml.example   # config template
├── .env.example          # env var template
├── llm.py                # convenience layer over core.llm + text helpers
├── requirements.txt      # pyyaml, httpx, fastapi, uvicorn
├── main.py               # CLI entrypoint
├── orchestrator.py       # hand-rolled supervisor (router → workers → summarizer)
├── server.py             # FastAPI: /orchestrate(/stream), /agents/*, /files/*
├── core/                 # the from-scratch agent harness (see above)
├── agents/               # vda.py, vpm.py, vswe.py, vds.py
├── tools/                # sql_tools, code_tools, research_tools, workspace_tools
├── tests/                # test_smoke.py (no model required)
└── ui/                   # Next.js chat interface (SSE streaming)
```

---

## Adding a tool

Write a typed, documented function and decorate it — the schema is derived
automatically from the signature and docstring:

```python
from core.tools import tool

@tool
def fetch_weather(city: str, units: str = "celsius") -> str:
    """Get the current weather for a city."""
    ...
```

Then add it to a worker's tool list in `agents/<name>.py`.
