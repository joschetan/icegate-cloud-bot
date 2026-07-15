import os
import time
import json
import re
import gspread
import requests
from google.oauth2.service_account import Credentials

GOOGLE_JSON_SECRET = os.environ.get("GOOGLE_JSON_SECRET")
SPREADSHEET_ID = "1NYC9vpFB17i7ErF4IoYJT0iWxchXIsQmJfGOWjarY8E" 

if not GOOGLE_JSON_SECRET:
    print("❌ Error: GOOGLE_JSON_SECRET missing!")
    exit(1)

try:
    creds_dict = json.loads(GOOGLE_JSON_SECRET)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(SPREADSHEET_ID)
    sheet = workbook.worksheet("Welspun DSR")
    print("✅ Successfully connected to Google Sheets!")
except Exception as e:
    print(f"❌ Connection Error: {e}")
    exit(1)

all_rows = sheet.get_all_values()
if len(all_rows) <= 1:
    exit(0)

data_rows = all_rows[1:]

IDX_P = 15   
IDX_Q = 16   
IDX_AB = 27  
IDX_AQ = 42  

def is_pure_number(s):
    return bool(re.match(r'^\d+$', str(s).strip()))

print("🚀 Launching Dedicated Network-Proof Success Engine...")

for i, row in enumerate(data_rows):
    row_num = i + 2  
    while len(row) < 43:
        row.append("")
        
    sailing_date = row[IDX_AB].strip()
    egm_status = row[IDX_AQ].strip()
    sb_number = row[IDX_P].strip()
    sb_date = row[IDX_Q].strip()

    # 🔒 आपकी सख्त कंडीशंस
    if not sailing_date:
        continue

    if egm_status and is_pure_number(egm_status):
        continue

    if not sb_number or not sb_date:
        continue

    print(f"\n🎯 Condition Match! Row {row_num} | Testing Connection with google.com...")

    status_value = "N.A."
    try:
        # 🌐 दुनिया की सबसे स्थिर वेबसाइट (google.com) को हिट करना
        # हमने टाइमआउट को बढ़ाकर 15 सेकंड कर दिया है ताकि गिटहब का लैग इसे फेल न कर सके
        test_url = "https://www.google.com"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        response = requests.get(test_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            status_value = "Google Success"
            print(f"✅ Connection Established! HTTP Status: {response.status_code}")
        else:
            status_value = f"HTTP Error {response.status_code}"
            
    except Exception as err:
        print(f"❌ Network Lag Detected on row {row_num}: {err}")
        status_value = "Timeout / Slow"

    # 📝 सीधे Google Sheet में रिजल्ट राइट करना
    try:
        sheet.update_cell(row_num, 43, status_value)
        print(f"📝 Sheet AQ{row_num} successfully updated with: '{status_value}'")
    except Exception as write_err:
        print(f"❌ Sheet write failed at row {row_num}: {write_err}")

    # सुरक्षित 2 सेकंड का डिले
    time.sleep(2)

print("\n🏁 Pure Success Process Completed!")
