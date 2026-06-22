import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, TypedDict, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from langgraph.graph import StateGraph, END

from app.config import settings

logger = logging.getLogger(__name__)

# State definition
class AgentState(TypedDict):
    raw_text: str
    home_currency: str
    savings_goal: float
    existing_transactions: List[Dict[str, Any]]
    parsed_transactions: List[Dict[str, Any]]
    analysis_results: Dict[str, Any]
    briefing_markdown: str
    status: str  # "ok" | "needs_review" | "alert"
    flags: List[str]

# Structured output schemas for OpenAI
class ExtractedTransaction(BaseModel):
    date: str = Field(description="Date in YYYY-MM-DD format. If date is not clear, infer from context or leave empty.")
    description: str = Field(description="Original description text from statement.")
    merchant: str = Field(description="Cleaned, recognizable merchant name (e.g. 'Uber' instead of 'UBER *TRIP HELP.UBER.COM').")
    amount: float = Field(description="Positive number for debit/spending, negative number for credit/income.")
    currency: str = Field(description="Three letter currency code (e.g. GBP, USD, EUR).")
    category: str = Field(description="Category mapping: housing, food, transport, health, entertainment, shopping, finance, income, transfer, other")
    confidence: str = Field(description="Confidence of categorization: 'high' (well-known mapping), 'medium' (probable mapping), 'low' (cannot classify cleanly)")

class ExtractedTransactionList(BaseModel):
    transactions: List[ExtractedTransaction]

class MerchantMapping(BaseModel):
    description: str = Field(description="Original description or merchant keyword sent in request")
    merchant: str = Field(description="Cleaned, recognizable merchant name")
    category: str = Field(description="Category from taxonomy: housing, food, transport, health, entertainment, shopping, finance, income, transfer, other")
    confidence: str = Field(description="Confidence rating: high, medium, low")

class MerchantMappingList(BaseModel):
    mappings: List[MerchantMapping]

class Opportunity(BaseModel):
    action: str = Field(description="Specific actionable advice (e.g., 'Cancel your unused Netflix subscription')")
    saving: float = Field(description="Exact monthly savings amount in user's home currency")
    effort: str = Field(description="Low, Medium, or High effort required")
    evidence: str = Field(description="Direct reference to user's transaction data (e.g., 'Netflix charged £15.99 on 2026-06-15')")

class AnalysisOpportunities(BaseModel):
    opportunities: List[Opportunity]
    patterns: List[str] = Field(description="Pattern observations like delivery overuse, cafe spending spikes, weekday spikes, etc.")

# Sub-helpers
def generate_tx_id(tx: Dict[str, Any]) -> str:
    """Generate a unique deterministic hash for a transaction if no ID is present."""
    payload = f"{tx.get('date', '')}:{tx.get('description', '')}:{tx.get('amount', 0.0)}:{tx.get('currency', 'GBP')}"
    return hashlib.md5(payload.encode('utf-8')).hexdigest()

def is_near_identical_recurring(tx1: Dict[str, Any], tx2: Dict[str, Any], allow_increase: bool = False) -> bool:
    """
    Check if two transactions are near-identical (recurring):
    - Merchant matches closely (case-insensitive containment or match)
    - Amount is within +-2% (or up to +-20% if allow_increase is True)
    - Day of month is within +-5 days
    """
    m1 = tx1.get("merchant", "").lower().strip()
    m2 = tx2.get("merchant", "").lower().strip()
    
    # Merchant check: direct match or substring
    if m1 not in m2 and m2 not in m1:
        return False
        
    # Amount check
    a1 = abs(float(tx1.get("amount", 0.0)))
    a2 = abs(float(tx2.get("amount", 0.0)))
    if a1 == 0 or a2 == 0:
        return False
        
    if allow_increase:
        # Allow price difference up to 20% to capture price increases
        if abs(a1 - a2) / max(a1, a2) > 0.20:
            return False
    else:
        # Standard strict check
        if abs(a1 - a2) / max(a1, a2) > 0.02:
            return False
        
    # Day-of-month check: within 5 days
    try:
        d1 = datetime.strptime(tx1.get("date", ""), "%Y-%m-%d")
        d2 = datetime.strptime(tx2.get("date", ""), "%Y-%m-%d")
        
        # We check the absolute day difference. To handle wrap-around (e.g., 28th and 2nd),
        # we check the day difference modulo 30, or simpler:
        day_diff = abs(d1.day - d2.day)
        if day_diff > 5 and day_diff < 25:
            return False
    except Exception:
        return False
        
    return True

