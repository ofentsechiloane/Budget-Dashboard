from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "warehouse.db"
SCHEMA = ROOT / "sql" / "schema.sql"
MARTS = ROOT / "sql" / "marts.sql"
SAMPLE_DIR = ROOT / "data" / "sample"
OUT_DIR = ROOT / "dashboard" / "data"
LOG_DIR = ROOT / "logs"

UNCATEGORISED = "Uncategorised"
OTHER_INCOME = "Other Income"

# Order matters: first keyword match wins.
CATEGORIES = {
    "Salary":        {"type": "income",  "budget": 0,    "color": "#1a9c6b", "keywords": ["SALARY", "PAYROLL"]},
    OTHER_INCOME:    {"type": "income",  "budget": 0,    "color": "#4fc3a1", "keywords": ["INTEREST", "CASHSEND RECEIVED"]},
    "Rent":          {"type": "expense", "budget": 4500, "color": "#3B32A0", "keywords": ["RENT"]},
    "Groceries":     {"type": "expense", "budget": 3000, "color": "#534AB7", "keywords": ["SHOPRITE", "CHECKERS", "PICK N PAY", "SPAR", "WOOLWORTHS FOOD"]},
    "Transport":     {"type": "expense", "budget": 1200, "color": "#185FA5", "keywords": ["UBER", "BOLT", "ENGEN", "SHELL", "SASOL", "GAUTRAIN"]},
    "Eating Out":    {"type": "expense", "budget": 600,  "color": "#378ADD", "keywords": ["KFC", "NANDOS", "STEERS", "MUGG"]},
    "Utilities":     {"type": "expense", "budget": 1500, "color": "#7F77DD", "keywords": ["CITY POWER", "ESKOM", "RAND WATER", "TELKOM", "VODACOM", "MTN"]},
    "Entertainment": {"type": "expense", "budget": 400,  "color": "#d1454a", "keywords": ["NETFLIX", "SHOWMAX", "SPOTIFY", "DSTV"]},
    "Health":        {"type": "expense", "budget": 300,  "color": "#e8a33d", "keywords": ["DIS-CHEM", "DIS CHEM", "CLICKS"]},
    UNCATEGORISED:   {"type": "expense", "budget": 0,    "color": "#9AA0AA", "keywords": []},
}

# source file prefix -> (bank, account)
SOURCES = {
    "fnb": ("FNB", "FNB Cheque"),
    "capitec": ("Capitec", "Capitec Savings"),
    "dashboard_export": ("Budget Dashboard", "Dashboard Export"),
}
