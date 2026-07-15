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

last_filled_date = ""

with sync_playwright() as p:
    # सुरक्षित रन के लिए थोड़ा स्लो-मोशन (slow_mo) भी जोड़ दिया है
    browser = p.chromium.launch(headless=True, slow_mo=100)
    page = browser.new_page()
    
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
            loc_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]")
            sb_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")
            date_input = page.locator("#mat-input-0")

            # पोर्ट कोड चेक
            current_port_text = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select .ng-value-label").inner_text() or ""
            
            if port_code not in current_port_text:
                loc_input.focus()
                loc_input.click()
                time.sleep(0.5)
                loc_input.fill(port_code)
                time.sleep(0.5)
                page.keyboard.press("Enter")
                time.sleep(0.5)
                ng_option = page.locator(".ng-option-marked, .ng-option, mat-option").first
                if ng_option.is_visible():
                    ng_option.click()
                    time.sleep(0.5)

            # SB Number
            sb_input.focus()
            sb_input.clear() 
            time.sleep(0.3)
            sb_input.fill(sb_number)
            time.sleep(0.3)

            # Date Check
            current_date_val = date_input.input_value() or ""
            if clean_date != last_filled_date or current_date_val == "":
                date_input.focus()
                date_input.click()
                time.sleep(0.3)
                date_input.fill(clean_date)
                page.keyboard.press("Enter")
                time.sleep(0.3)
                date_input.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                date_input.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
                date_input.evaluate("el => el.blur()")
                last_filled_date = clean_date 
                time.sleep(0.5)

            # Click Search
            search_btn = page.locator("button:has-text('Search'), button.search, button[type='submit']").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                page.keyboard.press("Enter")

            # --- ⏳ सख्त फिक्स: LEGM टैब के लोड होने का लंबा और पक्का इंतजार (45 सेकंड) ---
            legm_tab = None
            # 0.5 सेकंड के 90 लूप = पूरे 45 सेकंड का सब्र
            for _ in range(90): 
                time.sleep(0.5)
                
                # चेक 1: क्या क्लास के जरिए टैब मिल रहे हैं?
                tabs = page.locator(".mat-tab-label, .mat-mdc-tab, [role='tab'], .mat-tab-links a")
                if tabs.count() >= 4:
                    legm_tab = tabs.nth(3)
                    if "LEGM" in (legm_tab.inner_text() or "").upper():
                        break
                
                # चेक 2: क्या टेक्स्ट के जरिए डायरेक्ट मिल रहा है?
                elements = page.locator("div, span, a")
                for j in range(elements.count()):
                    if (elements.nth(j).inner_text() or "").strip().upper() == "LEGM STATUS":
                        legm_tab = elements.nth(j)
                        break
                if legm_tab:
                    break

            if not legm_tab:
                raise Exception("Timeout / LEGM Tab Not Found after 45s")

            # टैब पर क्लिक और टेबल लोडिंग का भरपूर समय (3 सेकंड)
            legm_tab.click()
            time.sleep(3.0)

            # --- डेटा एक्सट्रैक्शन ---
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
            print(f"🎯 Row {row_num} Updated: {egm_value}")

        except Exception as err:
            err_msg = str(err)
            clean_err = "Timeout / Slow" if "Timeout" in err_msg or "Tab" in err_msg else "Fields Missing"
            print(f"❌ Row {row_num} Failed: {clean_err}")
            sheet.update_cell(row_num, 43, clean_err)
            last_filled_date = "" 
            
            try:
                close_btn = page.locator(".toast-close-button, alert button, .close").first
                if close_btn.is_visible():
                    close_btn.click()
                    time.sleep(1)
            except:
                pass

        # ⏳ दो रॉ के बीच का सेफ डिले बढ़ाकर 6 से 9 सेकंड कर दिया है ताकि सर्वर ब्लॉक न करे
        time.sleep(random.uniform(6.0, 9.0))

    browser.close()
print("🎉 Process Completed!")
