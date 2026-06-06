import pandas as pd
import json
import conversion_helper as helper
import suriyan_to_unicode as suriyan
import os

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load the DBF file data into memory
types_json_path = os.path.join(script_dir, "input", "daybook_types.json")
output_accounts_json_path = os.path.join(script_dir, "output", "daybook_types_accounts.json")

input_transactions_json_path = os.path.join(script_dir, "input", "daybook_types_accounts.json")
output_transactions_json_path = os.path.join(script_dir, "output", "daybook_types_accounts_transactions.json")

def get_shop_id():
    with open(types_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['shop_id']

def get_type_id(type_name):
    with open(types_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    types_data = data['types']
    for type_entry in types_data:
        if helper.normalize_text(type_entry['t_name']) == helper.normalize_text(type_name):
            return type_entry['id']
    return None

def get_acc_id(acc_name):
    with open(input_transactions_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    accounts_data = data['accounts']
    for account_entry in accounts_data:
        if helper.normalize_text(account_entry['t_name']) == helper.normalize_text(acc_name):
            return account_entry['id']
    return None

def get_accounts_list(df):
    accounts_list = []
    shop_id = get_shop_id()
    for index, row in df.iterrows():
        account = {
            'id': None,  
            "e_name": '',
            "t_name": suriyan.convert_word(row['NAME']),
            "shop_id": shop_id,
            "acc_type_id": get_type_id(suriyan.convert_word(row['TYPE'])),
            "priority": 1,
            "is_admin_only": True
        }
        accounts_list.append(account)
    return accounts_list

def add_accounts(df):
    accounts_list = get_accounts_list(df)
    with open(types_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["accounts"] = accounts_list

    with open(output_accounts_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_transaction_list(df):
    transactions_list = []
    shop_id = get_shop_id()
    for index, row in df.iterrows():
        if row['DEBIT'] > 0:
            transaction = {
                "id": None,
                "shop_id": shop_id,
                "account_id": get_acc_id(suriyan.convert_word(row['NAME'])),
                "account_name": "",
                "transaction_dt": helper.get_transaction_date(row['DATE']),
                "amount": row['DEBIT'],
                "tr_type": "DEBIT",
                "remarks": suriyan.convert_word(row['DETAIL']),
                "is_tally": helper.get_tally_status(row['TALLIED']),
            }
            transactions_list.append(transaction)
        if row['CREDIT'] > 0:
            transaction = {
                "id": None,
                "shop_id": shop_id,
                "account_id": get_acc_id(suriyan.convert_word(row['NAME'])),
                "account_name": "",
                "transaction_dt": helper.get_transaction_date(row['DATE']),
                "amount": row['CREDIT'],
                "tr_type": "CREDIT",
                "remarks": suriyan.convert_word(row['DETAIL']),
                "is_tally": helper.get_tally_status(row['TALLIED']),
            }
            transactions_list.append(transaction)
    print(f"Generated {len(transactions_list)} transactions from DBF.")
    return transactions_list

def add_transactions(df):
    transactions_list = generate_transaction_list(df)
    with open(input_transactions_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["transactions"] = transactions_list

    with open(output_transactions_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)