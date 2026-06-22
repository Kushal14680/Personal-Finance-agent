import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

class DatabaseHelper:
    def __init__(self):
        self.enabled = bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)
        self.client: Optional[Client] = None
        
        # Local mock DB state for when Supabase is not configured
        self._mock_profiles = {
            "00000000-0000-0000-0000-000000000000": {
                "id": "00000000-0000-0000-0000-000000000000",
                "email": "local.user@example.com",
                "currency": "GBP",
                "savings_goal": 500.00
            }
        }
        self._mock_transactions = [
            # April 2026
            {"id": "hist-1", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-04-01", "description": "STANDING ORDER RENT", "merchant": "Landlord Rent", "amount": 1200.00, "currency": "GBP", "category": "housing", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-2", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-04-08", "description": "GYM MEMBERSHIP ACT", "merchant": "Gym Membership", "amount": 40.00, "currency": "GBP", "category": "health", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-3", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-04-12", "description": "SPOTIFY PREMIUM STOCKHOLM", "merchant": "Spotify", "amount": 10.99, "currency": "GBP", "category": "entertainment", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-4", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-04-15", "description": "NETFLIX.COM CARD", "merchant": "Netflix", "amount": 15.99, "currency": "GBP", "category": "entertainment", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-5", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-04-28", "description": "TESCO GROCERIES", "merchant": "Tesco", "amount": 45.50, "currency": "GBP", "category": "food", "confidence": "high", "is_recurring": False, "flags": []},
            # May 2026
            {"id": "hist-6", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-05-01", "description": "STANDING ORDER RENT", "merchant": "Landlord Rent", "amount": 1200.00, "currency": "GBP", "category": "housing", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-7", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-05-08", "description": "GYM MEMBERSHIP ACT", "merchant": "Gym Membership", "amount": 40.00, "currency": "GBP", "category": "health", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-8", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-05-12", "description": "SPOTIFY PREMIUM STOCKHOLM", "merchant": "Spotify", "amount": 10.99, "currency": "GBP", "category": "entertainment", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-9", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-05-15", "description": "NETFLIX.COM CARD", "merchant": "Netflix", "amount": 15.99, "currency": "GBP", "category": "entertainment", "confidence": "high", "is_recurring": True, "flags": []},
            {"id": "hist-10", "profile_id": "00000000-0000-0000-0000-000000000000", "date": "2026-05-25", "description": "TESCO GROCERIES", "merchant": "Tesco", "amount": 52.30, "currency": "GBP", "category": "food", "confidence": "high", "is_recurring": False, "flags": []},
        ]
        self._mock_briefings = {}

        if self.enabled:
            try:
                self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                logger.info("Successfully connected to Supabase.")
            except Exception as e:
                logger.error(f"Failed to connect to Supabase: {e}. Falling back to mock database.")
                self.enabled = False
        else:
            logger.warning("Supabase URL or Key not set. Running with local in-memory mock database.")

    def get_profile(self, profile_id: str) -> Dict[str, Any]:
        """Fetch user profile details."""
        if self.enabled and self.client:
            try:
                res = self.client.table("profiles").select("*").eq("id", profile_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Error fetching profile from Supabase: {e}")
        
        # Return fallback or local mock profile
        if profile_id not in self._mock_profiles:
            self._mock_profiles[profile_id] = {
                "id": profile_id,
                "email": "user@example.com",
                "currency": "GBP",
                "savings_goal": 500.00
            }
        return self._mock_profiles[profile_id]

    def update_profile(self, profile_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile settings (currency, savings goal)."""
        if self.enabled and self.client:
            try:
                # Supabase table update
                res = self.client.table("profiles").update(updates).eq("id", profile_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Error updating profile in Supabase: {e}")
        
        # Local mock update
        profile = self.get_profile(profile_id)
        profile.update(updates)
        self._mock_profiles[profile_id] = profile
        return profile

    def get_transactions(self, profile_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch transactions for a profile."""
        if self.enabled and self.client:
            try:
                res = (self.client.table("transactions")
                       .select("*")
                       .eq("profile_id", profile_id)
                       .order("date", desc=True)
                       .limit(limit)
                       .execute())
                return res.data
            except Exception as e:
                logger.error(f"Error fetching transactions from Supabase: {e}")
        
        # Local mock fetch (sorted by date desc)
        filtered = [t for t in self._mock_transactions if t["profile_id"] == profile_id]
        filtered.sort(key=lambda x: x["date"], reverse=True)
        return filtered[:limit]

    def upsert_transactions(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert or update a list of transactions."""
        if not transactions:
            return []
            
        if self.enabled and self.client:
            try:
                res = self.client.table("transactions").upsert(transactions).execute()
                return res.data
            except Exception as e:
                logger.error(f"Error upserting transactions to Supabase: {e}")
        
        # Local mock upsert
        for tx in transactions:
            # Check for existing tx by ID
            existing_idx = next((i for i, t in enumerate(self._mock_transactions) if t["id"] == tx["id"]), None)
            if existing_idx is not None:
                self._mock_transactions[existing_idx] = tx
            else:
                self._mock_transactions.append(tx)
        return transactions

    def get_briefing(self, profile_id: str, month: str) -> Optional[Dict[str, Any]]:
        """Fetch monthly briefing details."""
        if self.enabled and self.client:
            try:
                res = (self.client.table("briefings")
                       .select("*")
                       .eq("profile_id", profile_id)
                       .eq("month", month)
                       .execute())
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"Error fetching briefing from Supabase: {e}")
        
        # Local mock fetch
        key = f"{profile_id}:{month}"
        return self._mock_briefings.get(key)

    def upsert_briefing(self, briefing: Dict[str, Any]) -> Dict[str, Any]:
        """Save a monthly briefing."""
        if self.enabled and self.client:
            try:
                res = self.client.table("briefings").upsert(briefing).execute()
                return res.data[0]
            except Exception as e:
                logger.error(f"Error upserting briefing to Supabase: {e}")
        
        # Local mock upsert
        profile_id = briefing["profile_id"]
        month = briefing["month"]
        key = f"{profile_id}:{month}"
        self._mock_briefings[key] = briefing
        return briefing

db = DatabaseHelper()
