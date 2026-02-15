import json, os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION (Non-Secret Defaults) ---
DEFAULT_BUDGET = {
    'swing_limit': 100000,
    'long_limit': 200000,
    'swing_used': 0,
    'long_used': 0,
    'profit_vault': 0,
    'chat_id': os.getenv("AUTHORIZED_CHAT_ID") # Pulled from .env
}

PORT_FILE = "port.json"
BUDGET_FILE = "budget.json"

def init_files():
    if not os.path.exists(PORT_FILE):
        with open(PORT_FILE, 'w') as f: json.dump([], f)
    
    # Initialize budget from DEFAULT_BUDGET template if file is missing
    if not os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE, 'w') as f: 
            json.dump(DEFAULT_BUDGET, f, indent=4)

def get_port():
    with open(PORT_FILE, 'r') as f: return json.load(f)

def save_port(data):
    with open(PORT_FILE, 'w') as f: json.dump(data, f, indent=4)

def get_budget():
    with open(BUDGET_FILE, 'r') as f: return json.load(f)

def save_budget(data):
    # Validation logic to prevent corruption/negatives
    data['swing_used'] = max(0, data.get('swing_used', 0))
    data['long_used'] = max(0, data.get('long_used', 0))
    with open(BUDGET_FILE, 'w') as f: json.dump(data, f, indent=4)

def update_chat_id(chat_id):
    b = get_budget()
    # Only update if we don't have a fixed ID from .env
    if not os.getenv("AUTHORIZED_CHAT_ID"):
        b['chat_id'] = chat_id
        save_budget(b)