import io
import pandas as pd
from pypdf import PdfReader
from typing import List, Dict, Any

def parse_file_to_text(file_bytes: bytes, filename: str) -> str:
    """Parses PDF, Excel, or CSV files and returns their text contents (Fallback/PDF)."""
    ext = filename.split(".")[-1].lower()
    
    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext in ["xlsx", "xls"]:
        return parse_excel(file_bytes)
    elif ext == "csv":
        return parse_csv(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

def parse_pdf(file_bytes: bytes) -> str:
    """Extracts text from all pages of a PDF file."""
    reader = PdfReader(io.BytesIO(file_bytes))
    text_content = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            text_content.append(f"--- Page {i + 1} ---\n{text}")
            
    if not text_content:
        raise ValueError("Could not extract any text from the PDF file. It might be scanned or empty.")
        
    return "\n\n".join(text_content)

def parse_excel(file_bytes: bytes) -> str:
    """Converts Excel sheet data to standard CSV formatted text."""
    try:
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
        sheets_content = []
        
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            df.dropna(how="all", inplace=True)
            csv_text = df.to_csv(index=False)
            sheets_content.append(f"--- Sheet: {sheet_name} ---\n{csv_text}")
            
        return "\n\n".join(sheets_content)
    except Exception as e:
        raise ValueError(f"Failed to parse Excel file: {e}")

def parse_csv(file_bytes: bytes) -> str:
    """Converts raw CSV bytes to string, ensuring clean layout."""
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
        df.dropna(how="all", inplace=True)
        return df.to_csv(index=False)
    except Exception as e:
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")

def parse_tabular_file_to_raw_txs(file_bytes: bytes, filename: str, home_currency: str) -> List[Dict[str, Any]]:
    """
    Parses Excel/CSV statement files directly using pandas.
    Extracts Date, Description, Amount, and Currency columns dynamically.
    """
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        return []
        
    try:
        if ext in ["xlsx", "xls"]:
            df = pd.read_excel(io.BytesIO(file_bytes))
        elif ext == "csv":
            try:
                df = pd.read_csv(io.BytesIO(file_bytes))
            except Exception:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")
        else:
            return []
    except Exception as e:
        raise ValueError(f"Failed to parse spreadsheet table: {e}")
        
    # Drop completely empty rows and columns
    df.dropna(how="all", inplace=True)
    if df.empty:
        return []
        
    # Heuristic to find the table headers row index
    header_idx = 0
    found_headers = False
    
    for idx, row in df.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
        has_date = any(k in row_str for k in ["date", "dt", "booking", "valuta"])
        has_amount = any(k in row_str for k in ["amount", "debit", "credit", "spent", "value", "withdrawal", "deposit"])
        if has_date and has_amount:
            header_idx = idx
            found_headers = True
            break
            
    if found_headers:
        columns = df.iloc[header_idx].values
        cleaned_cols = []
        for c in columns:
            if pd.isna(c):
                cleaned_cols.append(f"col_{len(cleaned_cols)}")
            else:
                cleaned_cols.append(str(c).strip().lower())
        df_sliced = df.iloc[header_idx + 1:].copy()
        df_sliced.columns = cleaned_cols
        df = df_sliced
    else:
        df.columns = [str(c).strip().lower() for c in df.columns]
        
    # Identify key columns
    col_mapping = {}
    
    # 1. Date Col
    date_col = next((c for c in df.columns if any(k in c for k in ["date", "dt", "booking", "valuta"])), None)
    if date_col:
        col_mapping["date"] = date_col
        
    # 2. Description Col
    desc_col = next((c for c in df.columns if any(k in c for k in ["desc", "particular", "narrative", "remark", "detail", "info", "text"])), None)
    if desc_col:
        col_mapping["description"] = desc_col
    else:
        text_cols = [c for c in df.columns if c != date_col and df[c].dtype == object]
        if text_cols:
            col_mapping["description"] = text_cols[0]
            
    # 3. Amount, Debit, Credit Cols
    amount_col = next((c for c in df.columns if any(k == c for k in ["amount", "spent", "value"])), None)
    if not amount_col:
        amount_col = next((c for c in df.columns if any(k in c for k in ["amount", "spent", "value", "withdrawal", "deposit"])), None)
        
    debit_col = next((c for c in df.columns if any(k in c for k in ["debit", "withdrawal", "spent", "outflow", "paid"])), None)
    credit_col = next((c for c in df.columns if any(k in c for k in ["credit", "deposit", "received", "inflow", "income"])), None)
    
    # 4. Currency Col
    curr_col = next((c for c in df.columns if any(k in c for k in ["currency", "ccy", "symbol"])), None)
    
    raw_txs = []
    for _, row in df.iterrows():
        # Extract Date
        date_val = ""
        if "date" in col_mapping:
            raw_d = row[col_mapping["date"]]
            if pd.notna(raw_d):
                try:
                    parsed_dt = pd.to_datetime(raw_d)
                    date_val = parsed_dt.strftime("%Y-%m-%d")
                except Exception:
                    date_val = str(raw_d).strip()[:10]
                    
        # Skip row if invalid date (usually metadata or totals at bottom)
        if not date_val or len(date_val) < 8:
            continue
            
        # Extract Description
        desc_val = "Unknown Transaction"
        if "description" in col_mapping:
            raw_desc = row[col_mapping["description"]]
            if pd.notna(raw_desc):
                desc_val = str(raw_desc).strip()
                
        # Extract Amount
        amount_val = 0.0
        if debit_col or credit_col:
            d_val = 0.0
            c_val = 0.0
            if debit_col and pd.notna(row[debit_col]):
                try:
                    cleaned = str(row[debit_col]).replace(",", "").replace("₹", "").replace("$", "").replace("£", "").strip()
                    d_val = abs(float(cleaned))
                except ValueError:
                    pass
            if credit_col and pd.notna(row[credit_col]):
                try:
                    cleaned = str(row[credit_col]).replace(",", "").replace("₹", "").replace("$", "").replace("£", "").strip()
                    c_val = abs(float(cleaned))
                except ValueError:
                    pass
            if d_val > 0:
                amount_val = d_val
            elif c_val > 0:
                amount_val = -c_val
        elif amount_col and pd.notna(row[amount_col]):
            try:
                cleaned = str(row[amount_col]).replace(",", "").replace("₹", "").replace("$", "").replace("£", "").strip()
                # Check for negative signs or credit symbols inside description
                amount_val = float(cleaned)
            except ValueError:
                pass
                
        # Skip zero amount lines
        if amount_val == 0.0:
            continue
            
        # Extract Currency
        curr_val = home_currency
        if curr_col and pd.notna(row[curr_col]):
            curr_val = str(row[curr_col]).strip().upper()
            
        raw_txs.append({
            "date": date_val,
            "description": desc_val,
            "merchant": desc_val,
            "amount": amount_val,
            "currency": curr_val,
            "category": "other",
            "confidence": "low"
        })
        
    return raw_txs
