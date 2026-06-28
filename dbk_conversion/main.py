import pandas as pd
from dbfread import DBF
import type_mapping_csv_generator as type_gen
import os
import accounts_helper as acc_helper

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load the DBF file data into memory
names_dbf = DBF(os.path.join(script_dir, 'dbf_files/DBK/sgfnck_dba.dbf'), load=True)
transactions_dbf = DBF(os.path.join(script_dir, 'dbf_files/DBK/sgfnck.dbf'), load=True)

# Convert the records into a standard Pandas DataFrame
names_df = pd.DataFrame(names_dbf.records)
transactions_df = pd.DataFrame(transactions_dbf.records)

print("""
Steps to follow:
    1. Generate type mapping CSV from DBF file
    2. Replace csv file in daybook lite and create Shop in Daybook app
    3. Once shop is created, export types and place the exported JSON in input folder with name 'daybook_types.json' 
    4. Generate Accounts json
    5. Import accounts json in Daybook app and export the accounts with groups and place the exported JSON in input folder with name 'daybook_accounts.json'
    6. Generate Transactions json
    7. Import transactions json in Daybook app 
""")

while True:
    user_input = input("Enter the step number to execute (or 'exit' to quit): ")
    is_ezbal = None
    if 'names' in names_dbf.filename:
        is_ezbal = False
    elif 'dba' in names_dbf.filename:
        is_ezbal = True
    
    if user_input.lower() == 'exit':
        print("Exiting the program.")
        break
    match user_input:
        case '1':
            type_gen.generate_type_mapping_csv(names_df,is_ezbal)
            break
        case '4':
            acc_helper.add_accounts(names_df,is_ezbal)
            break
        case '6':
            acc_helper.add_transactions(names_dbf,transactions_dbf,is_ezbal)
            break
        case _:
            print("Invalid input. Please enter a valid step number or 'exit' to quit.")