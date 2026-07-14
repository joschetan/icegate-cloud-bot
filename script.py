import os
import time
import json
import random
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# --- 1. एनवायरनमेंट वेरिएबल्स (GitHub Secrets से आएंगे) ---
GOOGLE_JSON_SECRET = os.environ.get("GOOGLE_JSON_SECRET")
# आपकी दी गई शीट की यूनिक ID
SPREADSHEET_ID = "1NYC9vpFB17i7ErF4IoYJT0iWxchXIsQmJfGOWjarY8E" 

if not GOOGLE_JSON_SECRET:
    print("❌ Error: GOOGLE_JSON_SECRET missing in GitHub Secrets!")
    exit(1)

# --- 2. गूगल शीट कनेक्शन ---
try:
    creds_dict = json.loads(GOOGLE_JSON_SECRET)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    # Welspun DSR शीट को ओपन करना
    workbook = client.open_by_key(SPREADSHEET_ID)
    sheet = workbook.worksheet("Welspun DSR")
    print("✅ Successfully connected to 'Welspun DSR' Sheet!")
except Exception as e:
    print(f"❌ Google Sheet Connection Error: {e}")
    exit(1)

# --- 3. डेटा रीड करना ---
all_rows = sheet.get_all_values()
if len(all_rows) <= 1:
    print("Sheet is empty or only contains headers.")
    exit(0)

header = all_rows[0]
data_rows = all_rows[1:]

# कॉलम इंडेक्स मैपिंग (1-based index को 0-based में बदलना)
# P=16 (SB No), Q=17 (SB Date), AB=28 (Sailing Date), AQ=43 (EGM No)
IDX_P = 15   # Shipping Bill No
IDX_Q = 16   # Shipping Bill Date
IDX_AB = 27  # Vessel Sailing Date
IDX_AQ = 42  # EGM Number Status

def is_pure_number(s):
    """जांचता है कि क्या वैल्यू सिर्फ एक शुद्ध EGM नंबर है"""
    return bool(re.match(r'^\d+$', str(s).strip()))

print(f"Total rows found in sheet: {len(data_rows)}")

# --- 4. ब्राउज़र ऑटोमेशन (Playwright - Chrome Engine) ---
with sync_playwright() as p:
    # क्रोमियम इंजन को बिना स्क्रीन (Headless) लॉन्च करना
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print("Opening ICEGATE Public Enquiry Page...")
    page.goto("https://www.icegate.gov.in/Enquiry/") 
    time.sleep(4) 

    # हर एक रो को स्कैन करना
    for i, row in enumerate(data_rows):
        row_num = i + 2  # हेडर छोड़कर असली एक्सेल/शीट रो नंबर
        
        # सुरक्षित लंबाई सुनिश्चित करना
        while len(row) < 43:
            row.append("")
            
        sailing_date = row[IDX_AB].strip()
        egm_status = row[IDX_AQ].strip()
        sb_number = row[IDX_P].strip()
        sb_date = row[IDX_Q].strip()
        port_code = "INMUN1" # हमेशा फिक्स Mundra Port

        # 🛑 कंडीशन 1: अगर AB (Sailing Date) खाली है, तो स्किप करें
        if not sailing_date:
            continue

        # 🛑 कंडीशन 2: अगर AQ में पहले से शुद्ध नंबर वैल्यू है, तो टच नहीं करना
        if egm_status and is_pure_number(egm_status):
            continue

        # अगर शिपिंग बिल डिटेल्स ही गायब हैं
        if not sb_number or not sb_date:
            print(f"⚠️ Row {row_num}: Sailing Date present but SB No/Date missing. Skipping.")
            continue

        # तारीख को क्रोम वाले फ़ॉर्मेट (DD-MM-YYYY) में ढालना
        clean_date = str(sb_date).replace("/", "-").replace(".", "-").strip()
        if len(clean_date) == 8 and "-" not in clean_date:
            y, m, d = clean_date[0:4], clean_date[4:6], clean_date[6:8]
            clean_date = f"{d}-{m}-{y}"

        print(f"🔄 Processing Row {row_num} | SB: {sb_number} | Date: {clean_date}")

        try:
            # --- 💡 क्रोम एक्सटेंशन वाला हूबहू इनपुट बाईपास लॉजिक ---
            
            # 1. Location Selection (ng-select)
            loc_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]")
            loc_input.focus()
            loc_input.click()
            time.sleep(0.2)
            loc_input.fill(port_code)
            time.sleep(0.3)
            page.keyboard.press("Enter")
            time.sleep(0.4)
            
            ng_option = page.locator(".ng-option-marked, .ng-option, mat-option").first
            if ng_option.is_visible():
                ng_option.click()

            # 2. Shipping Bill Number
            sb_input = page.locator("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")
            sb_input.focus()
            sb_input.fill(sb_number)
            time.sleep(0.2)

            # 3. Shipping Bill Date (Angular Validation Bypass)
            date_input = page.locator("#mat-input-0")
            date_input.focus()
            date_input.click()
            time.sleep(0.1)
            date_input.fill(clean_date)
            
            # एंगुलर स्टेट को 'Dirty' मार्क करने और वैल्यू लॉक करने के इवेंट्स ट्रिगर करना
            page.keyboard.press("Enter")
            time.sleep(0.2)
            date_input.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
            date_input.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
            date_input.evaluate("el => el.blur()")
            time.sleep(0.5)

            # 4. Click Search Button
            search_btn = page.locator("button:has-text('Search'), button.search, button[type='submit']").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                page.keyboard.press("Enter")

            # --- 5. स्मार्ट वेटिंग फॉर टैब्स (12 सेकंड तक होल्ड) ---
            legm_tab = None
            for _ in range(30):
                time.sleep(0.4)
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

            # LEGM Status पर क्लिक और डेटा लोड वेट
            legm_tab.click()
            time.sleep(1.5)

            # --- 6. डेटा एक्सट्रैक्शन लूप ---
            egm_value = "N.A."
            target_rows = page.locator(".mat-tab-body-active table tr, .mat-mdc-tab-body-active mat-row, table tr, mat-row")
            
            for j in range(target_rows.count()):
                cells = target_rows.nth(j).locator("td, mat-cell, .mat-mdc-cell")
                if cells.count() > 0:
                    text = cells.nth(0).inner_text().strip()
                    if text != "" and "EGM NO" not in text.upper() and "LOADING" not in text.upper():
                        egm_value = text
                        break

            # गूगल शीट की कॉलम AQ (43वीं कॉलम) में लाइव सेव करना
            sheet.update_cell(row_num, 43, egm_value)
            print(f"🎯 Success! Row {row_num} updated: {egm_value}")

        except Exception as err:
            err_msg = str(err)
            clean_err = "Timeout / Slow" if "Timeout" in err_msg or "Tabs" in err_msg else "Fields Missing"
            print(f"❌ Row {row_num} Failed: {clean_err}")
            
            # एरर होने पर भी टेक्स्ट AQ में लिखना ताकि कल दोबारा री-ट्राई हो सके
            sheet.update_cell(row_num, 43, clean_err)
            
            try:
                close_btn = page.locator(".toast-close-button, alert button, .close").first
                if close_btn.is_visible():
                    close_btn.click()
            except:
                pass

        # सरकारी सर्वर सुरक्षा के लिए 4 से 6 सेकंड का सेफ डिले
        time.sleep(random.uniform(4.0, 6.0))

    browser.close()
print("🎉 All eligible rows processed and Google Sheet is updated!")
