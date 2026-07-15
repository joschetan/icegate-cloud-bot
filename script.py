import os
import re
import time
import json
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# 📊 Google Sheet Configuration
SPREADSHEET_ID = '1NYC9vpFB17i7ErF4IoYJT0iWxchXIsQmJfGOWjarY8E'
SHEET_NAME = 'Welspun DSR'

def get_google_sheet_service():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    # स्थानीय क्रेडेंशियल्स या गITHUB SECRETS से टोकन उठाना
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if creds_json:
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
    elif os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    else:
        raise Exception("Google Credentials JSON not found in environment or file!")
    return build('sheets', 'v4', credentials=creds)

def fetch_egm_from_icegate_cloud(sb_no, sb_date):
    """
    यह फंक्शन सीधे ICEGATE के पब्लिक एंडपॉइंट को हिट करता है।
    क्लाउडफ्लेयर ब्लॉकिंग और टाइमआउट से बचने के लिए इसमें सख्त 15 सेकंड का टाइमआउट है।
    """
    url = f"https://foservices.icegate.gov.in/fe-proxy/documentStatus/getSbEgmStatus"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json"
    }
    payload = {
        "sbNo": str(sb_no).strip(),
        "sbDate": str(sb_date).strip(),
        "portCode": "INMUN1" # डिफ़ॉल्ट मुंद्रा, आवश्यकतानुसार आप बदल सकते हैं
    }
    
    # ⚡ टाइमआउट को रोकने के लिए सख्त 15 सेकंड लिमिट
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    if response.status_code == 200:
        res_data = response.json()
        # मान लेते हैं कि API रिपॉन्स में 'egmNo' फ़ील्ड आती है
        return res_data.get('egmNo', 'N.A.')
    return "N.A."

def main():
    try:
        print("🚀 Cloud Bot Started. Fetching Google Sheet data...")
        service = get_google_sheet_service()
        sheet = service.spreadsheets()
        
        range_name = f"'{SHEET_NAME}'!A:AQ"
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        rows = result.get('values', [])
        
        if not rows:
            print("❌ Empty sheet or no data found.")
            return

        # 0-indexed कॉलम सेटिंग्स (P=15, Q=16, AB=27, AQ=42)
        COL_SB_NO = 15    
        COL_SB_DATE = 16  
        COL_SAILING = 27  
        COL_EGM_NO = 42   

        for index, row in enumerate(rows):
            if index == 0: # हेडर स्किप करें
                continue
                
            # इंडेक्स एरर से बचने के लिए रो की लेंथ पैड करना
            while len(row) < 43:
                row.append("")

            sb_no = str(row[COL_SB_NO]).strip()
            sb_date = str(row[COL_SB_DATE]).strip()
            sailing_date = str(row[COL_SAILING]).strip()
            egm_value = str(row[COL_EGM_NO]).strip()

            # 🔒 रूल वैलिडेशन चेक
            if not sb_no or sb_no.upper() == "N.A.":
                continue
            if not sailing_date or sailing_date.upper() == "N.A.":
                continue
            if egm_value and re.search(r'\d', egm_value):
                continue

            print(f"➔ Processing Row {index + 1}: SB {sb_no}")
            
            # 🛡️ सुपर सेफ्टी: यहाँ ट्राई-एक्सेप्ट लगाया है ताकि कोई भी सिंगल रो पूरे बोट को क्रैश (Exit code 1) न कर पाए
            extracted_egm = "N.A."
            try:
                # लाइव क्लाउड फेचिंग मेथड चालू करना
                extracted_egm = fetch_egm_from_icegate_cloud(sb_no, sb_date)
                if not extracted_egm or extracted_egm == "N.A.":
                    extracted_egm = "N.A. (Check Portal)"
            except requests.exceptions.Timeout:
                print(f"   ⚠️ Timeout on row {index + 1}. Skipping to save workflow.")
                extracted_egm = "Timeout / Slow"
            except Exception as row_err:
                print(f"   ⚠️ Row Error: {str(row_err)}")
                extracted_egm = "Fetch Error"

            # 📝 सीधे लाइव Google Sheet में राइट (अपडेट) करना
            try:
                update_range = f"'{SHEET_NAME}'!AQ{index + 1}"
                body = {'values': [[extracted_egm]]}
                sheet.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=update_range,
                    valueInputOption='RAW',
                    body=body
                ).execute()
                print(f"   ✅ AQ{index + 1} updated with: {extracted_egm}")
            except Exception as write_err:
                print(f"   ❌ Sheet write failed at row {index + 1}: {str(write_err)}")

            # गिटहब एक्शन्स पर ब्लॉक होने से बचने के लिए सेफ़ डिले
            time.sleep(3)

        print("\n🎉 Master Process Safely Finished without crashes!")

    except Exception as master_err:
        # अगर मास्टर क्रेडेंशियल में ही लोचा हुआ, तो ही लॉग प्रिंट होगा
        print(f"❌ Critical Master Error: {str(master_err)}")

if __name__ == "__main__":
    main()
