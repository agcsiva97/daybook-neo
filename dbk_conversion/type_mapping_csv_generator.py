import csv

import pandas as pd
from dbfread import DBF
import os
import conversion_helper as helper
import suriyan_to_unicode as suriyan

def type_exists(type_list, type_item):
    for item in type_list:
        if item[0] == type_item[0] and item[1] == type_item[1]:
            return True
    return False

def generate_type_mapping_csv(df):
    type_list = []
    row_count = 0
    for row in df.itertuples(index=False):
        row_count += 1
        type_item = [int(row[4]),suriyan.convert_word(row[2]),'']
        if not type_exists(type_list, type_item):
            type_list.append(type_item)
    with open("output/acc_types_groups_mapping.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(type_list)         
