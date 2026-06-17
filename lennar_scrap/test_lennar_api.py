import os
import numpy as np
import requests
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

headers={"User-agent":"Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36",
         "Accept":"ext/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
         "accept-encoding":"gzip, deflate, br, zstd"}

# ------------------------------------------------------------------------------------------------
def get_cookies_with_selenium():
    """Launch Selenium and get cookies from page visit"""
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-images")
    chrome_driver_path = os.path.join(os.path.dirname(ChromeDriverManager().install()), "chromedriver.exe")
    driver = webdriver.Chrome(service=Service(chrome_driver_path), options=chrome_options)

    url = "https://investor-marketplace.lennar.com/portal/properties?source=offmarket&listType=listings&viewStyle=grid"
    driver.get(url)
    time.sleep(6)

    cookies = driver.get_cookies()
    cookie_dict = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    driver.close()
    driver.quit()
    return cookie_dict

def get_response(cookies,api_url="https://investor-marketplace.lennar.com/api/underwriting/prod/v2/properties?source=offmarket&limit=5000&offset=0&filter=beds%3E=0"):
    headers["Cookie"]=cookies
    response = requests.get(api_url,verify=False, timeout=30,headers=headers)
    return response

# ----------------------------------------------------------------------------------------------------------------------------
def get_json_data():
    """Fetch JSON data from API and return clean DataFrame with duplicates removed"""
    cookies = get_cookies_with_selenium()
    response=get_response(cookies)
    print(response.status_code)
    json_data = response.json()
    return json_data


def get_lennar_df():
    json_data=get_json_data()
    df = pd.json_normalize(json_data)

    df['Beds'] = df['decisions'].apply(
        lambda items: items[0]['payload']['proforma']['buyAndHold'].get('Beds') if items[0]['payload']['proforma'] else np.nan
    )

    df['Baths'] = df['decisions'].apply(
        lambda items: items[0]['payload']['proforma']['buyAndHold'].get('Beds') if items[0]['payload']['proforma'] else np.nan
    )
    df['sqft'] = df['decisions'].apply(
        lambda items: items[0]['payload']['proforma']['buyAndHold'].get('Sqft') if items[0]['payload']['proforma'] else np.nan
    )

    df = df[["state", "meta.pm_fee_by_market.market", "full_address", "city", "postal_code", "meta.community",
             "meta.spec_price","misc.cap_rate", "meta.move_in_month","Beds","Baths","sqft"]]
    df["Address_State"] = df["state"]
    df.rename(columns={"state": "Market_State", "meta.pm_fee_by_market.market": "Market_City", "full_address": "Address",
                       "city": "Address_City", "postal_code": "Address_Zip",
                       "meta.community": "Community", "meta.spec_price": "Price", "misc.cap_rate": "Cap_Rate",
                       "meta.move_in_month": "Est_Move_in"}, inplace=True)

    duplicate_columns = [
        'Address', 'Price', 'Beds', 'Baths', 'Market_State', 'Market_City',
        'Community', 'Address_City', 'Address_State', 'Address_Zip','sqft'
    ]
    df.drop_duplicates(subset=duplicate_columns, keep='first',inplace=True)
    df.reset_index(drop=True,inplace=True)
    
    print(df.to_string(index=False))
    df.to_csv('lennar_test_output.csv', index=False, encoding='utf-8')
    return df


get_lennar_df()





# import requests

# URL = 'https://investor-marketplace.lennar.com/api/underwriting/prod/v2/properties?source=offmarket&limit=5000&offset=0&filter=beds%3E=0'

# TOKEN = 'paste_your_bearer_token_here'

# HEADERS = {
#     'accept': '*/*',
#     'accept-language': 'en-GB,en;q=0.9,en-US;q=0.8',
#     'authorization': f'Bearer {TOKEN}',
#     'referer': 'https://investor-marketplace.lennar.com/portal/properties?source=offmarket&listType=listings&viewStyle=grid',
#     'sec-fetch-dest': 'empty',
#     'sec-fetch-mode': 'cors',
#     'sec-fetch-site': 'same-origin',
#     'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0',
# }

# response = requests.get(URL, headers=HEADERS)
# print(f'Status: {response.status_code}')

# data = response.json()
# print(f'Total properties: {len(data)}')
# print(f'Type: {type(data)}')
# print()
# print('--- Full structure of first property ---')

# import json
# print(json.dumps(data[0], indent=2))
