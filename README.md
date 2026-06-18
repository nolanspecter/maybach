# Maybach

A multi-agent system with four virtual employees — Data Analyst, Product Manager, Software Engineer, and Data Scientist — orchestrated by a LangGraph supervisor. Comes with a modern chat UI.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- An Anthropic API key

---

## 1. Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com) and sign in (or create an account).
2. Navigate to **API Keys** in the left sidebar.
3. Click **Create Key**, give it a name, and copy the key — it starts with `sk-ant-...`.
4. Store it somewhere safe; you won't be able to view it again.

---

## 2. Backend Setup

```bash
# Clone / enter the project
cd maybach

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp .env.example .env
```

Open `.env` and paste your key:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Start the API server:

```bash
uvicorn server:app --reload --port 8000
```

The server is ready when you see `Uvicorn running on http://127.0.0.1:8000`.

You can verify it with:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## 3. Frontend Setup

```bash
cd ui
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## 4. CLI (optional)

You can also run tasks directly from the terminal without the UI:

```bash
# From the maybach/ directory with the venv active
python main.py "Write a PRD for a user notification system"
```

---

## Project Structure

```
maybach/
├── .env                  # Your API key (never commit this)
├── .env.example          # Template
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

Every task goes through a **router** that picks the right worker:

| Worker | Role | Does |
|--------|------|------|
| vDA | Data Analyst | SQL queries, data exploration, metrics |
| vPM | Product Manager | PRDs, specs, roadmaps, backlogs |
| vSWE | Software Engineer | Code, debugging, scripts |
| vDS | Data Scientist | ML models, stats, predictions |

The router can chain workers — e.g., vPM writes a spec then vSWE implements it.
