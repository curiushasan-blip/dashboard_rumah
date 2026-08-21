"""
Dasbor Komparasi Rumah
========================
Aplikasi Streamlit untuk membandingkan beberapa pilihan rumah sebelum membeli:
peta lokasi interaktif (klik marker untuk lihat detail), jadwal & kuisioner
survey per rumah, kalkulator simulasi KPR, tabel komparasi harga & spesifikasi,
serta sinkronisasi opsional ke Google Sheets. Data disimpan di data/houses.json.

Jalankan dengan:  streamlit run app.py
"""

import calendar
import json
from datetime import date, datetime

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from sheets_utils import GSPREAD_AVAILABLE, extract_sheet_id, get_client, pull_houses, push_houses
from utils import (
    KESIMPULAN_COLORS,
    KESIMPULAN_OPTIONS,
    KUISIONER_LABELS,
    STATUS_COLORS,
    STATUS_FOLIUM_COLORS,
    STATUS_OPTIONS,
    SURVEY_NUMERIC_KEYS,
    SURVEY_STATUS_COLORS,
    SURVEY_STATUS_OPTIONS,
    calculate_kpr,
    coerce_house_types,
    compute_survey_score,
    format_rupiah,
    gdrive_video_file_id,
    latest_survey_info,
    load_houses,
    next_id,
    next_survey_id,
    price_per_m2,
    resolve_image_source,
    save_houses,
    summarize_yearly_schedule,
)

# --------------------------------------------------------------------------
# Konfigurasi halaman & gaya visual
# --------------------------------------------------------------------------

st.set_page_config(
    page_title="Dasbor Komparasi Rumah",
    page_icon="\U0001F3E0",
    layout="wide",
)

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
  --paper: #F4F5F0;
  --paper-side: #ECEEE7;
  --card: #FFFFFF;
  --ink: #1C3238;
  --ink-soft: #4B5D63;
  --line: rgba(28,50,56,0.14);
  --blueprint: #2B4C63;
  --brass: #B8863B;
  --forest: #3F6B4F;
  --brick: #A24B3F;
}

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: var(--paper); }
section[data-testid="stSidebar"] { background-color: var(--paper-side); border-right: 1px solid var(--line); }

h1, h2, h3 { font-family: 'Fraunces', serif !important; color: var(--ink) !important; letter-spacing: -0.01em; }
h1 { font-weight: 700 !important; }
h2, h3 { font-weight: 600 !important; }

.eyebrow {
  font-family: 'IBM Plex Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.72rem;
  color: var(--ink-soft);
  margin-bottom: 0.2rem;
}

.stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {
  background-color: var(--blueprint);
  color: #F4F5F0;
  border: 1px solid var(--blueprint);
  border-radius: 6px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.85rem;
  letter-spacing: 0.03em;
}
.stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {
  background-color: var(--ink);
  border-color: var(--ink);
  color: #F4F5F0;
}

button[data-baseweb="tab"] {
  font-family: 'IBM Plex Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 0.74rem;
  color: var(--ink-soft);
}
button[data-baseweb="tab"][aria-selected="true"] {
  color: var(--ink) !important;
  border-bottom: 2px solid var(--brass) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
  background-color: var(--card);
  border: 1px solid var(--line) !important;
  border-radius: 8px;
}

div[data-testid="stMetric"] {
  background-color: var(--card);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
}
div[data-testid="stMetricLabel"] {
  font-family: 'IBM Plex Mono', monospace;
  text-transform: uppercase;
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  color: var(--ink-soft);
}
div[data-testid="stMetricValue"] { font-family: 'Fraunces', serif; color: var(--ink); }

.stamp {
  display: inline-block;
  font-family: 'IBM Plex Mono', monospace;
  font-weight: 600;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.22rem 0.65rem;
  border: 2px solid currentColor;
  border-radius: 3px;
  transform: rotate(-2deg);
}

.index-tag {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.75rem;
  color: var(--ink-soft);
  letter-spacing: 0.05em;
}

