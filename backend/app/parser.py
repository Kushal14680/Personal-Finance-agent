import io
import pandas as pd
from pypdf import PdfReader

def parse_file_to_text(file_bytes: bytes, filename: str) -> str:
    """Parses PDF, Excel, or CSV files and returns their text contents."""
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
        # Load excel file
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
        sheets_content = []
        
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            # Drop completely empty rows and columns
            df.dropna(how="all", inplace=True)
            # Convert to CSV text
            csv_text = df.to_csv(index=False)
            sheets_content.append(f"--- Sheet: {sheet_name} ---\n{csv_text}")
            
        return "\n\n".join(sheets_content)
    except Exception as e:
        raise ValueError(f"Failed to parse Excel file: {e}")

def parse_csv(file_bytes: bytes) -> str:
    """Converts raw CSV bytes to string, ensuring clean layout."""
    try:
        # We can read with pandas to ensure it's valid, then convert back to csv format
        df = pd.read_csv(io.BytesIO(file_bytes))
        df.dropna(how="all", inplace=True)
        return df.to_csv(index=False)
    except Exception as e:
        # Fallback to simple decode
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")
