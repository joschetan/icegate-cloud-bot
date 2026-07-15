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

# ग्लोबल ट्रैकिंग वेरिएबल्स (यह लूप के बाहर रहेंगे ताकि बोट को याद रहे)
is_port_filled = False
last_filled_date = ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print("🚀 Opening ICEGATE Page...")
    # wait_until="commit" लगाने से भारी-भरकम एक्स्ट्रा स्क्रिप्ट्स के लोड होने का इंतज़ार नहीं करना पड़ेगा
    page.goto("https://foservices.icegate.gov.in/#/public-enquiries/document-status/ds-shipping-bill", wait_until="commit", timeout=20000) 
    time.sleep(4) 

    for i, row in enumerate(data_rows):
        row_num = i + 2  
        while len(row) < 43:
            row.append("")
            
        sailing_date = row[IDX_AB].strip()
        egm_status = row[IDX_AQ].strip()
        sb_number = row[IDX_P].strip()
        sb_date = row[IDX_Q].strip()
        port_code = "INMUN1" # फिक्स्ड मुंद्रा पोर्ट

        # 🔒 शर्त जाँच
        if not sailing_date or (egm_status and is_pure_number(egm_status)):
            continue

        if not sb_number or not sb_date:
            continue

        # 📅 डेट क्लीनिंग फ़िक्स
        clean_date = str(sb_date).replace("/", "-").replace(".", "-").strip()
        if len(clean_date) == 8 and "-" not in clean_date:
            y, m, d = clean_date[0:4], clean_date[4:6], clean_date[6:8]
            clean_date = f"{d}-{m}-{y}"

        print(f"\n🔄 Processing Row {row_num} | SB: {sb_number} | Target Date: {clean_date}")

        try:
            loc_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]")
            sb_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")
            date_input = page.locator("#mat-input-0")

            # 📍 1. मुंद्रा पोर्ट भरने का नियम: पूरी स्क्रिप्ट में सिर्फ पहली बार भरा जाएगा!
            if not is_port_filled:
                print("📍 Port (INMUN1) filling for the first time...")
                loc_input.focus()
                loc_input.click()
                time.sleep(0.2)
                loc_input.fill(port_code)
                time.sleep(0.3)
                page.keyboard.press("Enter")
                time.sleep(0.3)
                ng_option = page.locator(".ng-option-marked, .ng-option, mat-option").first
                if ng_option.is_visible():
                    ng_option.click()
                is_port_filled = True # अब ये हमेशा के लिए True हो गया, दोबारा लूप में यहाँ नहीं आएगा
                time.sleep(0.2)
            else:
                print("⚡ Port (INMUN1) already locked on portal, skipping!")

            # 🔢 2. Shipping Bill Number (यह हमेशा हर रो में नया भरा जाएगा)
            sb_input.focus()
            sb_input.clear()
            time.sleep(0.1)
            sb_input.fill(sb_number)
            time.sleep(0.1)

            # 📅 3. डेट भरने का नियम: केवल तब भरो जब डेट पिछली वाली रो से अलग हो!
            current_date_val = date_input.input_value() or ""
            if clean_date != last_filled_date or current_date_val == "":
                print(f"📅 Date changed or empty ({clean_date}), filling new date...")
                date_input.focus()
                date_input.click()
                time.sleep(0.2)
                date_input.fill(clean_date)
                page.keyboard.press("Enter")
                time.sleep(0.2)
                date_input.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                date_input.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                date_input.evaluate("el => el.blur()")
                last_filled_date = clean_date # नई डेट याद कर लो
            else:
                print("⚡ Date is same as previous row, skipping date fill!")

            time.sleep(0.2)

            # 🔍 4. क्लिक सर्च बटन
            search_btn = page.locator("button:has-text('Search'), button.search, button[type='submit']").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                page.keyboard.press("Enter")

            # ⏳ 5. डेटा एक्सट्रैक्शन पोलिंग लूप (आपके दोनों डायरेक्ट JS Paths का उपयोग करके)
            egm_value = "N.A."
            table_loaded = False
            
            # सर्च के बाद डेटा रिफ्रेश होने के लिए छोटा सा सेफ्टी होल्ड
            time.sleep(0.5)

            for attempt in range(40): # अधिकतम 8 सेकंड इंतज़ार करेगा
                time.sleep(0.2)
                
                # 🎯 आपके दिए गए EGM बटन का सटीक JS Path (4th Tab)
                egm_tab_button = page.locator("#tablerecords > div.row.row-border.tabindex.ds-shipping-bill-style-7 > button:nth-child(4)")
                if egm_tab_button.is_visible():
                    egm_tab_button.click()

                # 🎯 आपके दिए गए EGM No. डेटा सेल का सटीक JS Path[cite: 1]
                egm_cell = page.locator("#tablerecords > div.row.sb-table.table-responsive.ds-shipping-bill-style-103.ng-star-inserted > table > tbody > tr > td.mat-cell.cdk-cell.ds-shipping-bill-style-105.cdk-column-egmNo.mat-column-egmNo.ng-star-inserted")[cite: 1]
                
                if egm_cell.is_visible():
                    text_val = egm_cell.inner_text().strip()
                    # पक्का करें कि वैल्यू खाली, LOADING या हेडर टेक्स्ट न हो
                    if text_val != "" and "LOADING" not in text_val.upper() and "EGM NO" not in text_val.upper():
                        egm_value = text_val
                        table_loaded = True
                        break

            if not table_loaded:
                raise Exception("Timeout / Table Missing")

            # 📝 सीधे Google Sheet में लाइव AQ कॉलम को अपडेट करना
            sheet.update_cell(row_num, 43, egm_value)
            print(f"🎯 Row {row_num} Updated Success: {egm_value}")

        except Exception as err:
            err_msg = str(err)
            clean_err = "Timeout / Slow" if "Timeout" in err_msg or "Table" in err_msg else "Fields Missing"
            print(f"❌ Row {row_num} Failed: {clean_err}")
            sheet.update_cell(row_num, 43, clean_err)
            
            # एरर आने पर हो सकता है वेबसाइट रिसेट हुई हो, इसलिए सेफ साइड रहने के लिए
            # अगली रो में पोर्ट और डेट दोबारा चेक करने देंगे
            is_port_filled = False
            last_filled_date = "" 
            
            try:
                close_btn = page.locator(".toast-close-button, alert button, .close").first
                if close_btn.is_visible():
                    close_btn.click()
            except:
                pass

        # रो के बीच रैंडम डिले (सर्वर ब्लॉकिंग से बचने के लिए)
        time.sleep(random.uniform(2.5, 3.5))

    browser.close()
print("🎉 Cloud Auto-Bot Process Completed Successfully!")
