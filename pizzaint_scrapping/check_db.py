import sqlite3
import pandas as pd

conn = sqlite3.connect('pizzaint_scrapping/pizzint_watch.db')
df = pd.read_sql('SELECT * FROM PIZZINT_WATCH ORDER BY DataDate, Time', conn)
print(df.to_string(index=False))
print(f'\nTotal rows: {len(df)}')
