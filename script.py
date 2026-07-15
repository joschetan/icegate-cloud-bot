import os
import time
import json
import random
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

# कॉलम इंडेक्स (0-indexed: P=15, Q=16, AB=27, AQ=42)
IDX_P = 15   
IDX_Q = 16   
IDX_AB = 27  
IDX_AQ = 42  

def is_pure_number(s):
    return bool(re.match(r'^\d+$', str(s).strip()))

def fetch_egm_direct_api(sb_no, sb_date):
    """
    बिना किसी ब्राउज़र के सीधे ICEGATE के लाइव API एंडपॉइंट से डेटा खींचने का सबसे तेज़ तरीका
    """
    url = "https://foservices.icegate.gov.in/fe-proxy/documentStatus/getSbEgmStatus"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://foservices.icegate.gov.in",
        "Referer": "https://foservices.icegate.gov.in/"
    }
    payload = {
        "sbNo": str(sb_no).strip(),
        "sbDate": str(sb_date).strip(),
        "portCode": "INMUN1"  # फिक्स्ड मुंद्रा पोर्ट रूल
    }
    
    # सख्त 6 सेकंड का टाइमआउट सीधा नेटवर्क हिट के लिए
    response = requests.post(url, json=payload, headers=headers, timeout=6)
    if response.status_code == 200:
        res_json = response.json()
        # API रिस्पॉन्स से सीधे EGM नंबर निकालना
        return res_json.get("egmNo", "N.A.").strip()
    else:
        raise Exception(f"Server responded with status: {response.status_code}")

print("🚀 Starting No-Browser Rocket Engine...")

for i, row in enumerate(data_rows):
    row_num = i + 2  
    while len(row) < 43:
        row.append("")
        
    sailing_date = row[IDX_AB].strip()
    egm_status = row[IDX_AQ].strip()
    sb_number = row[IDX_P].strip()
    sb_date = row[IDX_Q].strip()

    # 🔒 आपकी कस्टमाइज्ड स्मार्ट शर्तें
    if not sailing_date:
        continue

    if egm_status and is_pure_number(egm_status):
        print(f"⏩ Row {row_num} skipped: Pure EGM number already exists.")
        continue

    if not sb_number or not sb_date:
        continue

    # तारीख का सही फॉर्मेट सेट करना (DD-MM-YYYY)
    clean_date = str(sb_date).replace("/", "-").replace(".", "-").strip()
    if len(clean_date) == 8 and "-" not in clean_date:
        y, m, d = clean_date[0:4], clean_date[4:6], clean_date[6:8]
        clean_date = f"{d}-{m}-{y}"

    print(f"\n⚡ Direct Fetching Row {row_num} | SB: {sb_number} | Date: {clean_date}")

    egm_value = "N.A."
    try:
        # सीधे API से 1 सेकंड में डेटा लोड
        egm_value = fetch_egm_direct_api(sb_number, clean_date)
        if not egm_value or egm_value.upper() == "NULL" or egm_value == "":
            egm_value = "N.A."
        print(f"🎯 Success! Found EGM: {egm_value}")
    except Exception as err:
        print(f"❌ Fetch Failed on row {row_num}: {err}")
        egm_value = "Timeout / Slow"

    # 📝 सीधे Google Sheet में लाइव राइट करना
    try:
        sheet.update_cell(row_num, 43, egm_value)
        print(f"✅ Sheet AQ{row_num} updated with: {egm_value}")
    except Exception as write_err:
        print(f"❌ Sheet write failed at row {row_num}: {write_err}")

    # एंटी-ब्लॉकिंग के लिए छोटा सा 2 सेकंड का सेफ़ डिले
    time.sleep(2)

print("\n🎉 Cloud Auto-Bot Process Completed Safely!")
