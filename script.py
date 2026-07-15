import os
import time
import json
import random
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

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

with sync_playwright() as p:
    print("🌐 Launching Chromium in Headless Mode...")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # सख्त 4 सेकंड का टाइमआउट ताकि तुरंत पता चले
    page.set_default_timeout(4000)
    page.set_default_navigation_timeout(15000)

    print("⏳ Starting loop to check sheet conditions...")

    for i, row in enumerate(data_rows):
        row_num = i + 2  
        while len(row) < 43:
            row.append("")
            
        sailing_date = row[IDX_AB].strip()
        egm_status = row[IDX_AQ].strip()
        sb_number = row[IDX_P].strip()
        sb_date = row[IDX_Q].strip()

        # 🔒 आपकी बताई हुई सख्त कंडीशंस का मिलान:
        # 1. AB Column (Vessel Sailing Date) खाली नहीं होना चाहिए
        if not sailing_date:
            continue

        # 2. AQ Column में असली नंबर (EGM No) मौजूद नहीं होना चाहिए
        if egm_status and is_pure_number(egm_status):
            print(f"⏩ Row {row_num} skipped: Pure EGM number already exists.")
            continue

        # 3. शिपिंग बिल और डेट होनी चाहिए
        if not sb_number or not sb_date:
            continue

        print(f"\n🎯 Condition Matched! Processing Row {row_num} | SB: {sb_number}")
        
        extracted_text = "N.A."
        try:
            # 🌐 टेस्ट के लिए Google की पब्लिक साइट ओपन करना
            print(f"⏳ Opening Google Test Page for row {row_num}...")
            page.goto("https://www.google.com/search?q=Mundra+Port+News", wait_until="domcontentloaded")
            time.sleep(1.5)
            
            # Google के पेज से कोई भी लाइव टेक्स्ट उठाना (जैसे सर्च रिजल्ट का टाइटल या हेडर)
            # हम सुरक्षा के लिए पेज का टाइटल और पहला h3 टेक्स्ट कंबाइन कर लेते हैं
            page_title = page.title()
            first_h3 = page.locator("h3").first.inner_text() or "Google Content"
            
            extracted_text = f"G-Test: {first_h3[:15]}"
            print(f"📋 Success: Copied from Google -> '{extracted_text}'")
            
        except Exception as e:
            print(f"❌ Google Page Fetch Failed on row {row_num}: {e}")
            extracted_text = "G-Timeout / Slow"

        # 📝 सीधे Google Sheet के AQ कॉलम में लाइव अपडेट करना
        try:
            sheet.update_cell(row_num, 43, extracted_text)
            print(f"✅ Sheet AQ{row_num} updated with: '{extracted_text}'")
        except Exception as write_err:
            print(f"❌ Sheet write failed at row {row_num}: {write_err}")

        # लूप के बीच छोटा सा डिले
        time.sleep(2)

    browser.close()

print("\n🏁 Google Site Test Completed!")
