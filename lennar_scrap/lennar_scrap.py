import time
import logging
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)

PORTAL_URL = 'https://investor-marketplace.lennar.com/portal/properties?source=offmarket&listType=listings&viewStyle=grid'

API_URL = (
    'https://investor-marketplace.lennar.com/api/underwriting/prod/v2/properties'
    '?source=offmarket&limit=5000&offset=0&filter=beds%3E=0'
)

BASE_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-GB,en;q=0.9,en-US;q=0.8',
    'referer': PORTAL_URL,
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0',
}

FIELD_NAMES = [
    'scraped_date', 'market_state', 'market_city',
    'address', 'address_city', 'address_state', 'address_zip',
    'community', 'price', 'beds', 'baths', 'sqft',
    'cap_rate', 'est_move_in',
]


def create_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-images')
    # Prevents the site from detecting Selenium via navigator.webdriver flag
    options.add_argument('--disable-blink-features=AutomationControlled')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def get_session_with_cookies():
    driver = create_driver()
    try:
        logging.info('Navigating to portal to get fresh session...')
        driver.get('https://investor-marketplace.lennar.com')
        time.sleep(2)
        driver.get(PORTAL_URL)

        time.sleep(5)

        # Cognito stores the access token in localStorage, not a cookie
        token = driver.execute_script("""
            for (var key in localStorage) {
                if (key.includes('accessToken')) return localStorage.getItem(key);
            }
            return null;
        """)

        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])

        if not token:
            raise ValueError('Bearer token not found in localStorage after 20s.')

        logging.info('Session and token obtained successfully.')
        return session, token
    finally:
        driver.quit()


def fetch_properties(session, token):
    session.headers.update({**BASE_HEADERS, 'authorization': f'Bearer {token}'})
    response = session.get(API_URL)
    response.raise_for_status()
    return response.json()


def save_to_csv(raw_data):
    df = pd.json_normalize(raw_data)

    df['address_state'] = df['state']
    df['scraped_date'] = datetime.now().strftime('%Y-%m-%d')

    # beds/baths/sqft are nested under decisions[0] → payload → subjectProperty, not at the top level
    subject = df['decisions'].apply(
        lambda d: d[0].get('payload', {}).get('subjectProperty', {}) if d else {}
    )
    df['beds'] = subject.apply(lambda s: s.get('beds'))
    df['baths'] = subject.apply(lambda s: s.get('baths'))
    df['sqft'] = subject.apply(lambda s: s.get('sqft'))

    df = df.rename(columns={
        'state': 'market_state',
        'meta.lennar_metro': 'market_city',
        'full_address': 'address',
        'city': 'address_city',
        'postal_code': 'address_zip',
        'meta.community': 'community',
        'misc.spec_price': 'price',
        'misc.cap_rate': 'cap_rate',
        'meta.move_in_month': 'est_move_in',
    })[FIELD_NAMES]

    dedup_cols = [c for c in FIELD_NAMES if c != 'scraped_date']
    df.drop_duplicates(subset=dedup_cols, keep='first', inplace=True)
    df.reset_index(drop=True, inplace=True)

    filename = Path(__file__).parent / f'LEN_INVESTOR_PROPERTIES_{datetime.now().strftime("%Y%m%d")}.csv'
    df.to_csv(filename, index=False, encoding='utf-8')
    return df, filename


def main():
    logging.info('Starting Lennar investor properties scrape...')

    session, token = get_session_with_cookies()

    logging.info('Fetching properties from API...')
    raw_data = fetch_properties(session, token)
    logging.info(f'API returned {len(raw_data)} properties.')

    df, filename = save_to_csv(raw_data)

    logging.info(f'Unique properties after deduplication: {len(df)} (removed {len(raw_data) - len(df)} duplicates).')
    logging.info(f'Saved to {filename}')


if __name__ == '__main__':
    main()
