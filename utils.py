"""Fungsi-fungsi pendukung untuk Dasbor Komparasi Rumah."""

import json
import re
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "houses.json"

# ----------------------------------------------------------------------------
# Status rumah (tahap keputusan pembelian)
# ----------------------------------------------------------------------------

STATUS_OPTIONS = ["Survey", "Nego", "Deal", "Pertimbangan", "Batal"]

STATUS_COLORS = {
    "Survey": "#2B4C63",
    "Nego": "#B8863B",
    "Deal": "#3F6B4F",
    "Pertimbangan": "#6B5B73",
    "Batal": "#A24B3F",
}

# Warna marker peta Folium hanya mendukung palet warna tertentu
STATUS_FOLIUM_COLORS = {
    "Survey": "blue",
    "Nego": "orange",
    "Deal": "green",
    "Pertimbangan": "purple",
    "Batal": "red",
}

# ----------------------------------------------------------------------------
# Survey rumah (jadwal, kuisioner, hasil)
# ----------------------------------------------------------------------------

SURVEY_STATUS_OPTIONS = ["Terjadwal", "Selesai", "Dibatalkan"]

SURVEY_STATUS_COLORS = {
    "Terjadwal": "#2B4C63",
    "Selesai": "#3F6B4F",
    "Dibatalkan": "#A24B3F",
}

KESIMPULAN_OPTIONS = [
    "Layak Dilanjutkan",
    "Perlu Survey Ulang",
    "Masih Dipertimbangkan",
    "Tidak Layak",
]

KESIMPULAN_COLORS = {
    "Layak Dilanjutkan": "#3F6B4F",
    "Perlu Survey Ulang": "#B8863B",
    "Masih Dipertimbangkan": "#6B5B73",
    "Tidak Layak": "#A24B3F",
}

# Pertanyaan kuisioner bertipe rating 1-5, dipakai untuk hitung skor rata-rata
SURVEY_NUMERIC_KEYS = [
    "kondisi_bangunan",
    "struktur",
    "akses_jalan",
    "ketersediaan_air",
    "sinyal_internet",
    "ketenangan",
    "keamanan",
    "fasilitas_umum",
]

KUISIONER_LABELS = {
    "kondisi_bangunan": "Kondisi Bangunan (dinding/atap/lantai)",
    "struktur": "Kualitas Struktur (retak/rembes)",
    "akses_jalan": "Akses Jalan",
    "ketersediaan_air": "Ketersediaan & Tekanan Air",
    "sinyal_internet": "Sinyal Internet/Provider",
    "ketenangan": "Ketenangan Lingkungan",
    "keamanan": "Keamanan Lingkungan",
    "fasilitas_umum": "Kedekatan Fasilitas Umum",
    "potensi_banjir": "Potensi Banjir",
    "legalitas_dicek": "Legalitas Dokumen Sudah Dicek",
    "catatan_tambahan": "Catatan Tambahan",
}


def compute_survey_score(kuisioner):
    """Hitung rata-rata skor 1-5 dari jawaban kuisioner numerik."""
    if not kuisioner:
        return 0.0
    vals = [
        kuisioner[k]
        for k in SURVEY_NUMERIC_KEYS
        if k in kuisioner and kuisioner[k] is not None
    ]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def next_survey_id(house):
    """Hitung id survey berikutnya untuk sebuah rumah."""
    records = house.get("survey_records", [])
    if not records:
        return 1
    return max(r.get("id", 0) for r in records) + 1


def latest_survey_info(house):
    """Ringkasan status survey terbaru untuk sebuah rumah.

    Mengembalikan salah satu bentuk:
      {"type": "selesai", "score": float, "kesimpulan": str}
      {"type": "terjadwal", "jadwal": str}
      {"type": "belum"}
    """
    records = house.get("survey_records", [])
    completed = [r for r in records if r.get("status") == "Selesai"]
    scheduled = [r for r in records if r.get("status") == "Terjadwal"]

    if completed:
        latest = sorted(
            completed,
            key=lambda r: r.get("hasil", {}).get("tanggal_selesai") or r.get("jadwal") or "",
            reverse=True,
        )[0]
        score = compute_survey_score(latest.get("kuisioner", {}))
        return {
            "type": "selesai",
            "score": score,
            "kesimpulan": latest.get("hasil", {}).get("kesimpulan", "-"),
        }

    if scheduled:
        nearest = sorted(scheduled, key=lambda r: r.get("jadwal") or "")[0]
        return {"type": "terjadwal", "jadwal": nearest.get("jadwal", "-")}

    return {"type": "belum"}


# ----------------------------------------------------------------------------
# Kalkulator KPR
# ----------------------------------------------------------------------------


def calculate_kpr(pinjaman, suku_bunga_tahunan, tenor_tahun, metode="anuitas"):
    """Hitung estimasi cicilan KPR.

    metode: "anuitas" (angsuran tetap berbasis sisa pokok, umum dipakai bank)
            atau "flat" (bunga dihitung tetap dari pokok awal setiap bulan).

    Mengembalikan (cicilan_bulanan, total_bunga, total_bayar, jadwal_bulanan).
    Ini adalah estimasi umum, bukan simulasi resmi dari bank tertentu.
    """
    n_bulan = int(round(tenor_tahun * 12))
    r_bulanan = (suku_bunga_tahunan / 100) / 12

    if n_bulan <= 0 or pinjaman <= 0:
        return 0.0, 0.0, 0.0, []

    schedule = []
    sisa = pinjaman

    if metode == "flat":
        pokok_tetap = pinjaman / n_bulan
        bunga_tetap = pinjaman * r_bulanan
        cicilan = pokok_tetap + bunga_tetap
        for bulan in range(1, n_bulan + 1):
            sisa = max(sisa - pokok_tetap, 0)
            schedule.append(
                {"bulan": bulan, "pokok": pokok_tetap, "bunga": bunga_tetap, "sisa": sisa}
            )
    else:
        if r_bulanan > 0:
            cicilan = (
                pinjaman * r_bulanan * (1 + r_bulanan) ** n_bulan
                / ((1 + r_bulanan) ** n_bulan - 1)
            )
        else:
            cicilan = pinjaman / n_bulan
        for bulan in range(1, n_bulan + 1):
            bunga = sisa * r_bulanan
            pokok = cicilan - bunga
            sisa = max(sisa - pokok, 0)
            schedule.append({"bulan": bulan, "pokok": pokok, "bunga": bunga, "sisa": sisa})

    total_bayar = cicilan * n_bulan
    total_bunga = total_bayar - pinjaman
    return cicilan, total_bunga, total_bayar, schedule


