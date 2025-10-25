import pandas as pd
import sqlite3
import os

EXCEL_FILE = 'schedules.xlsx'
DB_FILE = 'schedules.db'
TABLE_NAME = 'schedules'

def convert_excel_to_sqlite():
    """
    Reads data from an Excel file and writes it to an SQLite database table.
    This script will replace the table if it already exists.
    """
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: The file '{EXCEL_FILE}' was not found.")
        print("Please make sure your Excel schedule file is in the project folder.")
        return

    try:
        # Read the data from the Excel file into a pandas DataFrame
        df = pd.read_excel(EXCEL_FILE)
        print("Successfully read data from Excel file.")

        # Ensure the DateTime column is in the correct text format for the database
        # SQLite can handle ISO8601 formatted strings efficiently.
        df['DateTime'] = pd.to_datetime(df['DateTime']).apply(lambda x: x.isoformat())

        # Create a connection to the SQLite database
        # This will create the file if it doesn't exist
        conn = sqlite3.connect(DB_FILE)
        
        # Write the data from the DataFrame to a table in the database
        # if_exists='replace': If the table already exists, drop it and create a new one.
        df.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)
        
        conn.close()
        
        print(f"Success! Data has been written to the '{TABLE_NAME}' table in '{DB_FILE}'.")
        print("You can now use DB Browser for SQLite to view this file.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    convert_excel_to_sqlite()