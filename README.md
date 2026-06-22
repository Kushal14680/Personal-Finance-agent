# FinSense: AI-Powered Personal Finance Agent

FinSense is an autonomous personal finance dashboard. It ingests bank statements (CSV, PDF, or Excel), normalises the transaction schemas, determines recurring subscription structures, detects transaction anomalies (e.g. price increases, duplicates, foreign FX, large debits), computes detailed category budgets/savings rate indicators, and generates a concise, data-backed monthly saving briefing.

## Architecture

The project is structured as a multi-service monorepo:
* **`/backend`**: Unified Python FastAPI backend server executing a **LangGraph** finance agent managed with **`uv`**.
* **`/frontend`**: React web application built with **Next.js 15** utilizing premium custom Vanilla CSS (dark-mode glassmorphism) and **Recharts**.
* **`/supabase`**: Schema design scripts for setup on Supabase (Postgres).
* **`/test_statements`**: Ready-to-use mock statement files to test the pipeline.

---

## Getting Started

### 1. Database Setup (Supabase)
1. Create a free project on [Supabase](https://supabase.com).
2. Go to the **SQL Editor** in your Supabase dashboard.
3. Paste the contents of [`/supabase/schema.sql`](file:///c:/Users/kusha/Desktop/projects/Personal%20Finance%20agent/supabase/schema.sql) and execute the query. This will construct the tables (`profiles`, `transactions`, `briefings`) and set up development indexes.

### 2. Backend Configuration & Start
The backend uses **`uv`** for dependency and environment management.
1. Open a terminal inside the `/backend` folder.
2. Create a `.env` file by copying the template:
   ```bash
   cp .env.example .env
   ```
3. Populate `.env` with your `OPENAI_API_KEY`. (Optional: Add `SUPABASE_URL` and `SUPABASE_KEY` if you want persistent storage; otherwise, the server gracefully falls back to an **in-memory database** pre-loaded with sample history!).
4. Run the FastAPI development server:
   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```
   The API will be available at `http://localhost:8000`.

### 3. Frontend Configuration & Start
1. Open a terminal inside the `/frontend` folder.
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   The web dashboard will be available at `http://localhost:3000`.

---

## Testing & Verification

### Run Unit Tests
To verify transaction recurrence matching, price increases, large debits, duplicates, and foreign FX checks:
1. Navigate to `/backend`.
2. Run pytest:
   ```bash
   uv run pytest -o pythonpath=.
   ```

### Try Ingesting a Statement
1. Open `http://localhost:3000`.
2. Click **Import Statement** in the top right.
3. Select or drag-and-drop the pre-created test statement: [`/test_statements/statement_june_2026.csv`](file:///c:/Users/kusha/Desktop/projects/Personal%20Finance%20agent/test_statements/statement_june_2026.csv).
4. Watch the agent normalize, flag anomalies, audit subscriptions, and draft your monthly briefing!
