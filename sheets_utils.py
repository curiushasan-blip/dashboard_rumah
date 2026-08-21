"""
Integrasi Google Sheets (opsional) untuk sinkronisasi data rumah.

Dipakai sebagai cara backup & berbagi data antar perangkat/anggota keluarga
tanpa perlu database. Lihat README.md bagian "Integrasi Google Sheets"
untuk panduan pengaturan Service Account secara lengkap.

Semua field yang berupa list/dict (kelebihan, kekurangan, gambar,
survey_records) disimpan sebagai teks JSON dalam satu sel, lalu diurai
kembali saat data ditarik dari Sheets.
"""

import json
import re

import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials

    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Urutan kolom pada worksheet "Rumah"
HOUSE_FIELDS = [
    "id", "nama", "alamat", "latitude", "longitude", "harga", "status",
    "luas_tanah", "luas_bangunan", "kamar_tidur", "kamar_mandi", "carport",
    "lantai", "tahun_dibangun", "sertifikat", "hadap", "developer",
    "deskripsi", "kelebihan", "kekurangan", "gambar", "video",
    "kontak_agen", "sumber_listing", "estimasi_cicilan", "survey_records",
]

# Field yang disimpan sebagai JSON dalam satu sel (list / dict bersarang)
HOUSE_LIST_FIELDS = ["kelebihan", "kekurangan", "gambar", "survey_records"]

WORKSHEET_NAME = "Rumah"


def extract_sheet_id(text):
    """Terima URL Google Sheets penuh atau ID mentah, kembalikan ID-nya saja."""
    text = (text or "").strip()
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    return text


def get_client():
    """Buat klien gspread terautentikasi dari kredensial di st.secrets."""
    if not GSPREAD_AVAILABLE:
        raise RuntimeError(
            "Library 'gspread' dan 'google-auth' belum terpasang. "
            "Jalankan: pip install gspread google-auth"
        )
    no_creds_msg = (
        "Kredensial Google belum diatur. Salin '.streamlit/secrets.toml.example' "
        "menjadi '.streamlit/secrets.toml' dan isi sesuai panduan di README.md."
    )
    try:
        # Mengakses st.secrets melempar StreamlitSecretNotFoundError (bukan
        # sekadar mengembalikan kosong) kalau file secrets.toml belum ada
        # sama sekali, jadi harus dibungkus try/except.
        has_creds = "gcp_service_account" in st.secrets
    except Exception:
        has_creds = False
    if not has_creds:
        raise RuntimeError(no_creds_msg)
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds)


def _serialize(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _deserialize(value, field, list_fields):
    if field not in list_fields:
        return value
    if isinstance(value, (list, dict)):
        return value
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [line.strip() for line in str(value).splitlines() if line.strip()]


def push_houses(gc, sheet_id, houses):
    """Kirim (timpa) seluruh data rumah ke worksheet 'Rumah' pada spreadsheet tujuan."""
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(
            title=WORKSHEET_NAME,
            rows=max(len(houses) + 10, 20),
            cols=len(HOUSE_FIELDS) + 2,
        )
    ws.clear()
    rows = [HOUSE_FIELDS]
    for h in houses:
        rows.append([_serialize(h.get(col, "")) for col in HOUSE_FIELDS])
    ws.update(rows)
    return len(houses)


def pull_houses(gc, sheet_id):
    """Tarik seluruh data rumah dari worksheet 'Rumah'. Melempar error bila belum ada."""
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(WORKSHEET_NAME)  # raise gspread.WorksheetNotFound bila belum ada
    raw_records = ws.get_all_records()
    houses = []
    for row in raw_records:
        h = {k: _deserialize(v, k, HOUSE_LIST_FIELDS) for k, v in row.items()}
        houses.append(h)
    return houses
