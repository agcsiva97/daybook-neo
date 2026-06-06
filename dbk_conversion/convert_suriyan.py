import csv
from datetime import datetime, timedelta, timezone
import os
import re
import unicodedata
import pandas as pd
import json


import suriyan_to_unicode as suriyan
import conversion_helper as helper

def normalize_text(text):
    text = unicodedata.normalize("NFC", text)   # fix Tamil composition
    text = text.replace('\xa0', ' ')            # fix NBSP
    text = re.sub(r'\s+', ' ', text)            # normalize spaces
    return text.strip()

def generate_csv(sheet_name):
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    
    converted_rows = []
    for index, row in df.iterrows():
        converted_row = []
        for col_idx, column in enumerate(row):
            if col_idx in (0, 3, 4, 5):  # Columns 1,4,5,6 (0-indexed: 0,3,4,5)
                converted_column = column
            else:
                # print(f"Converting row {index+2} column {col_idx+1}: {column}")  # +2 because index starts at 0, and header is row 1
                converted_column = suriyan.convert_word(str(column))
            converted_row.append(converted_column)
        converted_rows.append(converted_row)
    
    converted_df = pd.DataFrame(converted_rows, columns=df.columns)
    converted_df.to_csv(output_path, index=False, encoding='utf-8')
    
    print(f"Conversion complete. Converted CSV saved to csv/usb_accounts_converted.csv, total rows converted: {len(converted_rows)}")

def generate_type_csv(sheet_name):
    output_path = os.path.join(os.path.dirname(__file__), 'csv', 'acc_types_groups_mapping.csv')
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    
    converted_rows = []
    for index, row in df.iterrows():
        converted_row = []
        for col_idx, column in enumerate(row):
            if col_idx in (0, 2):  # Skip columns
                converted_column = column
            else:
                # print(f"Converting row {index+2} column {col_idx+1}: {column}")  # +2 because index starts at 0, and header is row 1
                converted_column = suriyan.convert_word(str(column))
            converted_row.append(converted_column)
        converted_rows.append(converted_row)
    
    converted_df = pd.DataFrame(converted_rows, columns=df.columns)
    converted_df.to_csv(output_path, index=False, encoding='utf-8')
    
    print(f"Conversion complete. Converted CSV saved to csv/usb_accounts_converted.csv, total rows converted: {len(converted_rows)}")

def get_type_id(type_name):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    types_data = data['types']
    for type_entry in types_data:
        if normalize_text(type_entry['t_name']) == normalize_text(type_name):
            return type_entry['id']
    return None

def get_acc_id(acc_name):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    accounts_data = data['accounts']
    for account_entry in accounts_data:
        if normalize_text(account_entry['t_name']) == normalize_text(acc_name):
            return account_entry['id']
    return None

def get_shop_id():
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['shop_id']

def get_accounts_list(output_path):
    df = pd.read_csv(output_path)
    accounts_list = []
    shop_id = get_shop_id()
    for index, row in df.iterrows():
        account = {
            'id': None,  
            "e_name": row['e_name'],
            "t_name": row['t_name'],
            "shop_id": shop_id,
            "acc_type_id": get_type_id(row['type']),
            "priority": 1,
            "is_admin_only": True
        }
        accounts_list.append(account)
    return accounts_list

def generate_transaction_list(output_path):
    df = pd.read_csv(output_path)
    transactions_list = []
    shop_id = get_shop_id()
    for index, row in df.iterrows():
        if row['debit'] > 0:
            transaction = {
                "id": None,
                "shop_id": shop_id,
                "account_id": get_acc_id(row['name']),
                "account_name": "",
                "transaction_dt": helper.get_transaction_date(row['date']),
                "amount": row['debit'],
                "tr_type": "DEBIT",
                "remarks": row['remarks'],
                "name": "",
                "is_tally": helper.get_tally_status(row['tallied']),
            }
            transactions_list.append(transaction)
        if row['credit'] > 0:
            transaction = {
                "id": None,
                "shop_id": shop_id,
                "account_id": get_acc_id(row['name']),
                "account_name": "",
                "transaction_dt": helper.get_transaction_date(row['date']),
                "amount": row['credit'],
                "tr_type": "CREDIT",
                "remarks": row['remarks'],
                "name": "",
                "is_tally": helper.get_tally_status(row['tallied']),
            }
            transactions_list.append(transaction)
    print(f"Generated {len(transactions_list)} transactions from CSV.")
    return transactions_list

def add_accounts():
    accounts_list = get_accounts_list(output_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["accounts"] = accounts_list

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def add_transactions():
    output_json_path = os.path.join(os.path.dirname(__file__), 'csv', 'tlb_transactions_data.json')
    transactions_list = generate_transaction_list(output_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["transactions"] = transactions_list

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

excel_path = os.path.join(os.path.dirname(__file__), 'csv', 'TLBData_New.xlsx')
output_path = os.path.join(os.path.dirname(__file__), 'csv', 'tlb_accounts_converted.csv')
# json_path = os.path.join(os.path.dirname(__file__), 'csv', 'transactions_USB_all_20260426_210615.json')
json_path = os.path.join(os.path.dirname(__file__), 'csv', 'transactions_tlb_all_accounts.json')

output_json_path = os.path.join(os.path.dirname(__file__), 'csv', 'tlb_accounts_data.json')

generate_type_csv('Type')

generate_csv('Accounts')
add_accounts()

generate_csv('Transactions')
add_transactions()

