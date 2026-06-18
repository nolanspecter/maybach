# Maybach

A multi-agent system with four virtual employees — Data Analyst, Product Manager, Software Engineer, and Data Scientist — orchestrated by a LangGraph supervisor. Comes with a modern chat UI.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- An AWS account with Bedrock access

---

## 1. Get AWS Credentials & Enable Bedrock

### Create an IAM user with Bedrock access

1. Go to [console.aws.amazon.com/iam](https://console.aws.amazon.com/iam) and sign in.
2. Navigate to **Users** → **Create user**.
3. Give it a name (e.g. `maybach-agent`), click **Next**.
4. Select **Attach policies directly** and search for **AmazonBedrockFullAccess** → check it → **Next** → **Create user**.
5. Open the user → **Security credentials** tab → **Create access key**.
6. Select **Application running outside AWS**, click through, and **download the CSV** or copy both keys.

### Enable Claude model access in Bedrock

1. Go to [console.aws.amazon.com/bedrock](https://console.aws.amazon.com/bedrock).
2. In the left sidebar click **Model access** → **Modify model access**.
3. Check the Claude models you want (Claude Sonnet recommended) → **Save changes**.
4. Wait a few minutes for access to be approved (usually instant for Claude).

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

# Configure your credentials
cp .env.example .env
```

Open `.env` and fill in your AWS keys:

```env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250514-v1:0
```

> **Region note:** Claude models on Bedrock are available in `us-east-1` and `us-west-2`. The `us.` prefix in the model ID enables cross-region inference for higher throughput.

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
