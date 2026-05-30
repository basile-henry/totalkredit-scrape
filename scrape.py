#!/usr/bin/env python3
import os
import re
import json
import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1rJ7ZoBaF723kXSDHV1RNf5SjuOIVjeVIVk3os5eBgGk"
SHEET_NAME = "Renter"
HEADERS = ["Dato", "F-kort aktuel rente", "Tilpasningslån F3 med afdrag", "Tilpasningslån F5 med afdrag"]

BASE_URL = "https://www.totalkredit.dk/api/bondinformation/table"
VARIABLE_TABLE = "privat-udbetaling-af-variabel-laan-aktuelle-kurser-kunder"
KONTANTRENTER_TABLE = "privat-udbetaling-af-laan-kontantrenter-raadgivere-og-kunder"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def fetch_table(table_id):
    resp = requests.get(BASE_URL, params={"tableId": table_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_rate(value: str) -> float:
    return float(value.replace("%", "").replace(",", ".").strip())


def get_fkort_rate(data: dict) -> float:
    for group in data.get("groups", []):
        if group["name"] == "F-kort":
            for entry in group.get("entries", []):
                match = re.search(r"Aktuel rente ([\d,]+)%", entry["name"])
                if match:
                    return parse_rate(match.group(1))
    raise ValueError("F-kort aktuel rente not found")


def get_tilpasning_rate(data: dict, loan_name: str) -> float:
    for group in data.get("groups", []):
        for entry in group.get("entries", []):
            if entry["name"] == loan_name:
                return parse_rate(entry["innerInterestGrossValue"])
    raise ValueError(f"{loan_name} not found")


def get_or_create_sheet(gc, spreadsheet_id, sheet_name):
    spreadsheet = gc.open_by_key(spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
    return worksheet


def ensure_headers(worksheet):
    first_row = worksheet.row_values(1)
    if first_row != HEADERS:
        worksheet.insert_row(HEADERS, index=1)


def main():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS environment variable not set")

    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(creds)

    variable_data = fetch_table(VARIABLE_TABLE)
    kontantrenter_data = fetch_table(KONTANTRENTER_TABLE)

    fkort_rate = get_fkort_rate(variable_data)
    f3_rate = get_tilpasning_rate(kontantrenter_data, "F3 med afdrag")
    f5_rate = get_tilpasning_rate(kontantrenter_data, "F5 med afdrag")

    today = datetime.date.today().isoformat()
    row = [today, fkort_rate, f3_rate, f5_rate]

    worksheet = get_or_create_sheet(gc, SPREADSHEET_ID, SHEET_NAME)
    ensure_headers(worksheet)
    worksheet.append_row(row, value_input_option="USER_ENTERED")

    print(f"Appended: {row}")


if __name__ == "__main__":
    main()
