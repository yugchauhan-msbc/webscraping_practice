"""
Runs the pizzint.watch scraper every 30 minutes and stores results in SQLite.
Usage: python runner.py
Data saved to pizzint_watch.db in the same folder.
"""
import time
import sqlite3
import logging
from pathlib import Path
from scraper import run_once

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

DB_PATH = Path(__file__).parent / 'pizzint_watch.db'
INTERVAL_MINUTES = 30

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS PIZZINT_WATCH (
    DataDate TEXT,
    Time     TEXT,
    Section  TEXT,
    DataName TEXT,
    Status   TEXT,
    Metric   TEXT,
    Value    REAL,
    PRIMARY KEY (DataDate, Time, Section, DataName, Metric)
)
"""


def get_connection():
    """Return a SQLite connection and ensure the table exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    return conn


def save_to_db(conn, df):
    """Insert DataFrame rows; skip any that already exist (same primary key)."""
    conn.executemany(
        """INSERT OR IGNORE INTO PIZZINT_WATCH
               (DataDate, Time, Section, DataName, Status, Metric, Value)
           VALUES
               (:DataDate, :Time, :Section, :DataName, :Status, :Metric, :Value)""",
        df.to_dict('records'),
    )
    conn.commit()


if __name__ == '__main__':
    logging.info('Starting pizzint.watch runner...')
    conn = get_connection()
    logging.info(f'DB ready at {DB_PATH}')

    while True:
        try:
            df = run_once()
            save_to_db(conn, df)
            logging.info(f'Saved {len(df)} rows — next run in {INTERVAL_MINUTES} min')
        except Exception as e:
            logging.error(f'Run failed — {e}')
        time.sleep(INTERVAL_MINUTES * 60)
