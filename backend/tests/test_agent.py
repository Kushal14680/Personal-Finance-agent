import pytest
from app.agent import (
    generate_tx_id, 
    is_near_identical_recurring, 
    anomaly_detector_node,
    AgentState
)

def test_generate_tx_id():
    tx1 = {"date": "2026-06-01", "description": "TEST 1", "amount": 100.0, "currency": "GBP"}
    tx2 = {"date": "2026-06-01", "description": "TEST 1", "amount": 100.0, "currency": "GBP"}
    tx3 = {"date": "2026-06-01", "description": "TEST 2", "amount": 100.0, "currency": "GBP"}
    
    assert generate_tx_id(tx1) == generate_tx_id(tx2)
    assert generate_tx_id(tx1) != generate_tx_id(tx3)

def test_is_near_identical_recurring():
    # Identical
    tx1 = {"merchant": "Netflix", "amount": 15.99, "date": "2026-04-15"}
    tx2 = {"merchant": "Netflix", "amount": 15.99, "date": "2026-05-15"}
    assert is_near_identical_recurring(tx1, tx2) is True
    
    # Slight amount diff (+-2%)
    tx3 = {"merchant": "Netflix", "amount": 16.20, "date": "2026-05-15"} # +1.3%
    assert is_near_identical_recurring(tx1, tx3) is True
    
    # Large amount diff (>2%)
    tx4 = {"merchant": "Netflix", "amount": 18.00, "date": "2026-05-15"} # +12%
    assert is_near_identical_recurring(tx1, tx4) is False
    
    # Slight date diff (+-5 days)
    tx5 = {"merchant": "Netflix", "amount": 15.99, "date": "2026-05-18"} # 3 days diff
    assert is_near_identical_recurring(tx1, tx5) is True
    
    # Large date diff (>5 days)
    tx6 = {"merchant": "Netflix", "amount": 15.99, "date": "2026-05-25"} # 10 days diff
    assert is_near_identical_recurring(tx1, tx6) is False

def test_anomaly_detector():
    state: AgentState = {
        "raw_text": "",
        "home_currency": "GBP",
        "savings_goal": 500.0,
        "existing_transactions": [
            {"id": "h1", "merchant": "Netflix", "amount": 15.99, "date": "2026-04-15", "category": "entertainment"},
            {"id": "h2", "merchant": "Netflix", "amount": 15.99, "date": "2026-05-15", "category": "entertainment"},
            {"id": "h3", "merchant": "Gym", "amount": 40.00, "date": "2026-04-08", "category": "health"},
            {"id": "h4", "merchant": "Gym", "amount": 40.00, "date": "2026-05-08", "category": "health"},
        ],
        "parsed_transactions": [
            # Regular subscription match
            {"id": "t1", "merchant": "Netflix", "amount": 15.99, "date": "2026-06-15", "category": "entertainment", "confidence": "high"},
            # Price increase subscription (>5%)
            {"id": "t2", "merchant": "Gym", "amount": 45.00, "date": "2026-06-08", "category": "health", "confidence": "high"},
            # Duplicate transactions (within 48 hours, same merchant and amount)
            {"id": "t3", "merchant": "Uber", "amount": 15.40, "date": "2026-06-05", "category": "transport", "confidence": "high"},
            {"id": "t4", "merchant": "Uber", "amount": 15.40, "date": "2026-06-05", "category": "transport", "confidence": "high"},
            # Large debit (compared to median)
            {"id": "t5", "merchant": "Currys PC", "amount": 950.00, "date": "2026-06-18", "category": "shopping", "confidence": "high"},
            # Foreign FX
            {"id": "t6", "merchant": "Adobe", "amount": 45.00, "date": "2026-06-20", "category": "entertainment", "confidence": "high", "currency": "USD"},
            # Low confidence merchant
            {"id": "t7", "merchant": "ZXZX", "amount": 12.50, "date": "2026-06-21", "category": "other", "confidence": "low", "currency": "GBP"},
            # New Subscription
            {"id": "t8", "merchant": "ChatGPT", "amount": 16.00, "date": "2026-06-22", "category": "entertainment", "confidence": "high", "currency": "GBP"},
        ],
        "analysis_results": {},
        "briefing_markdown": "",
        "status": "ok",
        "flags": []
    }
    
    # Run node
    result = anomaly_detector_node(state)
    txs = result["parsed_transactions"]
    
    # Index by ID for easier checks
    txs_by_id = {t["id"]: t for t in txs}
    
    # Checks
    assert txs_by_id["t1"]["is_recurring"] is True
    assert "PRICE_INCREASE" in txs_by_id["t2"]["flags"]
    assert "DUPLICATE" in txs_by_id["t3"]["flags"]
    assert "DUPLICATE" in txs_by_id["t4"]["flags"]
    assert "LARGE_DEBIT" in txs_by_id["t5"]["flags"]
    assert "FOREIGN_FX" in txs_by_id["t6"]["flags"]
    assert "UNKNOWN_MERCHANT" in txs_by_id["t7"]["flags"]
    assert txs_by_id["t8"]["is_recurring"] is False # First month only
