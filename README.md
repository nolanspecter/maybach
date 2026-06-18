# Maybach

A multi-agent system with four virtual employees — Data Analyst, Product Manager, Software Engineer, and Data Scientist — orchestrated by a LangGraph supervisor. Comes with a modern chat UI.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- An LLM provider (Ollama for free local testing, or AWS Bedrock for production)

---

## Option A — Run Free with Ollama (recommended for testing)

No API keys, no account, no cost. Runs entirely on your machine.

### 1. Install Ollama and pull a model

```bash
# macOS
brew install ollama

# Then pull a model (llama3.2 is ~2GB, runs well on most machines)
ollama pull llama3.2

# Start the Ollama server (runs in background)
ollama serve
```

> Other good free models: `mistral`, `gemma2:2b` (smaller/faster), `llama3.1:8b`

### 2. Configure `.env`

```bash
cp .env.example .env
```

The default `.env.example` already points to Ollama — no changes needed:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

---

## Option B — AWS Bedrock (production / Claude models)

### 1. Get AWS credentials

1. Go to [console.aws.amazon.com/iam](https://console.aws.amazon.com/iam) and sign in.
2. Navigate to **Users** → **Create user**.
3. Give it a name (e.g. `maybach-agent`), click **Next**.
4. Select **Attach policies directly** → search **AmazonBedrockFullAccess** → **Create user**.
5. Open the user → **Security credentials** → **Create access key** → download the CSV.

### 2. Enable Claude in Bedrock

1. Go to [console.aws.amazon.com/bedrock](https://console.aws.amazon.com/bedrock).
2. **Model access** → **Modify model access** → check Claude Sonnet → **Save**.

### 3. Configure `.env`

```env
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250514-v1:0
```

---

## Backend Setup

```bash
cd maybach

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt

uvicorn server:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## Frontend Setup

```bash
cd ui
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## CLI (optional)

```bash
# From the maybach/ directory with the venv active
python main.py "Write a PRD for a user notification system"
```

---

## Project Structure

```
maybach/
├── .env                  # Your config (never commit this)
├── .env.example          # Template — defaults to Ollama
├── llm.py                # LLM factory (switches provider via LLM_PROVIDER)
├── requirements.txt      # Python dependencies
├── main.py               # CLI entrypoint
├── orchestrator.py       # LangGraph supervisor graph
├── server.py             # FastAPI server
├── agents/
│   ├── vda.py            # Virtual Data Analyst
│   ├── vpm.py            # Virtual Product Manager
│   ├── vswe.py           # Virtual Software Engineer
│   └── vds.py            # Virtual Data Scientist
├── tools/
│   ├── sql_tools.py      # SQL query execution
│   ├── code_tools.py     # Python / bash execution
│   └── research_tools.py # Document and list generation
└── ui/                   # Next.js chat interface
```

## How It Works

Every task goes through a **router** that picks the right worker(s):

| Worker | Role | Does |
|--------|------|------|
| vDA | Data Analyst | SQL queries, data exploration, metrics |
| vPM | Product Manager | PRDs, specs, roadmaps, backlogs |
| vSWE | Software Engineer | Code, debugging, scripts |
| vDS | Data Scientist | ML models, stats, predictions |

The router can run workers **in parallel** (e.g. vDA + vDS simultaneously) or chain them sequentially. Each worker can also be called independently via `POST /agents/{name}`.
