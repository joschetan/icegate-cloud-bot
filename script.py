import os
import time
import json
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

GOOGLE_JSON_SECRET = os.environ.get("GOOGLE_JSON_SECRET")
SPREADSHEET_ID = "1NYC9vpFB17i7ErF4IoYJT0iWxchXIsQmJfGOWjarY8E" 

if not GOOGLE_JSON_SECRET:
    print("❌ Error: GOOGLE_JSON_SECRET missing in GitHub Secrets!")
    exit(1)

# ➔ चरण 1: गूगल शीट से कनेक्ट करने का टेस्ट
try:
    creds_dict = json.loads(GOOGLE_JSON_SECRET)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(SPREADSHEET_ID)
    sheet = workbook.worksheet("Welspun DSR")
    print("✅ BRIDGE STEP 1 SUCCESS: Successfully connected to Google Sheets!")
except Exception as e:
    print(f"❌ BRIDGE STEP 1 FAILED: Cannot connect to Google Sheet. Error: {e}")
    exit(1)

# ➔ [🎯 NEW STEP]: सबसे पहले सीधे AQ2 सेल में "HI TEST" लिखकर चेक करना
try:
    print("📝 Attempting direct write test... Writing 'HI TEST' to AQ2...")
    # gspread में सीधे (row, col, value) पास किया जाता है, row_num नाम का पैरामीटर नहीं होता
    sheet.update_cell(2, 43, "HI TEST")
    print("🎯 DIRECT WRITE SUCCESS: 'HI TEST' successfully written to AQ2!")
    time.sleep(2) # 2 सेकंड का होल्ड
except Exception as e:
    print(f"❌ DIRECT WRITE FAILED: Could not write directly to sheet. Error: {e}")

# ➔ चरण 2: किसी दूसरी पब्लिक वेबसाइट से डेटा कॉपी करने का टेस्ट
with sync_playwright() as p:
    print("\n🌐 Launching Chromium in Headless Mode...")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    test_website = "http://example.com"
    print(f"⏳ Opening neutral test website: {test_website}")
    
    extracted_text = "N.A."
    try:
        page.goto(test_website, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        
        # वेबसाइट का मुख्य हेडिंग (H1 Text) कॉपी करना
        extracted_text = page.locator("h1").first.inner_text()
        print(f"📋 BRIDGE STEP 2 SUCCESS: Copied text from website -> '{extracted_text}'")
    except Exception as e:
        print(f"❌ BRIDGE STEP 2 FAILED: Could not load website or copy text. Error: {e}")
        extracted_text = "Website Fetch Error"

    # ➔ चरण 3: कॉपी किए गए डेटा को Google Sheet की AQ2 सेल में ओवरराइट करने का टेस्ट
    try:
        print("📝 Attempting to write copied website text into Google Sheet column AQ2...")
        # फिक्स: पैरामीटर नेम हटाकर डायरेक्ट रो और कॉलम नंबर दिया है
        sheet.update_cell(2, 43, extracted_text)
        print(f"🎯 BRIDGE STEP 3 SUCCESS: Google Sheet cell AQ2 updated with website value: '{extracted_text}'")
    except Exception as e:
        print(f"❌ BRIDGE STEP 3 FAILED: Connected to sheet, but website text writing failed. Error: {e}")

    browser.close()

print("\n🏁 Bridge Testing Process Completed!")
