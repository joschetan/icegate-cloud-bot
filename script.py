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
    print("✅ Connected to Google Sheets!")
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

last_filled_date = ""

with sync_playwright() as p:
    # क्लाउड पर हेडलेस मोड में स्थिरता के लिए कुछ खास आर्ग्युमेंट्स जोड़ दिए हैं
    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = context.new_page()
    
    print("Opening ICEGATE Page...")
    page.goto("https://www.icegate.gov.in/Enquiry/", timeout=60000) 
    time.sleep(5) 

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
            clean_date = f"{d}-{m}-{y}"

        print(f"🔄 Processing Row {row_num} | SB: {sb_number}")

        try:
            loc_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 input[type=text]")
            sb_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 input")
            date_input = page.locator("#mat-input-0")

            # पोर्ट कोड स्मार्ट चेक
            current_port_text = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 ng-select .ng-value-label").inner_text() or ""
            
            if port_code not in current_port_text:
                loc_input.focus()
                loc_input.click()
                time.sleep(0.2)
                loc_input.fill(port_code)
                time.sleep(0.3)
                page.keyboard.press("Enter")
                time.sleep(0.3)
                
                # हेडलेस में ऑप्शन सिलेक्ट करने का पक्का तरीका
                ng_option = page.locator(".ng-option-marked, .ng-option, mat-option").first
                if ng_option.is_visible():
                    ng_option.click()
                    time.sleep(0.2)

            # SB Number भरना
            sb_input.focus()
            sb_input.fill("")
            time.sleep(0.1)
            sb_input.fill(sb_number)
            time.sleep(0.2)

            # Date Check
            current_date_val = date_input.input_value() or ""
            if clean_date != last_filled_date or current_date_val == "":
                date_input.focus()
                date_input.click()
                time.sleep(0.1)
                date_input.fill(clean_date)
                page.keyboard.press("Enter")
                time.sleep(0.2)
                date_input.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                date_input.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                date_input.evaluate("el => el.blur()")
                last_filled_date = clean_date 
                time.sleep(0.2)

            # Click Search
            search_btn = page.locator("button:has-text('Search'), button.search, button[type='submit']").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                page.keyboard.press("Enter")

            # --- ⏳ स्मार्ट डायनेमिक वेटिंग: हर 200ms में टैब चेक करेगा ---
            legm_tab = None
            for _ in range(175): # मैक्सिमम 35 सेकंड
                time.sleep(0.2) # पोलिंग इंटरवल
                
                tabs = page.locator(".mat-tab-label, .mat-mdc-tab, [role='tab'], .mat-tab-links a")
                if tabs.count() >= 4:
                    legm_tab = tabs.nth(3)
                    break
                
                elements = page.locator("div, span, a")
                found = False
                for j in range(elements.count()):
                    if (elements.nth(j).inner_text() or "").strip().upper() == "LEGM STATUS":
                        legm_tab = elements.nth(j)
                        found = True
                        break
                if found:
                    break

            if not legm_tab:
                raise Exception("Timeout / Tabs Missing")

            # टैब मिलते ही तुरंत क्लिक
            legm_tab.click()

            # --- ⏳ टेबल डेटा लोड होने का डायनेमिक वेट लूप ---
            egm_value = "N.A."
            table_loaded = False
            
            for _ in range(25): # मैक्सिमम 5 सेकंड
                time.sleep(0.2)
                target_rows = page.locator(".mat-tab-body-active table tr, .mat-mdc-tab-body-active mat-row, table tr, mat-row")
                
                if target_rows.count() > 0:
                    for j in range(target_rows.count()):
                        cells = target_rows.nth(j).locator("td, mat-cell, .mat-mdc-cell")
                        if cells.count() > 0:
                            text = (cells.nth(0).inner_text() or "").strip()
                            if text != "" and "EGM NO" not in text.upper() and "LOADING" not in text.upper():
                                egm_value = text
                                table_loaded = True
                                break
                if table_loaded:
                    break # डेटा मिलते ही तुरंत लूप तोड़कर बाहर!

            sheet.update_cell(row_num, 43, egm_value)
            print(f"🎯 Row {row_num} Updated: {egm_value}")

        except Exception as err:
            err_msg = str(err)
            clean_err = "Timeout / Slow" if "Timeout" in err_msg or "Tabs" in err_msg else "Fields Missing"
            print(f"❌ Row {row_num} Failed: {clean_err}")
            sheet.update_cell(row_num, 43, clean_err)
            last_filled_date = "" 
            
            try:
                close_btn = page.locator(".toast-close-button, alert button, .close").first
                if close_btn.is_visible():
                    close_btn.click()
            except:
                pass

        # काम खत्म होते ही बिना रुके सिर्फ 300ms से 500ms का छोटा सेफ गैप
        time.sleep(random.uniform(0.3, 0.5))

    browser.close()
print("🎉 Process Completed!")
