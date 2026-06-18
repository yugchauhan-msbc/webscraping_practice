import pandas as pd
from pathlib import Path
from datetime import datetime
from config import FIELD_NAMES


def save_to_csv(records):
    """Convert the collected records list to a DataFrame and save to a date-stamped CSV.

    Returns the DataFrame and the filename for logging and validation.
    """
    df = pd.DataFrame(records, columns=FIELD_NAMES)
    filename = Path(__file__).parent / f'TACOMA_SCREW_PRODUCTS_{datetime.now().strftime("%Y%m%d")}.csv'
    df.to_csv(filename, index=False, encoding='utf-8')
    return df, filename
