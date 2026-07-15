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

# कॉलम इंडेक्स सेटिंग्स (0-indexed: P=15, Q=16, AB=27, AQ=42)
IDX_P = 15   
IDX_Q = 16   
IDX_AB = 27  
IDX_AQ = 42  

def is_pure_number(s):
    return bool(re.match(r'^\d+$', str(s).strip()))

is_port_filled = False

with sync_playwright() as p:
    print("🌐 Launching Chromium in Headless Mode on GitHub Server...")
    browser = p.chromium.launch(headless=True) # गिटहब क्लाउड पर यह बिना स्क्रीन के बैकग्राउंड में चलेगा
    page = browser.new_page()
    
    page.set_default_timeout(10000) 
    page.set_default_navigation_timeout(30000)

    print("🚀 Opening ICEGATE Official Portal...")
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

        # तारीख का फॉर्मेट सही करना: DD-MM-YYYY (जैसे 04-07-2026)
        clean_date = str(sb_date).replace("/", "-").replace(".", "-").strip()
        if len(clean_date) == 8 and "-" not in clean_date:
            y, m, d = clean_date[0:4], clean_date[4:6], clean_date[6:8]
            clean_date = f"{d}-{m}-{y}"

        print(f"\n⚡ Processing Row {row_num} | SB: {sb_number} | Date: {clean_date}")

        try:
            # 📍 1. पोर्ट फिलिंग (केवल पहली बार - एक्सटेंशन लॉजिक)
            if not is_port_filled:
                page.focus("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]")
                page.click("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]")
                time.sleep(0.3)
                
                page.evaluate('() => { \
                    let locInput = document.querySelector("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-0 > div > div.search-box > ng-select > div > div > div.ng-input > input[type=text]"); \
                    let valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set; \
                    valueSetter.call(locInput, "INMUN1"); \
                    locInput.dispatchEvent(new Event("input", { bubbles: true })); \
                    locInput.dispatchEvent(new Event("change", { bubbles: true })); \
                }')
                
                time.sleep(0.5)
                page.keyboard.press("Enter")
                time.sleep(0.4)
                
                page.evaluate('() => { \
                    let ngOption = document.querySelector(".ng-option-marked, .ng-option, mat-option"); \
                    if (ngOption) ngOption.click(); \
                }')
                is_port_filled = True
                time.sleep(0.3)

            # 🔢 2. Shipping Bill Number (एक्सटेंशन फ़ोर्स सेट मेथड)
            page.focus("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")
            page.click("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input")
            page.evaluate(f'() => {{ \
                let sbInput = document.querySelector("#filter-section > div.col-lg-3.col-md-4.ds-shipping-bill-style-2 > div > div.search-box > input"); \
                let valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set; \
                valueSetter.call(sbInput, "{sb_number}"); \
                sbInput.dispatchEvent(new Event("input", {{ bubbles: true }})); \
                sbInput.dispatchEvent(new Event("change", {{ bubbles: true }})); \
            }}')
            time.sleep(0.3)

            # 📅 3. तारीख फिलिंग - (प्रूवन एक्सटेंशन फ़ोर्सफुल जावास्क्रिप्ट मेथड जिसने जादू किया)
            page.focus("#mat-input-0")
            page.click("#mat-input-0")
            time.sleep(0.2)
            
            page.evaluate(f'() => {{ \
                let dateInput = document.querySelector("#mat-input-0"); \
                let valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set; \
                let prototype = Object.getPrototypeOf(dateInput); \
                let prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, "value") ? Object.getOwnPropertyDescriptor(prototype, "value").set : null; \
                if (valueSetter && valueSetter !== prototypeValueSetter && prototypeValueSetter) {{ \
                    prototypeValueSetter.call(dateInput, "{clean_date}"); \
                }} else {{ \
                    valueSetter.call(dateInput, "{clean_date}"); \
                }} \
                dateInput.dispatchEvent(new Event("input", {{ bubbles: true }})); \
                dateInput.dispatchEvent(new Event("change", {{ bubbles: true }})); \
                dateInput.dispatchEvent(new KeyboardEvent("keydown", {{ key: "Enter", keyCode: 13, bubbles: true }})); \
            }}')
            
            time.sleep(0.5)
            page.keyboard.press("Tab")
            time.sleep(0.5)

            # 🔍 4. क्लिक सर्च बटन (एक्सटेंशन माउस इवेंट मेथड)
            page.evaluate('() => { \
                let searchBtn = null; \
                let buttons = document.querySelectorAll("button"); \
                for (let btn of buttons) { \
                    if (btn.innerText.includes("Search") || btn.className.includes("search") || btn.type === "submit") { \
                        searchBtn = btn; break; \
                    } \
                } \
                if (searchBtn) { \
                    searchBtn.dispatchEvent(new MouseEvent("click", { view: window, bubbles: true })); \
                } \
            }')

            # ⏳ 5. डेटा एक्सट्रैक्शन लूप
            egm_value = "N.A."
            table_loaded = False
            time.sleep(1.5) # क्लाउड सर्वर के लिए बफ़र गैप

            for attempt in range(25): 
                time.sleep(0.3)
                
                # चौथे बटन के अंदर स्पैन क्लिक फ़ोर्स करना (एक्सटेंशन मेथड)
                page.evaluate('() => { \
                    let egmTabButton = document.querySelector("#tablerecords > div.row.row-border.tabindex.ds-shipping-bill-style-7 > button:nth-child(4) > span > span") || document.querySelector("#tablerecords > div.row.row-border.tabindex.ds-shipping-bill-style-7 > button:nth-child(4)"); \
                    if (egmTabButton) egmTabButton.click(); \
                }')

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
            is_port_filled = False 
            try:
                page.locator(".toast-close-button, alert button, .close").first.click()
            except:
                pass

        time.sleep(random.uniform(2.5, 4.0))

    browser.close()
print("\n🎉 Master Cloud Auto-Bot Process Completed Successfully!")
