# FinSense: Autonomous AI Personal Finance Agent 🚀

[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.138-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Python-blue?style=flat-square&logo=chainlink)](https://github.com/langchain-ai/langgraph)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=flat-square&logo=openai)](https://openai.com/)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?style=flat-square&logo=supabase)](https://supabase.com/)

**FinSense** is an autonomous personal finance agent and dashboard. It ingests banking statements (in PDF, CSV, or Excel formats), cleans and categorises transactions using LLMs, runs deterministic rule engines to audit subscriptions and track anomalies, and constructs detailed savings analytics alongside a concise markdown monthly briefing.

---

## 🏗️ System Architecture

```
                 +-----------------------------------+
                 |        Next.js Frontend           |
                 |     (KPIs, Briefing, Charts)      |
                 +-----------------+-----------------+
                                   |
                                   | (Uploads statement file)
                                   v
                 +-----------------+-----------------+
                 |         FastAPI Backend           |
                 |       (API Endpoints & Routing)   |
                 +-----------------+-----------------+
                                   |
                                   | (Triggers StateGraph)
                                   v
                 +-----------------+-----------------+
                 |       LangGraph Finance Agent     |
                 |                                   |
                 |  [Node 1: Extract & Cleanse]      |
                 |  [Node 2: Deterministic Anomalies]|
                 |  [Node 3: Category MoM Budget]    |
                 |  [Node 4: Draft Briefing Summaries|
                 +--------+-----------------+--------+
                          |                 |
                          | (Inferences)    | (Saves profile, data, & briefs)
                          v                 v
                 +--------+-------+ +-------+--------+
                 |   OpenAI GPT   | |  Supabase Cloud|
                 +----------------+ +----------------+
```

---

## ✨ Features

* **File Normalisation**: Unified parsing of CSV, XLS, XLSX, and PDF statement files.
* **Intelligent Taxonomy Mapping**: Maps all incoming transactions into one of 10 standard categories (`housing`, `food`, `transport`, `health`, `entertainment`, `shopping`, `finance`, `income`, `transfer`, `other`) using OpenAI Structured Outputs with high/medium/low confidence assessments.
* **Deterministic Anomaly & Subscription Engine**: 
  - `NEW_SUBSCRIPTION` → Identifies recurring expenses starting this month.
  - `PRICE_INCREASE` → Flags subscriptions that went up in price by >5% MoM.
  - `DUPLICATE` → Flags charges from the same merchant with the same amount within 48 hours.
  - `LARGE_DEBIT` → Catches individual charges exceeding 3x the user's median debit.
  - `FOREIGN_FX` → Flags currency variances from the home currency settings.
  - `UNKNOWN_MERCHANT` → Flags items mapped to "other" due to low LLM confidence.
* **Savings Analytics**: Measures MoM category expenditure trends, subscription monthly burn totals, and savings rate comparisons.
* **Ranked Savings Opportunities**: Structured LLM savings strategies, ranking actions by monetary impact and rating required effort.
* **Monthly Briefing**: Generates a clean markdown briefing under 350 words detailing core numbers, observations, active warnings, and key moves.

---

## 🚀 Quickstart Guide

### 1. Database Setup (Supabase)
1. Register a project on [Supabase](https://supabase.com).
2. Open the **SQL Editor** in the Supabase control panel.
3. Paste and run the commands in [`supabase/schema.sql`](file:///c:/Users/kusha/Desktop/projects/Personal%20Finance%20agent/supabase/schema.sql) to set up tables (`profiles`, `transactions`, `briefings`), indexes, and RLS security policies.

### 2. Backend Installation & Startup
The backend utilizes **`uv`** to build the virtual environment and manage dependencies.
1. Open a terminal inside the `/backend` folder.
2. Create your configuration env file:
   ```bash
   cp .env.example .env
   ```
3. Add your `OPENAI_API_KEY`. (Optional: Add `SUPABASE_URL` and `SUPABASE_KEY`. If left empty, the server automatically starts using an **in-memory database pre-loaded with mock transaction history** for immediate developer validation).
4. Run the development server:
   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```

### 3. Frontend Installation & Startup
1. Open a terminal inside the `/frontend` folder.
2. Install npm modules:
   ```bash
   npm install
   ```
3. Launch the Next.js development server:
   ```bash
   npm run dev
   ```
4. Access the dashboard at `http://localhost:3000`.

---

## 🧪 Verification & Demo

### Run Backend Unit Tests
Run standard pytest assertions on recurrence matching, price increases, duplicates, and currency conversions:
```bash
cd backend
uv run pytest -o pythonpath=.
```

### Ingestion Validation
To test end-to-end processing, click **Import Statement** in the UI and select the pre-built mock file: [`/test_statements/statement_june_2026.csv`](file:///c:/Users/kusha/Desktop/projects/Personal%20Finance%20agent/test_statements/statement_june_2026.csv).

---

## 📦 Deployment Instructions

### 1. Deploy Backend (Render)
1. Deploy a new **Web Service** on [Render](https://render.com) pointing to your repo.
2. Select `Python` runtime, set Root Directory to `backend`.
3. Generate `requirements.txt` before deploying:
   ```bash
   uv pip compile pyproject.toml -o requirements.txt
   ```
4. Configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Map env values: `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.

### 2. Deploy Frontend (Vercel)
1. Deploy a new project on [Vercel](https://vercel.com) pointing to `/frontend`.
2. Add environment variable `NEXT_PUBLIC_API_URL` pointing to your deployed Render URL.