# 1. Parse and extract node (using LLM structured output)
def parse_and_extract_node(state: AgentState) -> Dict[str, Any]:
    # Check if tabular transactions have already been pre-parsed (via pandas)
    if state.get("parsed_transactions"):
        txs = state["parsed_transactions"]
        unique_descriptions = list(set(t["description"] for t in txs if t.get("description")))
        logger.info(f"parse_and_extract_node: Already have {len(txs)} pre-parsed transactions. Processing {len(unique_descriptions)} unique descriptions via LLM batch categoriser.")
        
        if not unique_descriptions:
            return {"parsed_transactions": []}
            
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        batch_size = 30
        mappings = {}
        
        for i in range(0, len(unique_descriptions), batch_size):
            batch = unique_descriptions[i:i + batch_size]
            prompt = f"""
For each of the following raw bank transaction descriptions, return a cleaned merchant name, a category from the taxonomy list, and your confidence.

TAXPONOMY LIST:
  housing       [rent, mortgage, utilities, insurance]
  food          [groceries, restaurants, cafes, delivery]
  transport     [fuel, public_transit, ride_share, parking]
  health        [pharmacy, gym, medical, dental]
  entertainment [streaming, gaming, events, hobbies]
  shopping      [clothing, electronics, household, personal]
  finance       [bank_fees, interest, investments, tax]
  income        [salary, freelance, refund, transfer_in]
  transfer      [inter_account, savings_deposit]
  other         [unclassifiable — always select this if you are not sure]

CONFIDENCE RULES:
  HIGH   -> Clear description maps to a merchant in that category.
  MEDIUM -> Probable category but some ambiguity.
  LOW    -> Unclassifiable (category must be set to "other").

Descriptions:
{json.dumps(batch, indent=2)}
"""
            try:
                completion = client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful merchant categorisation mapping system."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=MerchantMappingList,
                    timeout=35.0
                )
                for m in completion.choices[0].message.parsed.mappings:
                    mappings[m.description] = m.model_dump()
            except Exception:
                logger.exception("Error during batch merchant categorisation call")
                for desc in batch:
                    mappings[desc] = {
                        "description": desc,
                        "merchant": desc,
                        "category": "other",
                        "confidence": "low"
                    }
                    
        # Map mappings back to all transactions
        enriched_txs = []
        for tx in txs:
            desc = tx.get("description", "Unknown")
            mapping = mappings.get(desc, {
                "merchant": desc,
                "category": "other",
                "confidence": "low"
            })
            
            tx_enriched = tx.copy()
            tx_enriched["id"] = generate_tx_id(tx_enriched)
            tx_enriched["merchant"] = mapping.get("merchant", desc)
            
            cat = mapping.get("category", "other")
            conf = mapping.get("confidence", "low")
            
            if conf.lower() == "medium":
                if not cat.endswith("?"):
                    cat = f"{cat}?"
            elif conf.lower() == "low":
                cat = "other"
                
            tx_enriched["category"] = cat
            tx_enriched["confidence"] = conf
            tx_enriched["is_recurring"] = False
            tx_enriched["flags"] = []
            
            enriched_txs.append(tx_enriched)
            
        return {"parsed_transactions": enriched_txs}

    # PDF / Unstructured Text Workflow
    raw_text = state.get('raw_text', '')
    logger.info(f"Starting parse_and_extract_node... Raw text size: {len(raw_text)} characters")
    
    if len(raw_text) > 60000:
        logger.warning(f"Raw text is too large ({len(raw_text)} chars). Truncating to 60000 characters to prevent API timeout.")
        raw_text = raw_text[:60000] + "\n...[TRUNCATED FOR SIZE]..."
        
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    prompt = f"""
You are a transaction extraction expert. Extract all financial transactions from the following raw statement text.
Format them to the requested schema.

TAXPONOMY RULES:
Categorise every transaction into exactly one of these:
  housing       [rent, mortgage, utilities, insurance]
  food          [groceries, restaurants, cafes, delivery]
  transport     [fuel, public_transit, ride_share, parking]
  health        [pharmacy, gym, medical, dental]
  entertainment [streaming, gaming, events, hobbies]
  shopping      [clothing, electronics, household, personal]
  finance       [bank_fees, interest, investments, tax]
  income        [salary, freelance, refund, transfer_in]
  transfer      [inter_account, savings_deposit]
  other         [unclassifiable — always select this if you are not sure]

CONFIDENCE RULES:
  HIGH   -> If the description maps very clearly to a merchant in that category.
  MEDIUM -> If it is likely but there is some ambiguity.
  LOW    -> If it is unclassifiable (must set category to "other").

Raw Statement Text:
{raw_text}
"""

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise financial transaction parser."},
                {"role": "user", "content": prompt}
            ],
            response_format=ExtractedTransactionList,
            timeout=45.0
        )
        extracted = completion.choices[0].message.parsed.transactions
    except Exception as e:
        logger.exception("Error calling OpenAI API during transaction extraction")
        extracted = []

    # Map pydantic list to standard dicts, applying IDs and default confidence overrides
    parsed_txs = []
    for tx in extracted:
        tx_dict = tx.model_dump()
        tx_dict["id"] = generate_tx_id(tx_dict)
        
        # Taxonony/Confidence Rules:
        # Confidence rules:
        # HIGH   → categorise silently
        # MEDIUM → categorise, append "?" for user review
        # LOW    → set category = "other", always flag
        if tx_dict["confidence"].lower() == "medium":
            if not tx_dict["category"].endswith("?"):
                tx_dict["category"] = f"{tx_dict['category']}?"
        elif tx_dict["confidence"].lower() == "low":
            tx_dict["category"] = "other"
            
        tx_dict["is_recurring"] = False # computed in next node
        tx_dict["flags"] = []           # computed in next node
        parsed_txs.append(tx_dict)
        
    return {"parsed_transactions": parsed_txs}

