import csv
import queue
import logging
import threading
from pathlib import Path
from datetime import datetime
from config import BASE_URL, FIELD_NAMES
from api import get_categories, get_catalogpage, get_products
from parser import extract_product

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# 16 matches Scrapy's default CONCURRENT_REQUESTS; safe since the server handles it without throttling
MAX_WORKERS = 16


def scrape_category(cat_info, writer, csv_lock, scraped_date):
    """Fetch all pages of products for one leaf category and write each row directly to the CSV.

    Writing per-row keeps RAM flat. csv_lock prevents concurrent threads from interleaving rows.
    Returns the number of products scraped.
    """
    count = 0
    page = 1
    while True:
        try:
            data = get_products(cat_info['category_id'], page)
            pagination = data.get('pagination', {})
            products = data.get('products') or []
            for product in products:
                try:
                    record = extract_product(product, cat_info, scraped_date)
                    with csv_lock:
                        writer.writerow(record)
                    count += 1
                except Exception as e:
                    logging.warning(f"Skipped {product.get('sku')} — {e}")
            if page >= pagination.get('numberOfPages', 1):
                break
            page += 1
        except Exception as e:
            logging.warning(f"Skipped {cat_info['category_name']} page {page} — {e}")
            break
    return count


def main():
    """Discover categories and scrape products simultaneously using a single shared work queue.

    Workers expand category nodes via catalogpages and scrape products for leaf nodes in the
    same queue — no separate discovery phase means products start being written immediately
    as leaves are found, while other workers continue expanding deeper branches.
    """
    logging.info('Starting Tacoma Screw scrape...')
    scraped_date = datetime.now().strftime('%Y-%m-%d')

    categories = get_categories()
    logging.info(f'Fetched {len(categories)} top-level categories.')

    filename = Path(__file__).parent / f'TACOMA_SCREW_PRODUCTS_{datetime.now().strftime("%Y%m%d")}.csv'
    total = [0]
    total_lock = threading.Lock()

    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELD_NAMES)
        writer.writeheader()
        csv_lock = threading.Lock()

        work = queue.Queue()
        for top in categories:
            for sub in (top.get('subCategories') or []):
                work.put((sub, [top.get('name')]))

        logging.info(f'Starting with {work.qsize()} level-2 categories...')

        def process(cat, ancestors):
            # catalogpages uses shortDescription for display name; name is a URL slug
            name = cat.get('shortDescription') or cat.get('name')
            path = ancestors + [name]
            cat_path = cat.get('path') or f"/Catalog/{cat.get('urlSegment', '')}"

            try:
                page_data = get_catalogpage(cat_path)
                cat_full = page_data.get('category') or {}
                sub = cat_full.get('subCategories') or []
                cat_id = cat_full.get('id') or cat.get('id')
            except Exception as e:
                logging.warning(f'catalogpages failed for {cat_path} — {e}')
                sub = []
                cat_id = cat.get('id')

            if not sub:
                # Leaf found — scrape its products immediately without waiting for full tree discovery
                padded = (path + [None, None, None, None])[:4]
                cat_info = {
                    'category_level_1': padded[0],
                    'category_level_2': padded[1],
                    'category_level_3': padded[2],
                    'category_level_4': padded[3],
                    'category_name': name,
                    'category_url': BASE_URL + cat_path,
                    'category_id': cat_id,
                }
                count = scrape_category(cat_info, writer, csv_lock, scraped_date)
                with total_lock:
                    total[0] += count
                logging.info(f"Done: {name} ({count}) | Total: {total[0]}")
            else:
                # Not a leaf — push children into the shared queue for any free worker to pick up
                for s in sub:
                    work.put((s, path))

        def worker():
            while True:
                try:
                    cat, ancestors = work.get(timeout=30)
                except queue.Empty:
                    break
                try:
                    process(cat, ancestors)
                except Exception as e:
                    logging.warning(f'Worker error — {e}')
                finally:
                    work.task_done()

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(MAX_WORKERS)]
        for t in threads:
            t.start()
        work.join()

    logging.info(f'Done. {total[0]} products saved to {filename}')


if __name__ == '__main__':
    main()