def summarize_yearly_schedule(schedule):
    """Ringkas jadwal amortisasi bulanan menjadi rekap per tahun."""
    rows = []
    tahun = 1
    for start in range(0, len(schedule), 12):
        chunk = schedule[start : start + 12]
        if not chunk:
            continue
        rows.append(
            {
                "Tahun": tahun,
                "Total Pokok Dibayar": sum(x["pokok"] for x in chunk),
                "Total Bunga Dibayar": sum(x["bunga"] for x in chunk),
                "Sisa Pokok": chunk[-1]["sisa"],
            }
        )
        tahun += 1
    return rows


# ----------------------------------------------------------------------------
# Load / save data rumah
# ----------------------------------------------------------------------------


def load_houses():
    """Muat data rumah dari data/houses.json."""
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        try:
            houses = json.load(f)
        except json.JSONDecodeError:
            return []
    for h in houses:
        h.setdefault("survey_records", [])
    return houses


def save_houses(houses):
    """Simpan data rumah ke data/houses.json."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(houses, f, ensure_ascii=False, indent=2)


def format_rupiah(value):
    """Format angka menjadi string 'Rp 1.850.000.000'."""
    try:
        value = int(round(float(value)))
    except (ValueError, TypeError):
        return "Rp 0"
    return "Rp " + f"{value:,.0f}".replace(",", ".")


def next_id(houses):
    """Hitung id rumah berikutnya yang belum dipakai."""
    if not houses:
        return 1
    return max(h.get("id", 0) for h in houses) + 1


def price_per_m2(house):
    """Hitung harga per meter persegi luas bangunan."""
    lb = house.get("luas_bangunan") or 0
    harga = house.get("harga") or 0
    if lb <= 0:
        return 0
    return harga / lb


# ----------------------------------------------------------------------------
# Google Drive: konversi link "Share" biasa menjadi URL yang bisa langsung
# ditampilkan sebagai gambar / video embed di aplikasi.
# ----------------------------------------------------------------------------

_GDRIVE_ID_PATTERNS = [
    r"/file/d/([a-zA-Z0-9_-]{10,})",
    r"[?&]id=([a-zA-Z0-9_-]{10,})",
    r"/d/([a-zA-Z0-9_-]{10,})",
]


def extract_gdrive_file_id(text):
    """Ambil FILE_ID dari berbagai bentuk link Google Drive, atau None kalau
    teksnya bukan link/ID Google Drive."""
    text = (text or "").strip()
    if not text:
        return None
    if "drive.google.com" in text or "docs.google.com" in text:
        for pattern in _GDRIVE_ID_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
    # Izinkan pengguna menempel FILE_ID mentah saja (tanpa URL sama sekali).
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,80}", text):
        return text
    return None


def resolve_image_source(raw):
    """Terima URL gambar biasa, link Google Drive, atau path lokal --
    kembalikan sumber yang siap dipakai st.image(). Link Google Drive
    otomatis dikonversi ke bentuk thumbnail yang bisa langsung ditampilkan."""
    raw = (raw or "").strip()
    file_id = extract_gdrive_file_id(raw)
    if file_id:
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
    return raw


def gdrive_video_file_id(raw):
    """Kalau raw adalah link/ID Google Drive, kembalikan FILE_ID-nya (dipakai
    untuk merender iframe preview video). Kembalikan None kalau bukan."""
    return extract_gdrive_file_id(raw)


# ----------------------------------------------------------------------------
# Bantuan konversi tipe data (dipakai terutama setelah data ditarik dari
# Google Sheets, di mana semua nilai bisa datang sebagai teks)
# ----------------------------------------------------------------------------


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_house_types(house):
    """Pastikan tipe data tiap field rumah benar & lengkap."""
    h = dict(house)
    h["id"] = _to_int(h.get("id"), 0)
    h["latitude"] = _to_float(h.get("latitude"), 0.0)
    h["longitude"] = _to_float(h.get("longitude"), 0.0)
    h["harga"] = _to_int(h.get("harga"), 0)
    h["luas_tanah"] = _to_int(h.get("luas_tanah"), 0)
    h["luas_bangunan"] = _to_int(h.get("luas_bangunan"), 0)
    h["kamar_tidur"] = _to_int(h.get("kamar_tidur"), 0)
    h["kamar_mandi"] = _to_int(h.get("kamar_mandi"), 0)
    h["carport"] = _to_int(h.get("carport"), 0)
    h["lantai"] = _to_int(h.get("lantai"), 1)
    h["tahun_dibangun"] = _to_int(h.get("tahun_dibangun"), 2020)
    h["estimasi_cicilan"] = _to_int(h.get("estimasi_cicilan"), 0)
    for key in ("kelebihan", "kekurangan", "gambar"):
        if not isinstance(h.get(key), list):
            h[key] = []
    if not isinstance(h.get("survey_records"), list):
        h["survey_records"] = []
    return h
