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

# ट्रैक रखने के लिए कि पिछली रो में हमने कौन सी डेट भरी थी
last_filled_date = ""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print("Opening ICEGATE Page...")
    page.goto("https://www.icegate.gov.in/Enquiry/") 
    time.sleep(4) 

    for i, row in enumerate(data_rows):
        row_num = i + 2  
        while len(row) < 43:
            row.append("")
            
        sailing_date = row[IDX_AB].strip()
        egm_status = row[IDX_AQ].strip()
        sb_number = row[IDX_P].strip()
        sb_date = row[IDX_Q].strip()
        port_code = "INMUN1"

        if not sailing_date or (egm_status and is_pure_number(egm_status)):
            continue

        if not sb_number or not sb_date:
            continue

        clean_date = str(sb_date).replace("/", "-").replace(".", "-").strip()
        if len(clean_date) == 8 and "-" not in clean_date:
            y, m, d = clean_date[0:4], clean_date[4:6], clean_date[6:8]
            clean_date = f"{d}-${m}-${y}"

        print(f"🔄 Processing Row {row_num} | SB: {sb_number}")

        try:
            # लोकेटर डिफाइन करना
            loc_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]")
            sb_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")
            date_input = page.locator("#mat-input-0")

            # 🔍 स्मार्ट चेक 1: जांचें कि पोर्ट कोड बॉक्स में पहले से कुछ लिखा है या नहीं
            # ng-select का असली वैल्यू कंटेनर ढूँढना (अगर उसमें 'INMUN1' टेक्स्ट है तो छोड़ देंगे)
            current_port_text = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select .ng-value-label").inner_text() or ""
            
            if port_code not in current_port_text:
                print("📍 Port Code missing or empty, filling INMUN1...")
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
            else:
                print("⚡ Port Code already filled, skipping this step!")

            # 2. Shipping Bill Number (यह हमेशा भरा जाएगा)
            sb_input.focus()
            sb_input.clear() # पुराना नंबर साफ करना ज़रूरी है
            time.sleep(0.1)
            sb_input.fill(sb_number)
            time.sleep(0.2)

            # 🔍 स्मार्ट चेक 2: क्या डेट पिछली वाली ही है? और क्या बॉक्स वाकई भरा हुआ है?
            current_date_val = date_input.input_value() or ""
            
            if clean_date != last_filled_date or current_date_val == "":
                print(f"📅 Date changed or empty ({clean_date}), filling...")
                date_input.focus()
                date_input.click()
                time.sleep(0.1)
                date_input.fill(clean_date)
                page.keyboard.press("Enter")
                time.sleep(0.2)
                date_input.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                date_input.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                date_input.evaluate("el => el.blur()")
                last_filled_date = clean_date # करंट डेट सेव कर लें
            else:
                print("⚡ Date is same as previous, skipping date fill!")

            time.sleep(0.3)

            # 3. Click Search Button
            search_btn = page.locator("button:has-text('Search'), button.search, button[type='submit']").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                page.keyboard.press("Enter")

            # --- 4. स्मार्ट वेटिंग फॉर टैब्स ---
            legm_tab = None
            for _ in range(25): # अब वेट थोड़ा छोटा कर दिया क्योंकि पेज रीलोड नहीं हो रहा
                time.sleep(0.3)
                tabs = page.locator(".mat-tab-label, .mat-mdc-tab, [role='tab'], .mat-tab-links a")
                if tabs.count() >= 4:
                    legm_tab = tabs.nth(3)
                    break

            if not legm_tab:
                elements = page.locator("div, span, a")
                for j in range(elements.count()):
                    if elements.nth(j).inner_text().strip().upper() == "LEGM STATUS":
                        legm_tab = elements.nth(j)
                        break

            if not legm_tab:
                raise Exception("Timeout / Tabs Missing")

            legm_tab.click()
            time.sleep(1.2)

            # --- 5. डेटा एक्सट्रैक्शन ---
            egm_value = "N.A."
            target_rows = page.locator(".mat-tab-body-active table tr, .mat-mdc-tab-body-active mat-row, table tr, mat-row")
            
            for j in range(target_rows.count()):
                cells = target_rows.nth(j).locator("td, mat-cell, .mat-mdc-cell")
                if cells.count() > 0:
                    text = cells.nth(0).inner_text().strip()
                    if text != "" and "EGM NO" not in text.upper() and "LOADING" not in text.upper():
                        egm_value = text
                        break

            sheet.update_cell(row_num, 43, egm_value)
            print(f"🎯 Row {row_num} Updated Success: {egm_value}")

        except Exception as err:
            err_msg = str(err)
            clean_err = "Timeout / Slow" if "Timeout" in err_msg or "Tabs" in err_msg else "Fields Missing"
            print(f"❌ Row {row_num} Failed: {clean_err}")
            sheet.update_cell(row_num, 43, clean_err)
            
            # एरर आने पर हो सकता है पेज क्रैश हुआ हो या पॉपअप आया हो, इसलिए सेफ साइड रहने के लिए
            # अगली रो में हम दोबारा पोर्ट और डेट भरेंगे
            last_filled_date = "" 
            
            try:
                close_btn = page.locator(".toast-close-button, alert button, .close").first
                if close_btn.is_visible():
                    close_btn.click()
            except:
                pass

        # क्योंकि अब लोड कम है, डिले को भी थोड़ा कम (3 से 4 सेकंड) कर सकते हैं
        time.sleep(random.uniform(3.0, 4.0))

    browser.close()
print("🎉 Process Completed!")
