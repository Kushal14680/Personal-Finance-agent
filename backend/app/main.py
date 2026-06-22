import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db import db
from app.parser import parse_file_to_text
from app.agent import run_finance_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Personal Finance Agent API")

# Add CORS Middleware to allow requests from the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schemas for request payloads
class ProfileUpdate(BaseModel):
    currency: Optional[str] = None
    savings_goal: Optional[float] = None
    email: Optional[str] = None

@app.get("/")
def read_root():
    return {"message": "Welcome to the Personal Finance Agent API. Backend is up and running!"}

@app.get("/api/profile")
def get_profile(profile_id: str = "00000000-0000-0000-0000-000000000000"):
    """Fetch user profile details (home currency, savings goal)."""
    try:
        profile = db.get_profile(profile_id)
        return profile
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile")
def update_profile(
    payload: ProfileUpdate, 
    profile_id: str = "00000000-0000-0000-0000-000000000000"
):
    """Update profile configuration settings."""
    try:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided to update")
            
        updated = db.update_profile(profile_id, updates)
        return updated
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transactions")
def get_transactions(
    profile_id: str = "00000000-0000-0000-0000-000000000000", 
    limit: int = 100
):
    """Retrieve historical transactions."""
    try:
        transactions = db.get_transactions(profile_id, limit)
        return transactions
    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/briefings")
def get_briefings(
    profile_id: str = "00000000-0000-0000-0000-000000000000",
    month: Optional[str] = None
):
    """Retrieve monthly briefings."""
    try:
        if month:
            briefing = db.get_briefing(profile_id, month)
            return [briefing] if briefing else []
        else:
            # For simplicity, returning a list of briefings in mock / Supabase
            if db.enabled and db.client:
                res = db.client.table("briefings").select("*").eq("profile_id", profile_id).order("month", desc=True).execute()
                return res.data
            else:
                # Mock return
                return list(db._mock_briefings.values())
    except Exception as e:
        logger.error(f"Error fetching briefings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_statement(
    file: UploadFile = File(...),
    profile_id: str = Form("00000000-0000-0000-0000-000000000000")
):
    """
    Ingest statements (CSV, Excel, or PDF), extract text,
    run the LangGraph finance agent, and save output.
    """
    logger.info(f"Received file: {file.filename} for profile: {profile_id}")
    
    try:
        # 1. Parse upload file content to text
        file_bytes = await file.read()
        raw_text = parse_file_to_text(file_bytes, file.filename)
        
        # 2. Get user preferences from DB
        profile = db.get_profile(profile_id)
        currency = profile.get("currency", "GBP")
        savings_goal = float(profile.get("savings_goal", 500.00))
        
        # 3. Get existing transactions for recurring comparisons
        existing_txs = db.get_transactions(profile_id, limit=300)
        
        # 4. Invoke the LangGraph Python Finance Agent
        agent_response = run_finance_agent(
            raw_text=raw_text, 
            existing_txs=existing_txs,
            home_currency=currency,
            savings_goal=savings_goal
        )
        
        # 5. Enrich extracted transactions with profile_id and save to database
        transactions = agent_response.get("transactions", [])
        for tx in transactions:
            tx["profile_id"] = profile_id
            
        db.upsert_transactions(transactions)
        
        # 6. Save the generated monthly briefing
        analysis_data = agent_response.get("analysis", {})
        month = analysis_data.get("month")
        if not month:
            # Fallback to current year-month if agent couldn't extract
            month = datetime.utcnow().strftime("%Y-%m")
            
        briefing_payload = {
            "profile_id": profile_id,
            "month": month,
            "briefing_text": agent_response.get("briefing", ""),
            "analysis": analysis_data
        }
        db.upsert_briefing(briefing_payload)
        
        # Return exact JSON output format required by specifications
        return agent_response
        
    except ValueError as ve:
        logger.error(f"Value error in upload: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Internal server error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process statement: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
