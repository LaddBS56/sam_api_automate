import requests
from datetime import datetime, timedelta
import json
import os

# ---------- API KEY ----------
API_KEY = os.environ.get("SAM_API_KEY")

BASE_URL = "https://api.sam.gov/opportunities/v2/search"

# ---------- DATE RANGE ----------
today = datetime.utcnow()
start_date = today - timedelta(days=90)

posted_from = start_date.strftime("%m/%d/%Y")
posted_to = today.strftime("%m/%d/%Y")

# ---------- REQUEST ----------
params = {
    "limit": 10000,
    "postedFrom": posted_from,
    "postedTo": posted_to
}

headers = {
    "X-Api-Key": API_KEY,
    "Accept": "application/json"
}

response = requests.get(BASE_URL, headers=headers, params=params)

# Debug if needed
print(response.status_code)

data = response.json()

# ---------- SAVE FILE ----------
with open("sam_data.json", "w") as f:
    json.dump(data, f, indent=2)

print("Data saved successfully")