.price-plate {
  font-family: 'Fraunces', serif;
  font-weight: 700;
  font-size: 2rem;
  color: var(--blueprint);
  font-variant-numeric: tabular-nums;
}
"""

st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Sumber data awal: Google Sheets (jika sudah dikonfigurasi) -> file lokal
# --------------------------------------------------------------------------

def _configured_sheet_id():
    """Kembalikan sheet_id kalau kredensial Google + sheet_id sudah diatur di
    secrets, atau None kalau belum (dicek dengan aman -- tidak melempar error
    walau secrets.toml belum ada sama sekali)."""
    if not GSPREAD_AVAILABLE:
        return None
    try:
        has_creds = "gcp_service_account" in st.secrets
        raw_sheet_id = st.secrets.get("sheet_id", "") if has_creds else ""
    except Exception:
        return None
    if has_creds and raw_sheet_id:
        return extract_sheet_id(raw_sheet_id)
    return None


def load_initial_houses():
    """Tentukan data awal saat aplikasi pertama kali dibuka.

    1) Kalau kredensial & sheet_id Google Sheets sudah diatur (lewat
       .streamlit/secrets.toml, atau Secrets di Streamlit Community Cloud),
       coba tarik data dari sana lebih dulu -- ini penting terutama saat
       aplikasi dijalankan di cloud, karena penyimpanan file lokal di sana
       bersifat sementara dan bisa kembali ke data contoh setelah server
       restart. Google Sheets jadi sumber data yang persisten.
    2) Kalau Sheets belum dikonfigurasi, atau penarikan datanya gagal
       (belum ada worksheet, koneksi bermasalah, dll), aplikasi otomatis
       jatuh kembali memakai file lokal data/houses.json seperti biasa.
    """
    sheet_id = _configured_sheet_id()
    if sheet_id:
        try:
            gc = get_client()
            pulled = pull_houses(gc, sheet_id)
            if pulled:
                st.session_state["_data_source"] = "sheets"
                return [coerce_house_types(h) for h in pulled]
            st.session_state["_data_source"] = "sheets_empty"
        except Exception as exc:
            st.session_state["_data_source"] = "sheets_error"
            st.session_state["_data_source_error"] = str(exc)

    st.session_state.setdefault("_data_source", "local")
    return load_houses()


# --------------------------------------------------------------------------
# State awal
# --------------------------------------------------------------------------

if "houses" not in st.session_state:
    st.session_state.houses = load_initial_houses()
if "selected_id" not in st.session_state:
    st.session_state.selected_id = (
        st.session_state.houses[0]["id"] if st.session_state.houses else None
    )


# --------------------------------------------------------------------------
# Sidebar: filter & kelola data
# --------------------------------------------------------------------------

def sidebar_filters(houses):
    st.sidebar.markdown('<div class="eyebrow">Filter Pencarian</div>', unsafe_allow_html=True)
    keyword = st.sidebar.text_input("Cari nama / alamat", "")

    prices = [h.get("harga", 0) for h in houses]
    if prices:
        min_price, max_price = int(min(prices)), int(max(prices))
    else:
        min_price, max_price = 0, 1_000_000_000
    if min_price == max_price:
        max_price = min_price + 10_000_000

    price_range = st.sidebar.slider(
        "Rentang Harga (Rp)",
        min_value=min_price,
        max_value=max_price,
        value=(min_price, max_price),
        step=10_000_000,
    )

    min_kt = st.sidebar.slider("Minimal Kamar Tidur", 0, 6, 0)

    status_options = sorted(set(h.get("status", "-") for h in houses)) or STATUS_OPTIONS
    status_filter = st.sidebar.multiselect("Status", options=status_options, default=status_options)

    st.sidebar.divider()
    st.sidebar.markdown('<div class="eyebrow">Kelola Data</div>', unsafe_allow_html=True)

    source = st.session_state.get("_data_source", "local")
    if source == "sheets":
        st.sidebar.caption("\U0001F4E1 Data dimuat dari Google Sheets.")
    elif source == "sheets_empty":
        st.sidebar.caption("\U0001F4E1 Google Sheets terhubung tapi belum ada data \u2014 memakai data lokal.")
    elif source == "sheets_error":
        st.sidebar.caption("\u26A0\uFE0F Gagal menarik dari Google Sheets, memakai data lokal sebagai cadangan.")
    else:
        st.sidebar.caption("\U0001F4BE Data dimuat dari file lokal (data/houses.json).")

    col_a, col_b = st.sidebar.columns(2)
    if col_a.button("Simpan", use_container_width=True):
        save_houses(st.session_state.houses)
        st.sidebar.success("Tersimpan ke data/houses.json")
    if col_b.button("Muat Ulang", use_container_width=True):
        st.session_state.houses = load_initial_houses()
        st.rerun()

    st.sidebar.download_button(
        "Unduh JSON",
        data=json.dumps(st.session_state.houses, ensure_ascii=False, indent=2),
        file_name="houses_export.json",
        mime="application/json",
        use_container_width=True,
    )

    return {
        "keyword": keyword.strip().lower(),
        "price_range": price_range,
        "min_kt": min_kt,
        "status": status_filter,
    }


def apply_filters(houses, filters):
    result = []
    for h in houses:
        haystack = f"{h.get('nama', '')} {h.get('alamat', '')}".lower()
        if filters["keyword"] and filters["keyword"] not in haystack:
            continue
        harga = h.get("harga", 0)
        if not (filters["price_range"][0] <= harga <= filters["price_range"][1]):
            continue
        if h.get("kamar_tidur", 0) < filters["min_kt"]:
            continue
        if filters["status"] and h.get("status") not in filters["status"]:
            continue
        result.append(h)
    return result


# --------------------------------------------------------------------------
# Badge kecil (stempel)
# --------------------------------------------------------------------------

def render_stamp(text, color):
    st.markdown(
        f'<span class="stamp" style="color:{color}; background-color:{color}22;">{text}</span>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Kartu detail rumah
# --------------------------------------------------------------------------

def render_detail(house):
    with st.container(border=True):
        top_l, top_r = st.columns([3, 1])
        with top_l:
            st.markdown(
                f'<div class="index-tag">DOSIR NO. {house["id"]:03d}</div>',
                unsafe_allow_html=True,
            )
            st.header(house["nama"])
            st.caption(f"\U0001F4CD {house['alamat']}")
        with top_r:
            render_stamp(house.get("status", "Pertimbangan"), STATUS_COLORS.get(house.get("status"), "#4B5D63"))

        st.markdown(
            f'<div class="price-plate">{format_rupiah(house["harga"])}</div>',
            unsafe_allow_html=True,
        )
        ppm2 = price_per_m2(house)
        sub_bits = []
        if ppm2:
            sub_bits.append(f"\u00b1 {format_rupiah(ppm2)} / m\u00b2 bangunan")
        if house.get("estimasi_cicilan"):
            sub_bits.append(f"est. cicilan KPR {format_rupiah(house['estimasi_cicilan'])}/bulan")
        if sub_bits:
            st.markdown(
                f'<span class="eyebrow">{"  \u00b7  ".join(sub_bits)}</span>', unsafe_allow_html=True
            )

        st.write("")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("LT", f'{house.get("luas_tanah", 0)} m\u00b2')
        c2.metric("LB", f'{house.get("luas_bangunan", 0)} m\u00b2')
        c3.metric("KT", house.get("kamar_tidur", 0))
        c4.metric("KM", house.get("kamar_mandi", 0))
        c5.metric("Carport", house.get("carport", 0))
        c6.metric("Lantai", house.get("lantai", 1))

        st.write("")
        info_c1, info_c2 = st.columns(2)
        with info_c1:
            st.markdown(f"**Sertifikat:** {house.get('sertifikat', '-')}")
            st.markdown(f"**Hadap:** {house.get('hadap', '-') or '-'}")
        with info_c2:
            st.markdown(f"**Tahun dibangun:** {house.get('tahun_dibangun', '-')}")
            st.markdown(f"**Developer/Agen:** {house.get('developer', '-') or '-'}")

        info = latest_survey_info(house)
        st.write("")
        if info["type"] == "selesai":
            st.markdown(f"**Status Survey:** skor {info['score']:.1f}/5 \u2014 ")
            render_stamp(info["kesimpulan"], KESIMPULAN_COLORS.get(info["kesimpulan"], "#4B5D63"))
        elif info["type"] == "terjadwal":
            st.markdown(f"**Status Survey:** terjadwal pada {info['jadwal']}")
        else:
            st.caption("Belum ada jadwal survey untuk rumah ini (lihat tab \U0001F5D3\uFE0F Survey).")

        if house.get("deskripsi"):
            st.markdown("**Deskripsi**")
            st.write(house["deskripsi"])

        adv_c, dis_c = st.columns(2)
        with adv_c:
            st.markdown("**\u2705 Kelebihan**")
            for k in house.get("kelebihan", []):
                st.markdown(f"- {k}")
        with dis_c:
            st.markdown("**\u26A0\uFE0F Catatan**")
            for k in house.get("kekurangan", []):
                st.markdown(f"- {k}")

        images = house.get("gambar", [])
        if images:
            st.markdown("**\U0001F4F7 Galeri**")
            cols = st.columns(min(len(images), 3))
            for i, img in enumerate(images):
                with cols[i % len(cols)]:
                    try:
                        st.image(resolve_image_source(img), use_container_width=True)
                    except Exception:
                        st.caption("Gambar tidak dapat dimuat.")

        video = house.get("video")
        st.markdown("**\U0001F3AC Video**")
        if video:
            drive_id = gdrive_video_file_id(video)
            if drive_id:
                st.markdown(
                    f'<iframe src="https://drive.google.com/file/d/{drive_id}/preview" '
                    'width="100%" height="480" allow="autoplay" '
                    'style="border:none; border-radius:8px;"></iframe>',
                    unsafe_allow_html=True,
                )
            else:
                st.video(video)
        else:
            st.caption(
                "Belum ada video walkthrough. Tambahkan URL YouTube, link Google Drive, "
                "atau path video lokal pada tab 'Kelola Data'."
            )

        if house.get("kontak_agen") or house.get("sumber_listing"):
            st.divider()
            if house.get("kontak_agen"):
                st.caption(f"\U0001F4DE Kontak: {house['kontak_agen']}")
            if house.get("sumber_listing"):
                st.caption(f"\U0001F517 Sumber listing: {house['sumber_listing']}")


# --------------------------------------------------------------------------
# Tab 1: Peta & Detail
# --------------------------------------------------------------------------

def render_map_tab(filtered):
    if not filtered:
        st.info("Tidak ada rumah yang cocok dengan filter saat ini.")
        return

    col_map, col_detail = st.columns([1.3, 1])

    with col_map:
        avg_lat = sum(h["latitude"] for h in filtered) / len(filtered)
        avg_lng = sum(h["longitude"] for h in filtered) / len(filtered)
        m = folium.Map(location=[avg_lat, avg_lng], zoom_start=10, tiles="cartodbpositron")

        for h in filtered:
            color = STATUS_FOLIUM_COLORS.get(h.get("status"), "gray")
            popup_html = f"<b>{h['nama']}</b><br>{format_rupiah(h['harga'])}<br>{h['alamat']}"
            folium.Marker(
                location=[h["latitude"], h["longitude"]],
                tooltip=f"{h['id']} | {h['nama']}",
                popup=folium.Popup(popup_html, max_width=260),
                icon=folium.Icon(color=color, icon="home", prefix="fa"),
            ).add_to(m)

        map_data = st_folium(m, height=560, use_container_width=True, key="house_map")

        clicked_tooltip = (map_data or {}).get("last_object_clicked_tooltip")
        if clicked_tooltip and clicked_tooltip != st.session_state.get("_last_map_click"):
            st.session_state["_last_map_click"] = clicked_tooltip
            if "|" in clicked_tooltip:
                try:
                    st.session_state.selected_id = int(clicked_tooltip.split("|")[0].strip())
                except ValueError:
                    pass

        legend_html = " &nbsp;\u00b7&nbsp; ".join(
            f'<span class="eyebrow" style="color:{STATUS_COLORS.get(s, "#4B5D63")}">\u25CF {s}</span>'
            for s in STATUS_OPTIONS
        )
        st.markdown(legend_html, unsafe_allow_html=True)
        st.caption("Klik marker di peta untuk menampilkan detail rumah di panel sebelah kanan.")

    with col_detail:
        names = [h["nama"] for h in filtered]
        ids = [h["id"] for h in filtered]
        name_by_id = dict(zip(ids, names))
        current_name = name_by_id.get(st.session_state.selected_id, names[0])

        selector_key = f"house_selector_{st.session_state.selected_id}"
        chosen_name = st.selectbox(
            "Atau pilih dari daftar",
            options=names,
            index=names.index(current_name) if current_name in names else 0,
            key=selector_key,
        )
        chosen_id = next((h["id"] for h in filtered if h["nama"] == chosen_name), None)
        if chosen_id is not None:
            st.session_state.selected_id = chosen_id

        selected_house = next(
            (h for h in filtered if h["id"] == st.session_state.selected_id), filtered[0]
        )
        render_detail(selected_house)


# --------------------------------------------------------------------------
# Tab 2: Survey (jadwal, kuisioner, hasil) - per rumah
# --------------------------------------------------------------------------

def render_survey_record(house, rec, key_prefix=""):
    with st.container(border=True):
        top1, top2 = st.columns([3, 1])
        with top1:
            st.markdown(f"**\U0001F4C5 {rec.get('jadwal', '-')}**")
            st.caption(f"Surveyor/PIC: {rec.get('surveyor') or '-'}")
            if rec.get("catatan_persiapan"):
                st.caption(f"\U0001F4CC Persiapan: {rec['catatan_persiapan']}")
        with top2:
            render_stamp(rec.get("status", "Terjadwal"), SURVEY_STATUS_COLORS.get(rec.get("status"), "#4B5D63"))

        if rec.get("status") == "Selesai":
            k = rec.get("kuisioner", {}) or {}
            hasil = rec.get("hasil", {}) or {}
            score = compute_survey_score(k)
            st.markdown(f"**Skor Kuisioner: {score:.1f} / 5**")
            df_k = pd.DataFrame(
                {
                    "Aspek": [KUISIONER_LABELS.get(key, key) for key in SURVEY_NUMERIC_KEYS],
                    "Nilai": [k.get(key, "-") for key in SURVEY_NUMERIC_KEYS],
                }
            )
            st.dataframe(df_k, use_container_width=True, hide_index=True)
            extra_bits = []
            if k.get("potensi_banjir"):
                extra_bits.append(f"Potensi banjir: {k['potensi_banjir']}")
            if k.get("legalitas_dicek"):
                extra_bits.append(f"Legalitas dicek: {k['legalitas_dicek']}")
            if extra_bits:
                st.caption(" \u00b7 ".join(extra_bits))
            if k.get("catatan_tambahan"):
                st.markdown(f"**Catatan survei:** {k['catatan_tambahan']}")
            if hasil.get("kesimpulan"):
                render_stamp(hasil["kesimpulan"], KESIMPULAN_COLORS.get(hasil["kesimpulan"], "#4B5D63"))
            if hasil.get("catatan_hasil"):
                st.markdown(f"**Kesimpulan:** {hasil['catatan_hasil']}")

        toggle_key = f"toggle_form_{key_prefix}{house['id']}_{rec['id']}"
        action_c1, action_c2, action_c3 = st.columns(3)
        if rec.get("status") == "Terjadwal":
            if action_c1.button(
                "\u2705 Isi Hasil", key=f"btn_selesai_{key_prefix}{house['id']}_{rec['id']}", use_container_width=True
            ):
                st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
            if action_c2.button(
                "\u274C Batalkan", key=f"btn_batal_{key_prefix}{house['id']}_{rec['id']}", use_container_width=True
            ):
                rec["status"] = "Dibatalkan"
                save_houses(st.session_state.houses)
                st.rerun()
        elif rec.get("status") == "Selesai":
            if action_c1.button(
                "\u270F\uFE0F Edit Hasil", key=f"btn_edit_{key_prefix}{house['id']}_{rec['id']}", use_container_width=True
            ):
                st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
        if action_c3.button(
            "\U0001F5D1\uFE0F Hapus", key=f"btn_hapus_{key_prefix}{house['id']}_{rec['id']}", use_container_width=True
        ):
            house["survey_records"] = [r for r in house["survey_records"] if r["id"] != rec["id"]]
            save_houses(st.session_state.houses)
            if st.session_state.get("cal_selected") == (house["id"], rec["id"]):
                st.session_state["cal_selected"] = None
            st.rerun()

        if st.session_state.get(toggle_key):
            render_kuisioner_form(house, rec, toggle_key, key_prefix=key_prefix)


def render_kuisioner_form(house, rec, toggle_key, key_prefix=""):
    k = rec.get("kuisioner", {}) or {}
    hasil = rec.get("hasil", {}) or {}
    banjir_options = ["Tidak", "Ya", "Tidak Tahu"]
    legal_options = ["Ya", "Belum"]

    with st.form(f"form_kuisioner_{key_prefix}{house['id']}_{rec['id']}"):
        st.markdown("**Kuisioner Survey** \u2014 nilai 1 (buruk) sampai 5 (sangat baik)")
        new_k = {}
        for key in SURVEY_NUMERIC_KEYS:
            new_k[key] = st.slider(
                KUISIONER_LABELS.get(key, key),
                1, 5, int(k.get(key, 3)),
                key=f"kf_{key_prefix}{house['id']}_{rec['id']}_{key}",
            )
        c1, c2 = st.columns(2)
        new_k["potensi_banjir"] = c1.selectbox(
            "Potensi Banjir", banjir_options,
            index=banjir_options.index(k["potensi_banjir"]) if k.get("potensi_banjir") in banjir_options else 0,
            key=f"kf_banjir_{key_prefix}{house['id']}_{rec['id']}",
        )
        new_k["legalitas_dicek"] = c2.selectbox(
            "Legalitas Dokumen Sudah Dicek", legal_options,
            index=legal_options.index(k["legalitas_dicek"]) if k.get("legalitas_dicek") in legal_options else 1,
            key=f"kf_legal_{key_prefix}{house['id']}_{rec['id']}",
        )
        new_k["catatan_tambahan"] = st.text_area(
            "Catatan Tambahan Hasil Survei",
            value=k.get("catatan_tambahan", ""),
            key=f"kf_catatan_{key_prefix}{house['id']}_{rec['id']}",
        )

        st.markdown("**Kesimpulan**")
        kesimpulan = st.selectbox(
            "Kesimpulan", KESIMPULAN_OPTIONS,
            index=KESIMPULAN_OPTIONS.index(hasil["kesimpulan"]) if hasil.get("kesimpulan") in KESIMPULAN_OPTIONS else 0,
            key=f"kf_kesimpulan_{key_prefix}{house['id']}_{rec['id']}",
        )
        catatan_hasil = st.text_area(
            "Catatan Kesimpulan",
            value=hasil.get("catatan_hasil", ""),
            key=f"kf_hasilcatatan_{key_prefix}{house['id']}_{rec['id']}",
        )

        if st.form_submit_button("Simpan Hasil Survei"):
            rec["kuisioner"] = new_k
            rec["status"] = "Selesai"
            rec["hasil"] = {
                "kesimpulan": kesimpulan,
                "catatan_hasil": catatan_hasil,
                "tanggal_selesai": str(date.today()),
            }
            save_houses(st.session_state.houses)
            st.session_state[toggle_key] = False
            st.success("Hasil survei disimpan.")
            st.rerun()


def render_survey_rekap(houses):
    rows = []
    for h in houses:
        info = latest_survey_info(h)
        if info["type"] == "selesai":
            rows.append(
                {
                    "Rumah": h["nama"],
                    "Skor Terakhir": round(info["score"], 1),
                    "Kesimpulan": info["kesimpulan"],
                    "Keterangan": "-",
                }
            )
        elif info["type"] == "terjadwal":
            rows.append(
                {
                    "Rumah": h["nama"],
                    "Skor Terakhir": None,
                    "Kesimpulan": "-",
                    "Keterangan": f"Survey terjadwal: {info['jadwal']}",
                }
            )
        else:
            rows.append(
                {"Rumah": h["nama"], "Skor Terakhir": None, "Kesimpulan": "-", "Keterangan": "Belum ada jadwal survey"}
            )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    df_chart = df.dropna(subset=["Skor Terakhir"])
    if not df_chart.empty:
        fig = px.bar(
            df_chart, x="Rumah", y="Skor Terakhir", color="Rumah",
            color_discrete_sequence=["#2B4C63", "#B8863B", "#3F6B4F", "#A24B3F", "#4B5D63", "#6B8E9A"],
            range_y=[0, 5],
        )
        fig.update_layout(
            showlegend=False, plot_bgcolor="#F4F5F0", paper_bgcolor="#F4F5F0", font_family="IBM Plex Sans"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Belum ada survey yang selesai untuk ditampilkan skornya.")


def _all_survey_entries(houses):
    """Kumpulkan semua jadwal survey dari seluruh rumah, sudah di-parse tanggalnya."""
    entries = []
    for h in houses:
        for rec in h.get("survey_records", []):
            try:
                dt = datetime.strptime(rec.get("jadwal", ""), "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                continue
            entries.append({"house": h, "rec": rec, "dt": dt})
    return entries


SURVEY_STATUS_EMOJI = {"Terjadwal": "\U0001F553", "Selesai": "\u2705", "Dibatalkan": "\u274C"}

BULAN_NAMA = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def render_calendar_tab(houses):
    today = date.today()
    st.session_state.setdefault("cal_year", today.year)
    st.session_state.setdefault("cal_month", today.month)

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    if nav1.button("\u2190 Bulan Lalu", use_container_width=True, key="cal_prev"):
        m, y = st.session_state.cal_month - 1, st.session_state.cal_year
        if m < 1:
            m, y = 12, y - 1
        st.session_state.cal_month, st.session_state.cal_year = m, y
        st.rerun()
    if nav3.button("Bulan Depan \u2192", use_container_width=True, key="cal_next"):
        m, y = st.session_state.cal_month + 1, st.session_state.cal_year
        if m > 12:
            m, y = 1, y + 1
        st.session_state.cal_month, st.session_state.cal_year = m, y
        st.rerun()
    with nav2:
        st.markdown(
            f"<h3 style='text-align:center; margin:0;'>"
            f"{BULAN_NAMA[st.session_state.cal_month]} {st.session_state.cal_year}</h3>",
            unsafe_allow_html=True,
        )
        if st.button("Hari Ini", use_container_width=True, key="cal_today"):
            st.session_state.cal_year, st.session_state.cal_month = today.year, today.month
            st.rerun()

    st.caption(
        "\U0001F553 Terjadwal \u00b7 \u2705 Selesai \u00b7 \u274C Dibatalkan "
        "\u2014 klik salah satu jadwal untuk melihat/mengedit detailnya."
    )

    entries_by_day = {}
    for e in _all_survey_entries(houses):
        d = e["dt"].date()
        if d.year == st.session_state.cal_year and d.month == st.session_state.cal_month:
            entries_by_day.setdefault(d.day, []).append(e)

    weekday_labels = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
    header_cols = st.columns(7)
    for col, label in zip(header_cols, weekday_labels):
        col.markdown(f'<div class="eyebrow" style="text-align:center">{label}</div>', unsafe_allow_html=True)

    weeks = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
    for week in weeks:
        cols = st.columns(7)
        for col, day in zip(cols, week):
            with col:
                if day == 0:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    continue
                is_today = (
                    day == today.day
                    and st.session_state.cal_month == today.month
                    and st.session_state.cal_year == today.year
                )
                box_style = (
                    "background-color:#2B4C6322; border:1px solid #2B4C63;"
                    if is_today
                    else "border:1px solid var(--line); background-color:var(--card);"
                )
                st.markdown(
                    f'<div style="{box_style} border-radius:6px 6px 0 0; padding:3px 6px;">'
                    f'<span style="font-family:\'IBM Plex Mono\', monospace; font-size:0.78rem; color:var(--ink-soft);">{day}</span>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                day_entries = sorted(entries_by_day.get(day, []), key=lambda e: e["dt"])
                for e in day_entries:
                    emoji = SURVEY_STATUS_EMOJI.get(e["rec"].get("status"), "\u2022")
                    nama_singkat = e["house"]["nama"]
                    if len(nama_singkat) > 16:
                        nama_singkat = nama_singkat[:15] + "\u2026"
                    label = f'{emoji} {e["dt"].strftime("%H:%M")} {nama_singkat}'
                    btn_key = f'cal_{e["house"]["id"]}_{e["rec"]["id"]}'
                    if st.button(label, key=btn_key, use_container_width=True):
                        st.session_state["cal_selected"] = (e["house"]["id"], e["rec"]["id"])
                        st.rerun()

    st.divider()
    selected = st.session_state.get("cal_selected")
    if selected:
        house_id, rec_id = selected
        house = next((h for h in houses if h["id"] == house_id), None)
        rec = next((r for r in house.get("survey_records", []) if r["id"] == rec_id), None) if house else None
        if house and rec:
            st.markdown(f"##### Detail Jadwal \u2014 {house['nama']}")
            render_survey_record(house, rec, key_prefix="cal_")
        else:
            st.session_state["cal_selected"] = None
            st.caption("Jadwal yang dipilih sudah tidak tersedia (mungkin telah dihapus).")
    else:
        st.caption("Belum ada jadwal dipilih.")


def render_survey_tab():
    houses = st.session_state.houses
    if not houses:
        st.info("Tambahkan data rumah terlebih dahulu di tab 'Kelola Data'.")
        return

    sub_kelola, sub_kalender, sub_rekap = st.tabs(
        ["\U0001F4DD Jadwal & Kuisioner", "\U0001F4C5 Kalender", "\U0001F4CA Rekap Semua Rumah"]
    )

    with sub_kelola:
        names = [h["nama"] for h in houses]
        pilihan = st.selectbox("Pilih rumah", names, key="survey_house_selector")
        house = next(h for h in houses if h["nama"] == pilihan)
        house.setdefault("survey_records", [])

        st.markdown("##### \u2795 Jadwalkan Survey Baru")
        with st.form(f"form_jadwal_baru_{house['id']}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            tgl = c1.date_input("Tanggal", key=f"tgl_{house['id']}")
            wkt = c2.time_input("Waktu", key=f"wkt_{house['id']}")
            surveyor = st.text_input("Surveyor / PIC", key=f"surveyor_{house['id']}")
            catatan_persiapan = st.text_area("Catatan Persiapan (opsional)", key=f"prep_{house['id']}")
            if st.form_submit_button("Simpan Jadwal"):
                rec = {
                    "id": next_survey_id(house),
                    "jadwal": f"{tgl} {wkt.strftime('%H:%M')}",
                    "surveyor": surveyor,
                    "status": "Terjadwal",
                    "catatan_persiapan": catatan_persiapan,
                    "kuisioner": {},
                    "hasil": {},
                }
                house["survey_records"].append(rec)
                save_houses(st.session_state.houses)
                st.success("Jadwal survey ditambahkan.")
                st.rerun()

        st.divider()
        st.markdown(f"##### Riwayat Survey \u2014 {house['nama']}")
        records = sorted(house["survey_records"], key=lambda r: r.get("jadwal", ""), reverse=True)
        if not records:
            st.caption("Belum ada jadwal survey untuk rumah ini.")
        for rec in records:
            render_survey_record(house, rec, key_prefix="k_")

    with sub_kalender:
        render_calendar_tab(houses)

    with sub_rekap:
        render_survey_rekap(houses)


# --------------------------------------------------------------------------
# Tab 3: Kalkulator KPR
# --------------------------------------------------------------------------

def render_kpr_tab():
    st.markdown("#### \U0001F9EE Kalkulator Simulasi KPR")
    st.caption(
        "Simulasi estimasi cicilan KPR (Kredit Pemilikan Rumah) \u2014 perkiraan umum, "
        "bukan penawaran resmi dari bank manapun."
    )

    houses = st.session_state.houses
    house_names = ["(Isi manual)"] + [h["nama"] for h in houses]
    pilihan = st.selectbox("Gunakan harga dari rumah:", house_names, key="kpr_house_pick")

    selected_house = None
    default_harga = 1_000_000_000
    if pilihan != "(Isi manual)":
        selected_house = next(h for h in houses if h["nama"] == pilihan)
        default_harga = selected_house["harga"]

    c1, c2 = st.columns(2)
    harga_rumah = c1.number_input("Harga Rumah (Rp)", min_value=0, step=10_000_000, value=int(default_harga))
    dp_persen = c2.slider("Uang Muka / DP (%)", 0, 90, 20)

    dp_rupiah = harga_rumah * dp_persen / 100
    plafon = harga_rumah - dp_rupiah

    c3, c4, c5 = st.columns(3)
    bunga = c3.number_input("Suku Bunga per Tahun (%)", min_value=0.0, max_value=30.0, value=6.5, step=0.1)
    tenor = c4.slider("Tenor (tahun)", 1, 30, 15)
    metode_label = c5.selectbox("Metode Bunga", ["Anuitas (paling umum)", "Flat"])
    metode = "anuitas" if metode_label.startswith("Anuitas") else "flat"

    cicilan, total_bunga, total_bayar, schedule = calculate_kpr(plafon, bunga, tenor, metode)

    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Uang Muka (DP)", format_rupiah(dp_rupiah))
    m2.metric("Plafon Kredit", format_rupiah(plafon))
    m3.metric("Cicilan / Bulan", format_rupiah(cicilan))
    m4.metric("Total Bunga", format_rupiah(total_bunga))

    st.write("")
    penghasilan = st.number_input(
        "Penghasilan Bersih per Bulan (Rp) \u2014 opsional, untuk cek kemampuan bayar",
        min_value=0, step=1_000_000, value=0,
    )
    if penghasilan > 0 and cicilan > 0:
        dsr = cicilan / penghasilan * 100
        if dsr <= 30:
            st.success(
                f"Rasio cicilan terhadap penghasilan: {dsr:.1f}% \u2014 umumnya masih aman "
                "(aturan umum bank: maks. \u2264 30-40%)."
            )
        elif dsr <= 40:
            st.warning(
                f"Rasio cicilan terhadap penghasilan: {dsr:.1f}% \u2014 mendekati batas atas, "
                "pertimbangkan DP lebih besar atau tenor lebih panjang."
            )
        else:
            st.error(
                f"Rasio cicilan terhadap penghasilan: {dsr:.1f}% \u2014 cukup berat, "
                "KPR mungkin sulit disetujui bank."
            )

    with st.expander("\U0001F4C4 Estimasi Biaya Tambahan di Awal (provisi, BPHTB, notaris)"):
        b1, b2 = st.columns(2)
        provisi_persen = b1.number_input("Biaya Provisi Bank (%)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
        biaya_notaris = b2.number_input(
            "Notaris + Appraisal + Asuransi (Rp)", min_value=0, step=500_000, value=5_000_000
        )
        b3, b4 = st.columns(2)
        bphtb_persen = b3.number_input("BPHTB (%)", min_value=0.0, max_value=10.0, value=5.0, step=0.5)
        npoptkp = b4.number_input("NPOPTKP / Nilai Tidak Kena Pajak (Rp)", min_value=0, step=5_000_000, value=60_000_000)
        st.caption("NPOPTKP berbeda tiap daerah \u2014 cek ke kantor pajak daerah/notaris setempat untuk angka pasti.")

        biaya_provisi = plafon * provisi_persen / 100
        bphtb = max(harga_rumah - npoptkp, 0) * bphtb_persen / 100
        total_awal = dp_rupiah + biaya_provisi + biaya_notaris + bphtb

        st.markdown(f"- Biaya Provisi: **{format_rupiah(biaya_provisi)}**")
        st.markdown(f"- BPHTB: **{format_rupiah(bphtb)}**")
        st.markdown(f"- Notaris + Appraisal + Asuransi: **{format_rupiah(biaya_notaris)}**")
        st.markdown(f"- **Total dana yang perlu disiapkan di awal (termasuk DP): {format_rupiah(total_awal)}**")

    if schedule:
        yearly = summarize_yearly_schedule(schedule)
        df_yearly = pd.DataFrame(yearly)
        fig = px.bar(
            df_yearly, x="Tahun", y=["Total Pokok Dibayar", "Total Bunga Dibayar"], barmode="stack",
            color_discrete_map={"Total Pokok Dibayar": "#2B4C63", "Total Bunga Dibayar": "#B8863B"},
            labels={"value": "Rp", "variable": "Komponen"},
        )
        fig.update_layout(
            plot_bgcolor="#F4F5F0", paper_bgcolor="#F4F5F0", font_family="IBM Plex Sans", legend_title_text=""
        )
        st.markdown("**Komposisi Pokok vs Bunga per Tahun**")
        st.plotly_chart(fig, use_container_width=True)

    if selected_house is not None and cicilan > 0:
        if st.button(f"\U0001F4BE Simpan estimasi cicilan ke '{selected_house['nama']}'"):
            for h in st.session_state.houses:
                if h["id"] == selected_house["id"]:
                    h["estimasi_cicilan"] = int(cicilan)
            save_houses(st.session_state.houses)
            st.success("Estimasi cicilan disimpan. Akan muncul di panel detail & tabel komparasi.")


# --------------------------------------------------------------------------
# Tab 4: Komparasi
# --------------------------------------------------------------------------

def render_compare_tab(filtered):
    if len(filtered) < 2:
        st.info("Perlu minimal 2 rumah (setelah filter) untuk dibandingkan.")
        return

    names = [h["nama"] for h in filtered]
    default = names[: min(3, len(names))]
    chosen = st.multiselect("Pilih rumah untuk dibandingkan", options=names, default=default)
    chosen_houses = [h for h in filtered if h["nama"] in chosen]

    if len(chosen_houses) < 2:
        st.info("Pilih minimal 2 rumah untuk melihat tabel & grafik komparasi.")
        return

    def survey_score_label(h):
        info = latest_survey_info(h)
        if info["type"] == "selesai":
            return f"{info['score']:.1f}/5 ({info['kesimpulan']})"
        if info["type"] == "terjadwal":
            return f"Terjadwal {info['jadwal']}"
        return "Belum disurvey"

    rows = {
        "Harga": [format_rupiah(h["harga"]) for h in chosen_houses],
        "Harga / m\u00b2 Bangunan": [format_rupiah(price_per_m2(h)) for h in chosen_houses],
        "Estimasi Cicilan KPR/Bulan": [
            format_rupiah(h["estimasi_cicilan"]) if h.get("estimasi_cicilan") else "-" for h in chosen_houses
        ],
        "Skor Survey": [survey_score_label(h) for h in chosen_houses],
        "Luas Tanah (m\u00b2)": [h.get("luas_tanah") for h in chosen_houses],
        "Luas Bangunan (m\u00b2)": [h.get("luas_bangunan") for h in chosen_houses],
        "Kamar Tidur": [h.get("kamar_tidur") for h in chosen_houses],
        "Kamar Mandi": [h.get("kamar_mandi") for h in chosen_houses],
        "Carport": [h.get("carport") for h in chosen_houses],
        "Lantai": [h.get("lantai") for h in chosen_houses],
        "Sertifikat": [h.get("sertifikat") for h in chosen_houses],
        "Tahun Dibangun": [h.get("tahun_dibangun") for h in chosen_houses],
        "Status": [h.get("status") for h in chosen_houses],
        "Alamat": [h.get("alamat") for h in chosen_houses],
    }
    df = pd.DataFrame(rows, index=[h["nama"] for h in chosen_houses]).T
    st.dataframe(df, use_container_width=True)

    chart_df = pd.DataFrame(
        {
            "Rumah": [h["nama"] for h in chosen_houses],
            "Harga": [h["harga"] for h in chosen_houses],
            "Label": [format_rupiah(h["harga"]) for h in chosen_houses],
        }
    )
    palette = ["#2B4C63", "#B8863B", "#3F6B4F", "#A24B3F", "#4B5D63", "#6B8E9A"]
    fig = px.bar(
        chart_df, x="Rumah", y="Harga", text="Label", color="Rumah",
        color_discrete_sequence=palette,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        showlegend=False,
        plot_bgcolor="#F4F5F0",
        paper_bgcolor="#F4F5F0",
        font_family="IBM Plex Sans",
        yaxis_title="Harga (Rp)",
        margin=dict(t=30, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Kelebihan & Catatan")
    cols = st.columns(len(chosen_houses))
    for col, h in zip(cols, chosen_houses):
        with col:
            st.markdown(f"**{h['nama']}**")
            for k in h.get("kelebihan", []):
                st.markdown(f"\u2705 {k}")
            for k in h.get("kekurangan", []):
                st.markdown(f"\u26A0\uFE0F {k}")


# --------------------------------------------------------------------------
# Tab 5: Semua Data
# --------------------------------------------------------------------------

def render_table_tab(filtered):
    if not filtered:
        st.info("Tidak ada data untuk ditampilkan.")
        return

    df = pd.DataFrame(
        [
            {
                "Nama": h["nama"],
                "Alamat": h["alamat"],
                "Harga": h["harga"],
                "LT (m\u00b2)": h.get("luas_tanah"),
                "LB (m\u00b2)": h.get("luas_bangunan"),
                "KT": h.get("kamar_tidur"),
                "KM": h.get("kamar_mandi"),
                "Status": h.get("status"),
                "Skor Survey": (
                    f"{latest_survey_info(h)['score']:.1f}" if latest_survey_info(h)["type"] == "selesai" else "-"
                ),
            }
            for h in filtered
        ]
    )
    st.dataframe(
        df.style.format({"Harga": lambda v: format_rupiah(v)}),
        use_container_width=True,
        hide_index=True,
    )
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Unduh sebagai CSV", data=csv, file_name="daftar_rumah.csv", mime="text/csv")


# --------------------------------------------------------------------------
# Tab 6: Kelola Data (tambah / edit / hapus rumah)
# --------------------------------------------------------------------------

def house_form_fields(prefix, e=None):
    e = e or {}
    c1, c2 = st.columns(2)
    nama = c1.text_input("Nama / Judul Listing*", value=e.get("nama", ""), key=f"{prefix}_nama")
    status = c2.selectbox(
        "Status",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(e["status"]) if e.get("status") in STATUS_OPTIONS else 0,
        key=f"{prefix}_status",
    )
    alamat = st.text_input("Alamat Lengkap*", value=e.get("alamat", ""), key=f"{prefix}_alamat")

    c3, c4 = st.columns(2)
    latitude = c3.number_input(
        "Latitude*", format="%.6f", value=float(e.get("latitude", -6.200000)), key=f"{prefix}_lat"
    )
    longitude = c4.number_input(
        "Longitude*", format="%.6f", value=float(e.get("longitude", 106.800000)), key=f"{prefix}_lng"
    )
    st.caption("Tip: klik kanan lokasi di Google Maps \u2192 salin angka koordinat yang muncul.")

    harga = st.number_input(
        "Harga (Rp)*", min_value=0, step=10_000_000, value=int(e.get("harga", 0)), key=f"{prefix}_harga"
    )

    c5, c6, c7, c8 = st.columns(4)
    luas_tanah = c5.number_input("Luas Tanah (m\u00b2)", min_value=0, value=int(e.get("luas_tanah", 0)), key=f"{prefix}_lt")
    luas_bangunan = c6.number_input("Luas Bangunan (m\u00b2)", min_value=0, value=int(e.get("luas_bangunan", 0)), key=f"{prefix}_lb")
    kamar_tidur = c7.number_input("Kamar Tidur", min_value=0, value=int(e.get("kamar_tidur", 0)), key=f"{prefix}_kt")
    kamar_mandi = c8.number_input("Kamar Mandi", min_value=0, value=int(e.get("kamar_mandi", 0)), key=f"{prefix}_km")

    c9, c10, c11 = st.columns(3)
    carport = c9.number_input("Carport", min_value=0, value=int(e.get("carport", 0)), key=f"{prefix}_carport")
    lantai = c10.number_input("Jumlah Lantai", min_value=1, value=int(e.get("lantai", 1)), key=f"{prefix}_lantai")
    tahun_dibangun = c11.number_input(
        "Tahun Dibangun", min_value=1950, max_value=2100, value=int(e.get("tahun_dibangun", 2020)), key=f"{prefix}_tahun"
    )

    c12, c13 = st.columns(2)
    sert_options = ["SHM", "HGB", "Girik", "PPJB", "Lainnya"]
    sertifikat = c12.selectbox(
        "Sertifikat",
        sert_options,
        index=sert_options.index(e["sertifikat"]) if e.get("sertifikat") in sert_options else 0,
        key=f"{prefix}_sertifikat",
    )
    hadap = c13.text_input("Hadap Rumah", value=e.get("hadap", ""), key=f"{prefix}_hadap")

    developer = st.text_input("Developer / Nama Agen", value=e.get("developer", ""), key=f"{prefix}_dev")
    deskripsi = st.text_area("Deskripsi", value=e.get("deskripsi", ""), key=f"{prefix}_desk")
    kelebihan = st.text_area(
        "Kelebihan (satu poin per baris)", value="\n".join(e.get("kelebihan", [])), key=f"{prefix}_plus"
    )
    kekurangan = st.text_area(
        "Catatan / Kekurangan (satu poin per baris)", value="\n".join(e.get("kekurangan", [])), key=f"{prefix}_minus"
    )
    gambar = st.text_area(
        "URL Gambar (satu URL per baris) \u2014 boleh URL biasa, link share Google Drive, "
        "atau path lokal seperti images/rumah1.jpg",
        value="\n".join(e.get("gambar", [])),
        key=f"{prefix}_img",
        help=(
            "Link Google Drive otomatis dikonversi agar bisa tampil. Cukup klik kanan file "
            "di Drive \u2192 Bagikan \u2192 ubah akses jadi \u201cSiapa saja yang memiliki link\u201d "
            "\u2192 salin link, lalu tempel di sini apa adanya."
        ),
    )
    video = st.text_input(
        "URL Video (YouTube, link share Google Drive, dll) atau path lokal (mis. videos/rumah1.mp4)",
        value=e.get("video", ""),
        key=f"{prefix}_video",
    )
    kontak_agen = st.text_input("Kontak Agen", value=e.get("kontak_agen", ""), key=f"{prefix}_kontak")
    sumber_listing = st.text_input("Sumber Listing (URL)", value=e.get("sumber_listing", ""), key=f"{prefix}_sumber")

    return {
        "nama": nama,
        "alamat": alamat,
        "latitude": latitude,
        "longitude": longitude,
        "harga": harga,
        "status": status,
        "luas_tanah": luas_tanah,
        "luas_bangunan": luas_bangunan,
        "kamar_tidur": kamar_tidur,
        "kamar_mandi": kamar_mandi,
        "carport": carport,
        "lantai": lantai,
        "tahun_dibangun": tahun_dibangun,
        "sertifikat": sertifikat,
        "hadap": hadap,
        "developer": developer,
        "deskripsi": deskripsi,
        "kelebihan": [k.strip() for k in kelebihan.splitlines() if k.strip()],
        "kekurangan": [k.strip() for k in kekurangan.splitlines() if k.strip()],
        "gambar": [g.strip() for g in gambar.splitlines() if g.strip()],
        "video": video.strip(),
        "kontak_agen": kontak_agen,
        "sumber_listing": sumber_listing,
    }


def render_manage_tab():
    st.markdown("#### \u2795 Tambah Rumah Baru")
    with st.form("form_tambah", clear_on_submit=True):
        data = house_form_fields("add")
        submitted = st.form_submit_button("Simpan Rumah Baru")
        if submitted:
            if not data["nama"] or not data["alamat"]:
                st.error("Nama dan alamat wajib diisi.")
            else:
                data["id"] = next_id(st.session_state.houses)
                data["estimasi_cicilan"] = 0
                data["survey_records"] = []
                st.session_state.houses.append(data)
                save_houses(st.session_state.houses)
                st.session_state.selected_id = data["id"]
                st.success(f"'{data['nama']}' ditambahkan dan disimpan.")
                st.rerun()

    st.divider()
    st.markdown("#### \u270F\uFE0F Edit Rumah")
    if st.session_state.houses:
        options_edit = [f'{h["id"]} \u2014 {h["nama"]}' for h in st.session_state.houses]
        chosen_edit = st.selectbox("Pilih rumah yang ingin diedit", options_edit, key="edit_selector")
        edit_id = int(chosen_edit.split(" \u2014 ")[0])
        existing = next(h for h in st.session_state.houses if h["id"] == edit_id)

        with st.form(f"form_edit_{edit_id}"):
            data_edit = house_form_fields(f"edit_{edit_id}", existing)
            submitted_edit = st.form_submit_button("Simpan Perubahan")
            if submitted_edit:
                data_edit["id"] = edit_id
                # Field ini tidak diedit lewat form ini -- pertahankan nilai lama.
                data_edit["estimasi_cicilan"] = existing.get("estimasi_cicilan", 0)
                data_edit["survey_records"] = existing.get("survey_records", [])
                st.session_state.houses = [
                    data_edit if h["id"] == edit_id else h for h in st.session_state.houses
                ]
                save_houses(st.session_state.houses)
                st.success("Perubahan disimpan.")
                st.rerun()

        st.divider()
        st.markdown("#### \U0001F5D1\uFE0F Hapus Rumah")
        options_del = [f'{h["id"]} \u2014 {h["nama"]}' for h in st.session_state.houses]
        chosen_del = st.selectbox("Pilih rumah yang ingin dihapus", options_del, key="delete_selector")
        if st.button("Hapus Rumah Ini"):
            del_id = int(chosen_del.split(" \u2014 ")[0])
            st.session_state.houses = [h for h in st.session_state.houses if h["id"] != del_id]
            save_houses(st.session_state.houses)
            st.success("Rumah dihapus.")
            st.rerun()
    else:
        st.caption("Belum ada data rumah. Tambahkan lewat form di atas.")


# --------------------------------------------------------------------------
# Tab 7: Sinkronisasi Google Sheets
# --------------------------------------------------------------------------

def _get_gcp_secrets():
    """Ambil dict st.secrets dengan aman. Streamlit akan melempar
    StreamlitSecretNotFoundError (bukan sekadar mengembalikan kosong) kalau
    file secrets.toml belum ada sama sekali, jadi aksesnya wajib dibungkus
    try/except di sini."""
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets)
    except Exception:
        pass
    return None


def render_sync_tab():
    st.markdown("#### \u2601\uFE0F Sinkronisasi Google Sheets")
    st.caption("Backup & sinkronkan data rumah (termasuk riwayat survey) ke Google Sheets Anda sendiri.")
    st.caption(
        "\u2139\uFE0F Kalau kredensial & ID Sheet di bawah sudah diatur lewat `secrets.toml`, "
        "data ini otomatis ditarik sebagai data awal setiap kali aplikasi pertama kali dibuka "
        "(lihat indikator sumber data di sidebar)."
    )

    if not GSPREAD_AVAILABLE:
        st.error(
            "Library belum terpasang. Jalankan `pip install gspread google-auth` lalu restart aplikasi."
        )
        return

    secrets_dict = _get_gcp_secrets()
    if secrets_dict is None:
        st.warning("Kredensial Google belum diatur.")
        st.markdown(
            "Fitur ini **opsional** \u2014 aplikasi tetap berjalan normal tanpa ini. "
            "Ikuti panduan lengkap di **README.md** bagian *Integrasi Google Sheets* untuk "
            "membuat Service Account dan mengisi `.streamlit/secrets.toml` (salin dari "
            "`.streamlit/secrets.toml.example`)."
        )
        return

    default_sheet_id = secrets_dict.get("sheet_id", "")
    sheet_input = st.text_input(
        "ID atau tautan Google Sheet",
        value=st.session_state.get("sheet_id_override", default_sheet_id),
        help="Contoh: https://docs.google.com/spreadsheets/d/ISI_ID_DI_SINI/edit",
    )
    st.session_state["sheet_id_override"] = sheet_input
    sheet_id = extract_sheet_id(sheet_input)

    client_email = secrets_dict.get("gcp_service_account", {}).get("client_email", "-")
    st.caption(
        f"Service account: `{client_email}` \u2014 pastikan email ini sudah diundang "
        "sebagai **Editor** di Google Sheet tujuan."
    )

    if not sheet_id:
        st.info("Masukkan ID/tautan Google Sheet di atas untuk mulai sinkronisasi.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**\u2b06\uFE0F Push** \u2014 kirim data lokal ke Google Sheets (menimpa isi sheet)")
        if st.button("Push Semua Data ke Google Sheets", use_container_width=True):
            with st.spinner("Mengirim data ke Google Sheets..."):
                try:
                    gc = get_client()
                    n = push_houses(gc, sheet_id, st.session_state.houses)
                    st.success(f"Berhasil mengirim {n} data rumah ke Google Sheets.")
                except Exception as e:
                    st.error(f"Gagal push data: {e}")

    with col2:
        st.markdown("**\u2b07\uFE0F Pull** \u2014 tarik data dari Google Sheets (menimpa data lokal)")
        if st.button("Tarik Data dari Google Sheets", use_container_width=True):
            with st.spinner("Mengambil data dari Google Sheets..."):
                try:
                    gc = get_client()
                    pulled = pull_houses(gc, sheet_id)
                    pulled = [coerce_house_types(h) for h in pulled]
                    st.session_state.houses = pulled
                    save_houses(pulled)
                    st.session_state["_data_source"] = "sheets"
                    st.success(f"Berhasil menarik {len(pulled)} data rumah dari Google Sheets.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menarik data: {e}")


# --------------------------------------------------------------------------
# Layout utama
# --------------------------------------------------------------------------

st.markdown('<div class="eyebrow">Dasbor Pribadi \u00b7 Pencarian Rumah</div>', unsafe_allow_html=True)
st.title("\U0001F3E0 Komparasi Pilihan Rumah")
st.caption("Bandingkan lokasi, harga, spesifikasi, dan hasil survey tiap kandidat rumah sebelum memutuskan.")

filters = sidebar_filters(st.session_state.houses)
filtered = apply_filters(st.session_state.houses, filters)

tab_map, tab_survey, tab_kpr, tab_compare, tab_table, tab_manage, tab_sync = st.tabs(
    [
        "\U0001F5FA\uFE0F Peta & Detail",
        "\U0001F4CB Survey",
        "\U0001F9EE Kalkulator KPR",
        "\U0001F4CA Komparasi",
        "\U0001F4C4 Semua Data",
        "\u2795 Kelola Data",
        "\u2601\uFE0F Google Sheets",
    ]
)

with tab_map:
    render_map_tab(filtered)

with tab_survey:
    render_survey_tab()

with tab_kpr:
    render_kpr_tab()

with tab_compare:
    render_compare_tab(filtered)

with tab_table:
    render_table_tab(filtered)

with tab_manage:
    render_manage_tab()

with tab_sync:
    render_sync_tab()
