import csv
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)

BASE_URL = 'https://books.toscrape.com'
OUTPUT_FILE = 'books.csv'

RATING_MAP = {'One': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5}
FIELDNAMES = ['title', 'price', 'rating', 'upc', 'stock', 'description', 'url']


def scrape_list_page(soup):
    books = []
    for article in soup.select('article.product_pod'):
        title = article.select_one('h3 a')['title']
        price = article.select_one('p.price_color').text
        rating_word = article.select_one('p.star-rating')['class'][1]
        rating = RATING_MAP.get(rating_word, 0)
        detail_path = article.select_one('h3 a')['href']
        books.append({'title': title, 'price': price, 'rating': rating, 'detail_path': detail_path})
    return books


def scrape_detail_page(session, url):
    response = session.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    table = {row.th.text: row.td.text for row in soup.select('table.table-striped tr')}

    desc_tag = soup.select_one('#product_description ~ p')
    description = desc_tag.text.strip() if desc_tag else ''

    stock_text = table.get('Availability', '')
    stock = int(stock_text.strip().split('(')[1].split(' ')[0]) if '(' in stock_text else 0

    return {
        'upc': table.get('UPC', ''),
        'stock': stock,
        'description': description,
    }


def main():
    session = requests.Session()
    url = BASE_URL
    count = 0

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        while url:
            response = session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            current_url = url

            for book in scrape_list_page(soup):
                detail_url = urljoin(current_url, book.pop('detail_path'))
                try:
                    detail = scrape_detail_page(session, detail_url)
                    book.update(detail)
                    book['url'] = detail_url
                    writer.writerow(book)
                    count += 1
                except Exception as e:
                    logging.warning(f'Skipped {detail_url} — {e}')

            logging.info(f'Scraped: {count} books so far...')

            next_btn = soup.select_one('li.next a')
            url = urljoin(url, next_btn['href']) if next_btn else None

            if url:
                time.sleep(random.uniform(1, 3))

    logging.info(f'Total books scraped: {count}')
    logging.info(f'Saved to {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
