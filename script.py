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

# ग्लोबल ट्रैकिंग (यह लूप के बाहर रहेंगे ताकि बोट को पिछली रो का डेटा याद रहे)
is_port_filled = False
last_filled_date = ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # सख्त टाइमआउट लिमिट्स
    page.set_default_timeout(4000) # तत्वों को ढूंढने के लिए 4 सेकंड
    page.set_default_navigation_timeout(20000) # पेज ओपन होने के लिए 20 सेकंड

    print("🚀 Opening ICEGATE Page...")
    page.goto("https://foservices.icegate.gov.in/#/public-enquiries/document-status/ds-shipping-bill", wait_until="commit") 
    time.sleep(3) 

    for i, row in enumerate(data_rows):
        row_num = i + 2  
        while len(row) < 43:
            row.append("")
            
        sailing_date = row[IDX_AB].strip()
        egm_status = row[IDX_AQ].strip()
        sb_number = row[IDX_P].strip()
        sb_date = row[IDX_Q].strip()
        port_code = "INMUN1"

        # 🔒 आपकी कस्टमाइज्ड स्मार्ट शर्तें
        if not sailing_date:
            continue

        # केवल तब स्किप करेंगे जब असली EGM नंबर पहले से मौजूद हो।
        # अगर पुराना 'Timeout' या 'Slow' लिखा है, तो बोट उसे दोबारा चेक करेगा!
        if egm_status and is_pure_number(egm_status):
            print(f"⏩ Row {row_num} skipped: Pure EGM number already exists.")
            continue

        if not sb_number or not sb_date:
            continue

        clean_date = str(sb_date).replace("/", "-").replace(".", "-").strip()
        if len(clean_date) == 8 and "-" not in clean_date:
            y, m, d = clean_date[0:4], clean_date[4:6], clean_date[6:8]
            clean_date = f"{d}-{m}-{y}"

        print(f"\n🔄 Processing Row {row_num} | SB: {sb_number} | Date: {clean_date}")

        try:
            loc_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]")
            sb_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")
            date_input = page.locator("#mat-input-0")

            # 📍 1. मुंद्रा पोर्ट (पूरी स्क्रिप्ट में सिर्फ पहली बार भरा जाएगा)
            if not is_port_filled:
                print("📍 Filling Mundra Port (INMUN1) for the first time...")
                loc_input.focus()
                loc_input.click()
                time.sleep(0.1)
                loc_input.fill(port_code)
                time.sleep(0.2)
                page.keyboard.press("Enter")
                time.sleep(0.2)
                ng_option = page.locator(".ng-option-marked, .ng-option, mat-option").first
                if ng_option.is_visible():
                    ng_option.click()
                is_port_filled = True
                time.sleep(0.1)
            else:
                print("⚡ Port (INMUN1) already locked, skipping port fill!")

            # 🔢 2. Shipping Bill Number
            sb_input.focus()
            sb_input.clear()
            time.sleep(0.1)
            sb_input.fill(sb_number)

            # 📅 3. डेट फिलिंग (सिर्फ चेंज होने पर)
            current_date_val = date_input.input_value() or ""
            if clean_date != last_filled_date or current_date_val == "":
                print(f"📅 Date changed, filling: {clean_date}")
                date_input.focus()
                date_input.click()
                time.sleep(0.1)
                date_input.fill(clean_date)
                page.keyboard.press("Enter")
                time.sleep(0.1)
                date_input.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                date_input.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                date_input.evaluate("el => el.blur()")
                last_filled_date = clean_date
            else:
                print("⚡ Date is same as previous row, skipping date fill!")

            time.sleep(0.1)

            # 🔍 4. क्लिक सर्च
            search_btn = page.locator("button:has-text('Search'), button.search, button[type='submit']").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                page.keyboard.press("Enter")

            # ⏳ 5. सुपर-फ़ास्ट डेटा एक्सट्रैक्शन लूप (मैक्सिमम 3 सेकंड होल्ड)
            egm_value = "N.A."
            table_loaded = False
            time.sleep(0.3)

            for attempt in range(15): 
                time.sleep(0.2)
                
                # आपके अचूक JS Paths का उपयोग करके चौथे बटन (EGM टैब) पर क्लिक फ़ोर्स
                egm_tab_button = page.locator("#tablerecords > div.row.row-border.tabindex.ds-shipping-bill-style-7 > button:nth-child(4)")
                if egm_tab_button.is_visible():
                    egm_tab_button.click()

                # आपके सटीक JS Path से सेल को चेक करना[cite: 1]
                egm_cell = page.locator("#tablerecords > div.row.sb-table.table-responsive.ds-shipping-bill-style-103.ng-star-inserted > table > tbody > tr > td.mat-cell.cdk-cell.ds-shipping-bill-style-105.cdk-column-egmNo.mat-column-egmNo.ng-star-inserted")[cite: 1]
                
                if egm_cell.is_visible():
                    text_val = egm_cell.inner_text().strip()
                    if text_val != "" and "LOADING" not in text_val.upper() and "EGM NO" not in text_val.upper():
                        egm_value = text_val
                        table_loaded = True
                        break

            if not table_loaded:
                raise Exception("Timeout / Table Missing")

            # 📝 लाइव Google Sheet अपडेट (बिना पैरामीटर नेम के डायरेक्ट फिक्स किया हुआ)
            sheet.update_cell(row_num, 43, egm_value)
            print(f"🎯 Row {row_num} Updated Success: {egm_value}")

        except Exception as err:
            err_msg = str(err)
            clean_err = "Timeout / Slow" if "Timeout" in err_msg or "Table" in err_msg else "Fields Missing"
            print(f"❌ Row {row_num} Failed: {clean_err}")
            sheet.update_cell(row_num, 43, clean_err)
            
            # एरर आने पर रिसेट मारो ताकि अगली रो फ्रेश स्टार्ट हो
            is_port_filled = False
            last_filled_date = "" 
            
            try:
                close_btn = page.locator(".toast-close-button, alert button, .close").first
                if close_btn.is_visible():
                    close_btn.click()
            except:
                pass

        time.sleep(random.uniform(2.0, 3.5))

    browser.close()
print("🎉 Cloud Auto-Bot Process Completed Successfully!")
