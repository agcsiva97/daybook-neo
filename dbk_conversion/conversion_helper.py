from datetime import datetime, timedelta, timezone
import re
import unicodedata

def normalize_text(text):
    text = unicodedata.normalize("NFC", text)   # fix Tamil composition
    text = text.replace('\xa0', ' ')            # fix NBSP
    text = re.sub(r'\s+', ' ', text)            # normalize spaces
    return text.strip()

def get_transaction_date(date_str):

    IST = timezone(timedelta(hours=5, minutes=30))

    # Handle NaN or non-string values
    if date_str is None or (isinstance(date_str, float) and date_str != date_str):  # NaN check
        return None
    
    # Convert to string to be safe
    date_str = str(date_str).strip()
    
    # 1. Normalize dash (– → -)
    dt_str = date_str.replace('–', '-')
    
    # 2. Split
    year, month, day = dt_str.split('-')
    
    # 3. Convert 2-digit year → 4-digit (custom logic)
    year = int(year)
    if(len(str(year)) == 2):
        if year <= 30:
            year += 2000
        else:
            year += 1900
    else:
        year = int(year)
    
    
    # 5. Make timezone aware
    dt = datetime(
        year, int(month), int(day),
        0, 0, 0, 0,
        tzinfo=IST
    )
    
    return dt.isoformat()

def get_tally_status(tallied_str):
    if isinstance(tallied_str, bool):
        return tallied_str
    s = str(tallied_str).strip().lower()
    if 't' in s or 'true' in s:
        return True
    elif 'f' in s or 'false' in s:
        return False
    else:
        return False