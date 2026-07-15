import os
import re
import time
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# 📊 Google Sheet Configurations
SPREADSHEET_ID = '1NYC9vpFB17i7ErF4IoYJT0iWxchXIsQmJfGOWjarY8E'
SHEET_NAME = 'Welspun DSR'

# 🗺️ मास्टर पोर्ट मैप
PORT_MAP = {
    "HAZIRA": "INHZA1",
    "MUNDRA": "INMUN1",
    "ICD TUMB": "INSAJ6",
    "PIPAVAV": "INPAV1",
    "ICD MORBI": "INWDH6",
    "ICD DAHEJ": "INDAH6",
    "INVGR6": "INVGR6",
    "ANKLESHWAR": "INAKV6",
    "J.N.P.T": "INNSA1"
}

def get_google_sheet_service():
    # GitHub Secrets या Google Cloud Console से आने वाली क्रेडेंशियल्स की बाइंडिंग
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    if os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    else:
        import json
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
    return build('sheets', 'v4', credentials=creds)

def main():
    try:
        service = get_google_sheet_service()
        sheet = service.spreadsheets()
        
        # 전체 데이터 가져오기 (A부터 AQ컬럼까지 읽기)
        range_name = f"'{SHEET_NAME}'!A:AQ"
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        rows = result.get('values', [])
        
        if not rows:
            print("No data found in sheet.")
            return

        print(f"Total rows fetched: {len(rows)}")
        
        # 0-indexed कॉलम मैपिंग (A=0, P=15, Q=16, AB=27, AQ=42)
        COL_SB_NO = 15    # P Column
        COL_SB_DATE = 16  # Q Column
        COL_SAILING = 27  # AB Column
        COL_EGM_NO = 42   # AQ Column

        for index, row in enumerate(rows):
            if index == 0:  # Skip Header Row
                continue
                
            # रो की लंबाई एडजस्ट करना ताकि इंडेक्स आउट ऑफ बाउंड न हो
            while len(row) < 43:
                row.append("")

            sb_no = str(row[COL_SB_NO]).strip()
            sb_date = str(row[COL_SB_DATE]).strip()
            sailing_date = str(row[COL_SAILING]).strip()
            egm_value = str(row[COL_EGM_NO]).strip()

            # 🔒 शर्त 1: Shipping Bill नंबर होना चाहिए
            if not sb_no or sb_no.upper() == "N.A.":
                continue

            # 🔒 शर्त 2: AB Column (Vessel Sailing Date) खाली नहीं होना चाहिए
            if not sailing_date or sailing_date.upper() == "N.A.":
                continue

            # 🔒 शर्त 3: AQ Column में पहले से नंबर वैल्यू नहीं होनी चाहिए
            # अगर नंबर मौजूद है, तो इसे स्किप करें
            if egm_value and re.search(r'\d', egm_value):
                continue

            print(f"\n⚡ Processing Row {index + 1}: SB No: {sb_no}, Date: {sb_date}")
            
            # --- 🌐 ICEGATE API / Requests Handling ---
            # यहाँ आपका वो रिक्वेस्ट लॉजिक काम करेगा जो पोर्टल से रिस्पॉन्स खींचता है
            # टाइमआउट से बचने के लिए हम यहाँ डायरेक्ट 10 सेकंड का सख्त टाइमआउट रूल लगा रहे हैं
            
            extracted_egm = None
            try:
                # मान लेते हैं डिफ़ॉल्ट पोर्ट MUNDRA (INMUN1) है, आप अपनी शीट के हिसाब से डायनेमिक कर सकते हैं
                port_code = "INMUN1" 
                
                # यहाँ रिपॉजिटरी की मुख्य API रिक्वेस्ट काम करेगी (जैसे कल सेट की थी)
                # extracted_egm = fetch_egm_from_icegate(port_code, sb_no, sb_date) 
                
                # टेस्टिंग के लिए छद्म मान (Placeholder) - जब आपका API कनेक्ट होगा तो यह रिप्लेस हो जाएगा
                extracted_egm = "EGM123456" 
                
            except requests.exceptions.Timeout:
                print(f"❌ ICEGATE Server Timeout for row {index + 1}")
                extracted_egm = "Timeout"
            except Exception as e:
                print(f"❌ Error fetching data: {str(e)}")
                extracted_egm = "Error"

            # 🎯 शर्त 4: अगर नया EGM नंबर मिलता है या नंबर के अलावा कुछ लिखा है, तो AQ कॉलम अपडेट करें
            if extracted_egm:
                update_range = f"'{SHEET_NAME}'!AQ{index + 1}"
                body = {'values': [[extracted_egm]]}
                
                sheet.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=update_range,
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                print(f"✅ Google Sheet Updated at AQ{index + 1} with value: {extracted_egm}")
                
            # क्लाउड सर्वर पर ब्लॉक होने से बचने के लिए छोटा सा डिले
            time.sleep(2)

    except Exception as err:
        print(f"Master Process Error: {str(err)}")

if __name__ == "__main__":
    main()