# 2. Anomaly detector node
def anomaly_detector_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting anomaly_detector_node...")
    new_txs = state["parsed_transactions"]
    all_historical = state["existing_transactions"]
    home_currency = state["home_currency"]
    
    # Calculate median debit amount across all historical and new debits
    debits = [abs(t["amount"]) for t in (new_txs + all_historical) if t["amount"] > 0 and t["category"].replace("?", "") != "income"]
    
    if debits:
        debits.sort()
        n = len(debits)
        if n % 2 == 1:
            median_debit = debits[n // 2]
        else:
            median_debit = (debits[n // 2 - 1] + debits[n // 2]) / 2.0
    else:
        median_debit = 0.0

    # Determine recurring transactions using the 3-month rule:
    # A transaction is recurring if a near-identical merchant and amount appears in at least 2 of the last 3 months
    updated_txs = []
    
    for tx in new_txs:
        tx_flags = []
        is_rec = False
        
        # Check recurring against other transactions (both historical and new)
        match_count = 0
        matching_past_txs = []
        
        # Combine all to find matches
        all_txs_pool = all_historical + [t for t in new_txs if t["id"] != tx["id"]]
        for past in all_txs_pool:
            if is_near_identical_recurring(tx, past, allow_increase=True):
                match_count += 1
                matching_past_txs.append(past)
        
        # Recurring if we have at least 2 matching months in the past/pool
        # (meaning at least 2 distinct previous months contain it)
        distinct_months = set()
        for m_tx in matching_past_txs:
            try:
                dt = datetime.strptime(m_tx["date"], "%Y-%m-%d")
                distinct_months.add(f"{dt.year}-{dt.month}")
            except Exception:
                pass
                
        if len(distinct_months) >= 2:
            is_rec = True
            tx["is_recurring"] = True
            
            # Check NEW_SUBSCRIPTION: recurring charge not seen in prior months
            # This means we see it now, but we have no matching historical transaction in previous months
            past_matches_historical = [p for p in matching_past_txs if p in all_historical]
            if not past_matches_historical:
                tx_flags.append("NEW_SUBSCRIPTION")
                
            # Check PRICE_INCREASE: same subscription, amount up more than 5% vs average/previous recurring amounts
            if past_matches_historical:
                avg_past_amount = sum(abs(p["amount"]) for p in past_matches_historical) / len(past_matches_historical)
                current_amount = abs(tx["amount"])
                if avg_past_amount > 0 and (current_amount - avg_past_amount) / avg_past_amount > 0.05:
                    tx_flags.append("PRICE_INCREASE")
                    
        # Check DUPLICATE: same merchant and amount within 48 hours
        try:
            tx_dt = datetime.strptime(tx["date"], "%Y-%m-%d")
            for other_tx in new_txs:
                if other_tx["id"] == tx["id"]:
                    continue
                if other_tx["merchant"].lower().strip() == tx["merchant"].lower().strip() and abs(other_tx["amount"] - tx["amount"]) < 0.01:
                    other_dt = datetime.strptime(other_tx["date"], "%Y-%m-%d")
                    if abs((tx_dt - other_dt).total_seconds()) <= 172800: # 48 hours in seconds
                        if "DUPLICATE" not in tx_flags:
                            tx_flags.append("DUPLICATE")
        except Exception:
            pass
            
        # Check LARGE_DEBIT: single charge more than 3x the user's median debit
        if tx["amount"] > 0 and tx["category"].replace("?", "") != "income":
            if median_debit > 0 and tx["amount"] > 3 * median_debit:
                tx_flags.append("LARGE_DEBIT")
                
        # Check FOREIGN_FX: currency differs from user's home currency
        tx_currency = tx.get("currency", home_currency) or home_currency
        if tx_currency.upper() != home_currency.upper():
            tx_flags.append("FOREIGN_FX")
            
        # Check UNKNOWN_MERCHANT: confidence = low (category set to 'other')
        if tx["category"].replace("?", "") == "other" or tx.get("confidence", "").lower() == "low":
            tx_flags.append("UNKNOWN_MERCHANT")
            
        tx["is_recurring"] = is_rec
        tx["flags"] = tx_flags
        updated_txs.append(tx)
        
    return {"parsed_transactions": updated_txs}

# 3. Analyzer node
def analyzer_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting analyzer_node...")
    new_txs = state["parsed_transactions"]
    all_historical = state["existing_transactions"]
    savings_goal = state["savings_goal"]
    home_currency = state["home_currency"]
    
    # 1. Group transactions by month
    all_txs = all_historical + new_txs
    txs_by_month = {}
    for tx in all_txs:
        try:
            m = tx["date"][:7] # YYYY-MM
            if m not in txs_by_month:
                txs_by_month[m] = []
            txs_by_month[m].append(tx)
        except Exception:
            pass
            
    months_sorted = sorted(txs_by_month.keys())
    if not months_sorted:
        return {"analysis_results": {}}
        
    current_month = months_sorted[-1]
    prev_month = months_sorted[-2] if len(months_sorted) > 1 else None
    
    # Calculate Income and Debits for Current Month
    curr_txs = txs_by_month[current_month]
    
    income = sum(abs(t["amount"]) for t in curr_txs if t["amount"] < 0 or t["category"].replace("?", "") == "income")
    debits = sum(t["amount"] for t in curr_txs if t["amount"] > 0 and t["category"].replace("?", "") != "income")
    
    # MoM change calculations
    prev_debits = 0.0
    if prev_month:
        prev_txs = txs_by_month[prev_month]
        prev_debits = sum(t["amount"] for t in prev_txs if t["amount"] > 0 and t["category"].replace("?", "") != "income")
        
    mom_pct = 0.0
    if prev_debits > 0:
        mom_pct = ((debits - prev_debits) / prev_debits) * 100.0
        
    # Savings Rate: (income - total debits) / income
    savings = income - debits
    savings_rate = (savings / income) if income > 0 else 0.0
    
    # Category Breakdown
    cat_totals = {}
    for t in curr_txs:
        if t["amount"] > 0 and t["category"].replace("?", "") != "income":
            c = t["category"].replace("?", "") # Strip review symbol
            cat_totals[c] = cat_totals.get(c, 0.0) + t["amount"]
            
    # Calculate 3-month averages for categories
    # Take last 3 months
    last_3_months = months_sorted[-3:]
    cat_history = {} # cat -> [month1_total, month2_total, ...]
    
    for m in last_3_months:
        m_txs = txs_by_month[m]
        m_totals = {}
        for t in m_txs:
            if t["amount"] > 0 and t["category"].replace("?", "") != "income":
                c = t["category"].replace("?", "")
                m_totals[c] = m_totals.get(c, 0.0) + t["amount"]
        for c, tot in m_totals.items():
            if c not in cat_history:
                cat_history[c] = []
            cat_history[c].append(tot)
            
    cat_breakdown = {}
    for cat, curr_total in cat_totals.items():
        history = cat_history.get(cat, [curr_total])
        avg_3m = sum(history) / len(history)
        pct_of_income = (curr_total / income * 100.0) if income > 0 else 0.0
        
        # MoM category total change
        prev_cat_tot = 0.0
        if prev_month:
            prev_cat_tot = sum(t["amount"] for t in txs_by_month[prev_month] if t["amount"] > 0 and t["category"].replace("?", "") == cat)
        cat_mom_pct = ((curr_total - prev_cat_tot) / prev_cat_tot * 100.0) if prev_cat_tot > 0 else 0.0
        
        flag_high = False
        if curr_total > 1.2 * avg_3m and len(history) > 1:
            flag_high = True # flag if >20% above average
            
        cat_breakdown[cat] = {
            "total": round(curr_total, 2),
            "pct_of_income": round(pct_of_income, 2),
            "mom_change_pct": round(cat_mom_pct, 2),
            "three_month_avg": round(avg_3m, 2),
            "flagged_high": flag_high
        }
        
    # Subscription audit
    subscriptions = []
    sub_burn = 0.0
    for t in curr_txs:
        if t.get("is_recurring", False) and t["amount"] > 0:
            subscriptions.append({
                "merchant": t["merchant"],
                "amount": t["amount"],
                "flagged": len(t.get("flags", [])) > 0,
                "flags": t.get("flags", [])
            })
            sub_burn += t["amount"]
            
    # LLM-powered Savings opportunities and pattern detection
    # Format transactions and numeric breakdowns into text for LLM context
    tx_list_str = "\n".join([f"- {t['date']}: {t['merchant']} ({t['category']}) - {home_currency} {t['amount']} (Flags: {', '.join(t.get('flags', []))})" for t in curr_txs])
    
    llm_prompt = f"""
You are a financial analyst. Based on the user's spending data and categories below, perform:
1. Pattern detection (e.g. delivery overuse >= 4 orders/week, cafe spending > £60/month, overdraft fees, duplicate subscriptions, spending spikes by weekday).
2. Rank top saving opportunities.

User Monthly Goal: Save {home_currency} {savings_goal} (Current Month Saved: {home_currency} {savings:.2f})
Monthly Income: {home_currency} {income:.2f}
Total Debits/Spent: {home_currency} {debits:.2f}
Home Currency: {home_currency}

Category breakdown:
{json.dumps(cat_breakdown, indent=2)}

Transactions:
{tx_list_str}

Rules for opportunities:
- Every recommendation must name the exact merchant or category, the exact saving amount, and the exact action to take.
- Never say "consider" or "you might want to". Give specific, direct instructions.
- Rank by financial impact (£/$ saved).
"""

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    opportunities = []
    patterns = []
    
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional financial planner."},
                {"role": "user", "content": llm_prompt}
            ],
            response_format=AnalysisOpportunities
        )
        opp_res = completion.choices[0].message.parsed
        opportunities = [o.model_dump() for o in opp_res.opportunities]
        patterns = opp_res.patterns
    except Exception as e:
        logger.error(f"Error fetching opportunities from LLM: {e}")
        # Default empty fallbacks
        opportunities = []
        patterns = []

    analysis_results = {
        "month": current_month,
        "income": round(income, 2),
        "spent": round(debits, 2),
        "saved": round(savings, 2),
        "savings_rate": round(savings_rate * 100.0, 2),
        "savings_goal": savings_goal,
        "mom_spent_change_pct": round(mom_pct, 2),
        "categories": cat_breakdown,
        "subscriptions": {
            "items": subscriptions,
            "total_monthly_burn": round(sub_burn, 2)
        },
        "patterns": patterns,
        "opportunities": opportunities
    }
    
    # Set overall state status based on anomalies/flags
    all_flags = []
    for t in new_txs:
        all_flags.extend(t.get("flags", []))
        
    status = "ok"
    if "UNKNOWN_MERCHANT" in all_flags or "NEW_SUBSCRIPTION" in all_flags:
        status = "needs_review"
    if "DUPLICATE" in all_flags or "LARGE_DEBIT" in all_flags:
        status = "alert"
        
    return {
        "analysis_results": analysis_results,
        "status": status,
        "flags": list(set(all_flags))
    }

# 4. Briefing Generator Node
def briefing_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Starting briefing_node...")
    analysis = state["analysis_results"]
    home_currency = state["home_currency"]
    
    # Find biggest category
    biggest_cat = "None"
    biggest_amt = 0.0
    for cat, info in analysis.get("categories", {}).items():
        if info["total"] > biggest_amt:
            biggest_amt = info["total"]
            biggest_cat = cat
            
    # Gather alerts for "Heads up" section
    alerts = []
    new_txs = state["parsed_transactions"]
    for t in new_txs:
        for f in t.get("flags", []):
            if f == "DUPLICATE":
                alerts.append(f"Duplicate charge detected: {t['merchant']} for {home_currency} {abs(t['amount']):.2f} on {t['date']}.")
            elif f == "LARGE_DEBIT":
                alerts.append(f"Large debit flagged: {t['merchant']} for {home_currency} {abs(t['amount']):.2f} on {t['date']}.")
            elif f == "FOREIGN_FX":
                alerts.append(f"Foreign transaction: {t['merchant']} in {t['currency']} on {t['date']}.")

    prompt = f"""
Write a monthly briefing based on the following analysis. 
You MUST adhere strictly to the structure, formatting, and rules below.
Keep the entire output UNDER 350 words.

━━ BRIEFING STRUCTURE ━━
  Month in numbers
    Spent: {home_currency}{{Spent}} ({{Change}}% vs last month)
    Saved: {home_currency}{{Saved}} ({{Saved_rate}}% of income — target was {home_currency}{{Target}})
    Biggest category: {{BiggestCategory}} at {home_currency}{{BiggestAmount}}

  What stood out
    2–4 bullets. Each one cites a real transaction or pattern from the data.
    Format: "• [Observation] — [implication or next action]"

  Subscriptions to review
    List only flagged or unrecognised items: [Merchant] — {home_currency}[Amount]/mo — [why]
    If none: "All subscriptions look expected this month."

  Your top 3 moves this month
    Ordered by {home_currency} impact. Each move:
    [N]. [Action verb] → save {home_currency}[Amount]/mo
         [One sentence of evidence from their actual data]

  Heads up
    {"" if not alerts else "Alerts for fraud, duplicates, large debits, or fees: " + "; ".join(alerts)}
    (Omit this section entirely if there are no flags/alerts)

  Close with one bold line: the single most important action for next month.

━━ RULES ━━
1. Do not use Markdown headings like # or ##. Use the exact titles above as plain text lines.
2. Round all currencies to 2 decimal places.
3. Every recommendation must trace to a real number in the data.
4. Never say "consider" or "you might want to". Speak with absolute instruction.
5. Keep it concise, punchy, and highly professional.

DATA CONTEXT:
- Month: {analysis.get('month')}
- Spent: {analysis.get('spent')} (Change MoM: {analysis.get('mom_spent_change_pct')}%)
- Saved: {analysis.get('saved')} (Savings Rate: {analysis.get('savings_rate')}%, Stated Goal: {analysis.get('savings_goal')})
- Biggest Category: {biggest_cat} ({biggest_amt})
- Active Subscriptions: {json.dumps(analysis.get('subscriptions', {}).get('items', []))}
- Top Opportunities: {json.dumps(analysis.get('opportunities', []))}
- Patterns: {json.dumps(analysis.get('patterns', []))}
- Alerts List: {alerts}
"""

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",  # gpt-4o for high-quality structured briefing writing
            messages=[
                {"role": "system", "content": "You are a professional financial editor. You write concise monthly summaries in plain text with strict structure."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        briefing_text = completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error drafting briefing: {e}")
        briefing_text = "Failed to generate briefing due to service error."
        
    return {"briefing_markdown": briefing_text}

# Compile LangGraph Workflow
def build_agent_graph():
    builder = StateGraph(AgentState)
    
    # Add nodes
    builder.add_node("parse_and_extract", parse_and_extract_node)
    builder.add_node("anomaly_detector", anomaly_detector_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("briefing", briefing_node)
    
    # Define edges
    builder.set_entry_point("parse_and_extract")
    builder.add_edge("parse_and_extract", "anomaly_detector")
    builder.add_edge("anomaly_detector", "analyzer")
    builder.add_edge("analyzer", "briefing")
    builder.add_edge("briefing", END)
    
    return builder.compile()

def run_finance_agent(
    raw_text: str, 
    existing_txs: List[Dict[str, Any]], 
    home_currency: str = "GBP", 
    savings_goal: float = 500.00,
    parsed_transactions: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    graph = build_agent_graph()
    
    initial_state = {
        "raw_text": raw_text,
        "home_currency": home_currency,
        "savings_goal": savings_goal,
        "existing_transactions": existing_txs,
        "parsed_transactions": parsed_transactions or [],
        "analysis_results": {},
        "briefing_markdown": "",
        "status": "ok",
        "flags": []
    }
    
    result = graph.invoke(initial_state)
    
    # Construct final required JSON format
    return {
        "status": result["status"],
        "summary": f"Ingested {len(result['parsed_transactions'])} transactions. Found {len(result['flags'])} anomaly flags.",
        "transactions": result["parsed_transactions"],
        "flags": result["flags"],
        "analysis": result["analysis_results"],
        "briefing": result["briefing_markdown"]
    }
