import os
import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    print("🌐 Launching Browser in Headless Mode on GitHub Server...")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # सख्त 15 सेकंड का टाइमआउट टेस्ट के लिए
    page.set_default_timeout(15000)
    
    print("⏳ Attempting to open ICEGATE Shipping Bill page...")
    try:
        # सीधा उसी एंडपॉइंट को हिट कर रहे हैं जो स्क्रीनशॉट में है
        page.goto("https://foservices.icegate.gov.in/#/public-enquiries/document-status/ds-shipping-bill", wait_until="domcontentloaded")
        print("✓ Page request sent. Waiting for elements to appear...")
        time.sleep(5) # पेज को सेटल होने का टाइम दें
        
        print("\n--- 🔍 TESTING DATA COPY FROM SCREENSHOT ---")
        
        # टेस्ट 1: आपके स्क्रीनशॉट में सबसे ऊपर लेफ्ट साइड वाला टेक्स्ट कॉपी करना
        try:
            top_header = page.locator("header, .header, .top-bar, body").first.inner_text()
            print("📋 Raw Text Found on Page Top:")
            print(top_header[:300]) # शुरुआती 300 अक्षर प्रिंट करेगा
        except Exception as e:
            print(f"❌ Test 1 (Header Copy) Failed: {e}")
            
        # टेस्ट 2: आपके स्क्रीनशॉट में दिखने वाला "Shipping Bill" हेडिंग का लेबल कॉपी करना
        try:
            heading_label = page.locator("h1, h2, .page-title").first.inner_text()
            print(f"📋 Heading Label Found: {heading_label}")
        except Exception as e:
            print(f"❌ Test 2 (Heading Copy) Failed: {e}")

        # टेस्ट 3: फॉर्म के अंदर का "Select Location" वाला टेक्स्ट ढूंढना
        try:
            form_label = page.locator("text=Select Location").first.inner_text()
            print(f"📋 Form Label Found: {form_label}")
        except Exception as e:
            print(f"❌ Test 3 (Form Label Copy) Failed: {e}")

    except Exception as master_err:
        print(f"❌ Critical Connection Timeout: Page did not respond at all. Error: {master_err}")
        
    browser.close()
print("\n🏁 Test Completed!")
