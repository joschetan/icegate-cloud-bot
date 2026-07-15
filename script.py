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

is_port_filled = False

with sync_playwright() as p:
    print("🌐 Launching Chromium in Headless Mode on GitHub...")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    page.set_default_timeout(10000) 
    page.set_default_navigation_timeout(30000)

    print("🚀 Opening ICEGATE Document Status Portal...")
    page.goto("https://foservices.icegate.gov.in/#/public-enquiries/document-status/ds-shipping-bill", wait_until="networkidle") 
    time.sleep(4) 

    for i, row in enumerate(data_rows):
        row_num = i + 2  
        while len(row) < 43:
            row.append("")
            
        sailing_date = row[IDX_AB].strip()
        egm_status = row[IDX_AQ].strip()
        sb_number = row[IDX_P].strip()
        sb_date = row[IDX_Q].strip()

        if not sailing_date:
            continue

        if egm_status and is_pure_number(egm_status):
            continue

        if not sb_number or not sb_date:
            continue

        # तारीख का फॉर्मेट सही करना: DD-MM-YYYY (जैसे 06-07-2026)
        clean_date = str(sb_date).replace("/", "-").replace(".", "-").strip()
        if len(clean_date) == 8 and "-" not in clean_date:
            y, m, d = clean_date[0:4], clean_date[4:6], clean_date[6:8]
            clean_date = f"{d}-{m}-{y}"

        # बोट को टाइप करने के लिए बिना डैश वाला नंबर चाहिए (जैसे 06072026) ताकि कैलेंडर न भटके
        digits_only_date = clean_date.replace("-", "")

        print(f"\n⚡ Row {row_num} | SB: {sb_number} | Date: {clean_date}")

        try:
            loc_input = page.locator("input[placeholder*='Location'], ng-select input[type=text]").first
            sb_input = page.locator("#filter-section input[type='text']:not([placeholder*='Date']):not([readonly])").element_handle()
            
            # अगर ऊपर वाला लोकेटर न मिले तो सीधे आपके पुराने आईडी से ढूंढेंगे
            if not sb_input:
                sb_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")

            date_input = page.locator("input[placeholder='DD-MM-YYYY'], #mat-input-0, input[formcontrolname='sbDate']").first

            # 📍 1. पोर्ट सिलेक्शन (केवल पहली बार)
            if not is_port_filled:
                loc_input.focus()
                loc_input.click()
                time.sleep(0.5)
                loc_input.fill("INMUN1")
                time.sleep(0.5)
                page.keyboard.press("Enter")
                time.sleep(0.5)
                is_port_filled = True

            # 🔢 2. Shipping Bill Number भरना
            sb_input.focus()
            sb_input.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            time.sleep(0.3)
            sb_input.fill(sb_number)
            time.sleep(0.3)

            # 📅 3. विलेन का खात्मा - असली इंसानी कीबोर्ड टाइपिंग से डेट भरना
            date_input.focus()
            date_input.click()
            # पुराने किसी भी टेक्स्ट को पूरी तरह साफ़ करना
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            time.sleep(0.5)
            
            # एक-एक करके नंबर टाइप करना ताकि एंगुलर का कैलेंडर एक्टिव हो जाए
            for digit in digits_only_date:
                page.keyboard.type(digit)
                time.sleep(0.05)
                
            time.sleep(0.5)
            page.keyboard.press("Tab") # इनपुट बॉक्स से बाहर आकर चेंज रजिस्टर करना
            time.sleep(0.5)

            # 🔍 4. क्लिक सर्च बटन
            search_btn = page.locator("button:has-text('Search'), button.search-btn").first
            search_btn.click()
            print("   🔍 Search Button Clicked successfully!")

            # ⏳ 5. डेटा एक्सट्रैक्शन लूप
            egm_value = "N.A."
            table_loaded = False
            time.sleep(1.0)

            for attempt in range(25): 
                time.sleep(0.3)
                egm_tab_button = page.locator("button:has-text('EGM'), .ds-shipping-bill-style-7 button").nth(3)
                if not egm_tab_button.is_visible():
                    egm_tab_button = page.locator("#tablerecords button").nth(3)
                
                if egm_tab_button.is_visible():
                    egm_tab_button.click()

                # EGM नंबर वाले सेल को खोजना
                egm_cell = page.locator("td.mat-column-egmNo, cdk-column-egmNo").first
                if egm_cell.is_visible():
                    text_val = egm_cell.inner_text().strip()
                    if text_val != "" and "LOADING" not in text_val.upper() and "EGM NO" not in text_val.upper():
                        egm_value = text_val
                        table_loaded = True
                        break

            if not table_loaded:
                raise Exception("Timeout / Slow")

            sheet.update_cell(row_num, 43, egm_value)
            print(f"   🎯 Success! Found EGM: {egm_value}")

        except Exception as err:
            print(f"   ❌ Row {row_num} Failed: {err}")
            sheet.update_cell(row_num, 43, "Timeout / Slow")
            # अगर एरर आए तो अगली रो के लिए रिसेट करें ताकि फ्रेश स्टार्ट हो
            is_port_filled = False 
            try:
                # एरर का पॉपअप बंद करने की कोशिश
                page.locator(".toast-close-button, alert button").first.click()
            except:
                pass

        time.sleep(random.uniform(2.0, 3.5))

    browser.close()
print("\n🎉 Master Job Finished!")
