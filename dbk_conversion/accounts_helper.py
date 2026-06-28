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

def get_accounts_list(df,is_ezbal):
    accounts_list = []
    shop_id = get_shop_id()

    for index, row in df.iterrows():
        t_name = suriyan.convert_word(row['NAME'])
        if is_ezbal:
            e_name = row['CAPT']
        else:
            e_name = ''
        account = {
            'id': None,  
            "e_name": e_name,
            "t_name": t_name,
            "shop_id": shop_id,
            "acc_type_id": get_type_id(suriyan.convert_word(row['TYPE'])),
            "priority": 1,
            "is_admin_only": True
        }

        accounts_list.append(account)
    return accounts_list

def add_accounts(df,is_ezbal):
    accounts_list = get_accounts_list(df,is_ezbal)
    with open(types_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["accounts"] = accounts_list

    with open(output_accounts_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_trans_json(shop_id,acc_t_name,trans_date,amount,tr_type,remarks,is_tally):
    return {
        "id": None,
        "shop_id": shop_id,
        "account_id": get_acc_id(suriyan.convert_word(acc_t_name)),
        "account_name": "",
        "transaction_dt": helper.get_transaction_date(trans_date),
        "amount": abs(amount),
        "tr_type": tr_type,
        "remarks": remarks,
        "is_tally": helper.get_tally_status(is_tally),
    }

def generate_transaction_list(obal_trans_dbf,trans_dbf,is_ezbal):
    transactions_list = []
    shop_id = get_shop_id()
    if is_ezbal:
        debit_col = 'DB'
        credit_col = 'CR'
        tally = 'TLD'
    else:
        debit_col = 'DEBIT'
        credit_col = 'CREDIT'
        tally = 'TALLIED'
    for dbf in [trans_dbf,obal_trans_dbf]:
        df = pd.DataFrame(dbf.records)
        for index, row in df.iterrows():
            acc_t_name = row['NAME']
            trans_date = row['DATE']
            if 'names' in dbf.filename or 'dba' in dbf.filename:
                amount = row['OBAL']
                tr_type = "DEBIT" if amount < 0 else 'CREDIT'
                remarks = 'Openning Balance'
                is_tally = False
                transaction = get_trans_json(shop_id,acc_t_name,trans_date,amount,tr_type,remarks,is_tally)
                transactions_list.append(transaction)
            else:
                remarks = suriyan.convert_word(row['DETAIL'])
                is_tally = row[tally]
                if row[debit_col] > 0:
                    amount = row[debit_col]
                    tr_type = "DEBIT"
                    transaction = get_trans_json(shop_id,acc_t_name,trans_date,amount,tr_type,remarks,is_tally)
                    transactions_list.append(transaction)
                if row[credit_col] > 0:
                    amount = row[credit_col]
                    tr_type = "CREDIT"
                    transaction = get_trans_json(shop_id,acc_t_name,trans_date,amount,tr_type,remarks,is_tally)
                    transactions_list.append(transaction)
    print(f"Generated {len(transactions_list)} transactions from DBF.")
    return transactions_list

def add_transactions(obal_trans_dbf,trans_dbf,is_ezbal):
    transactions_list = generate_transaction_list(obal_trans_dbf,trans_dbf,is_ezbal)
    
    with open(input_transactions_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["transactions"] = transactions_list

    with open(output_transactions_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)