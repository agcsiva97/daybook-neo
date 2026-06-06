from datetime import date, datetime

def get_current_fy_string():
    """
    Returns current financial year in 'YY-YY' format (e.g., '24-25')
    """
    today = datetime.now()
    current_month = today.month
    current_year = today.year

    return str(current_year)


def get_fy_dates(financial_year: str):
    """
    Handles formats: '2024-25' or '24-25'
    Returns (start_date, end_date) as date objects
    """
    if not financial_year:
        financial_year = get_current_fy_string()

    financial_year = str(financial_year).strip()
    print("Input FY string:", financial_year)
    parts = financial_year.split('-')
    year_str = parts[0]

    # Convert 2-digit year to 4-digit (e.g., '24' -> 2024)
    if len(year_str) == 2:
        start_year = int("20" + year_str)
    elif len(year_str) == 3:
        start_year = int("2" + year_str)
    else:
        print("Year: " + year_str)
        start_year = int(year_str)

    start_date = date(start_year, 4, 1)       # April 1st
    end_date   = date(start_year + 1, 3, 31)  # March 31st of following year
    
    return start_date, end_date


def get_pre_nex_fy(curr_fy):
    parts = str(curr_fy).split('-')
    try:
        if(len(curr_fy)==4):
            pre_1 = int(parts[0])-2
            pre_2 = int(parts[0])-1
            nex_1 = int(parts[0])+1
            nex_2 = int(parts[0])+2
            pre_fy = f"{str(pre_1)}-{str(pre_2)}"
            nex_fy = f"{str(nex_1)}-{str(nex_2)}"
            return True, pre_fy, nex_fy
        else:
            return False, None, None
    except Exception as e:
        return False, None, None
    
# utils.py

def get_available_fy_years(shop=None):
    """
    Returns list of FY start years available in transactions.
    India FY: April 1 - March 31
    e.g. transaction in Jan 2024 → FY start year 2023
    Output: ['2023', '2024', '2025'] (ascending)
    """
    from entries.models import Transactions

    qs = Transactions.objects.all()
    if shop:
        qs = qs.filter(shop=shop)

    dates = qs.values_list('transaction_dt', flat=True).distinct()

    fy_set = set()
    for d in dates:
        fy_set.add(d.year if d.month >= 4 else d.year - 1)

    return [str(y) for y in sorted(fy_set)]