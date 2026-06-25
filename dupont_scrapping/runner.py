"""
Runs the DupontRegistry scraper daily and stores results in SQLite.
Usage: python runner.py
Data saved to dupontregistry.db in the same folder.
"""
import time
import sqlite3
import logging
from pathlib import Path

import yaml
from scraper import run_once

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

DB_PATH      = Path(__file__).parent / 'dupontregistry.db'
SCHEMA_PATH  = Path(__file__).parent / 'schema.yaml'
INTERVAL_SEC = 24 * 60 * 60  # daily


def load_schema(path):
    """Load table definition from YAML."""
    with open(path) as f:
        return yaml.safe_load(f)


def build_create_sql(schema):
    """Build CREATE TABLE SQL from schema YAML."""
    table    = schema['table']
    cols     = schema['columns']
    pks      = [c['name'] for c in cols if c.get('primary_key')]
    col_defs = [f"    {c['name']} {c['type']}" for c in cols]
    col_defs.append(f"    PRIMARY KEY ({', '.join(pks)})")
    return f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(col_defs) + "\n)"


def build_insert_sql(schema):
    """Build INSERT OR IGNORE SQL from schema YAML."""
    table = schema['table']
    cols  = [c['name'] for c in schema['columns']]
    return (
        f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join(':' + c for c in cols)})"
    )


def get_connection(schema):
    """Return SQLite connection with table created."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(build_create_sql(schema))
    conn.commit()
    return conn


def save_to_db(conn, insert_sql, df):
    """Insert rows — skip duplicates on primary key."""
    conn.executemany(insert_sql, df.to_dict('records'))
    conn.commit()


if __name__ == '__main__':
    logging.info('Starting DupontRegistry runner...')
    schema     = load_schema(SCHEMA_PATH)
    conn       = get_connection(schema)
    insert_sql = build_insert_sql(schema)
    logging.info(f'DB ready at {DB_PATH}')

    while True:
        try:
            df = run_once()
            save_to_db(conn, insert_sql, df)
            logging.info(f'Saved {len(df)} rows — next run in 24h')
        except Exception as e:
            logging.error(f'Run failed — {e}')
        time.sleep(INTERVAL_SEC)
