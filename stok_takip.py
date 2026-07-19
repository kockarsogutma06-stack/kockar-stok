import streamlit as st
import pandas as pd
import re
import requests
import base64
import gspread
import json
from google.oauth2.service_account import Credentials
from fpdf import FPDF

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Envanter Yönetim Sistemi", layout="wide")

# --- 1. SİSTEM GÜVENLİĞİ (ŞİFRELİ GİRİŞ) ---
if "sistem_acik" not in st.session_state:
    st.session_state.sistem_acik = False

if not st.session_state.sistem_acik:
    st.markdown("<h2 style='text-align: center; color: #0f172a; margin-top: 50px;'>🔒 Kurumsal Envanter Sistemine Giriş</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("Bu sistem Google Cloud & ImgBB API ile 7/24 Senkronize Çalışmaktadır.")
        sifre = st.text_input("Sistem Master Şifresi", type="password")
        if st.button("Sisteme Giriş Yap", use_container_width=True, type="primary"):
            if sifre == "Memo2026!":
                st.session_state.sistem_acik = True
                st.rerun()
            else:
                st.error("Hatalı veya yetkisiz şifre denemesi!")
    st.stop()

# --- 2. GOOGLE SHEETS VE IMGBB BAĞLANTILARI (GÜVENLİ KASA KULLANIMI) ---
DEFAULT_KATEGORILER = ["Kompresör Grubu", "Chiller Grubu", "Soğutma Grubu", "Diğer"]

# Şifreleri Streamlit'in Gizli Kasasından Çekiyoruz (Artık kodda görünmeyecek)
IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
GOOGLE_CREDENTIALS = json.loads(st.secrets["GOOGLE_JSON"])

# Google Bağlantısını Başlat
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=scopes)
    gc = gspread.authorize(creds)
    try:
        sh = gc.open("Stok_Veritabani")
        return sh.sheet1
    except Exception as e:
        st.error(f"Google E-Tabloya bağlanılamadı. Dosya adının tam olarak 'Stok_Veritabani' olduğundan emin olun. Hata: {e}")
        st.stop()

worksheet = get_google_sheet()

# Verileri E-Tablodan Çekme
records = worksheet.get_all_records()
if records:
    df = pd.DataFrame(records)
else:
    df = pd.DataFrame(columns=["ID", "Kategori", "Marka", "Model", "HP", "Kilovat", "Kalori", "Fiyat", "Adet", "Gorseller"])

# Güvenlik ve Tip Kontrolü
for col in ["Kategori", "Marka", "Model", "HP", "Kilovat", "Kalori", "Fiyat", "Gorseller"]:
    if col not in df.columns:
        df[col] = "Belirtilmedi"
    df[col] = df[col].astype(str)

if "Adet" not in df.columns:
    df["Adet"] = 0
if "ID" not in df.columns:
    df["ID"] = 0

# Verileri E-Tabloya Yazma Fonksiyonu
def veriyi_kaydet(data_frame):
    data_frame = data_frame.fillna("Belirtilmedi")
    update_data = [data_frame.columns.values.tolist()] + data_frame.values.tolist()
    worksheet.clear()
    worksheet.update(range_name='A1', values=update_data)

# Fotoğrafı ImgBB'ye Yükleme Fonksiyonu
def imgbb_yukle(image_file):
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": IMGBB_API_KEY,
        "image": base64.b64encode(image_file.read()).decode("utf-8")
    }
    res = requests.post(url, data=payload)
    if res.status_code == 200:
        return res.json()["data"]["url"]
    return None

# Metin Temizleme ve PDF Fonksiyonları
def tr_to_eng(text):
    tr_map = str.maketrans("ğüşöçıİĞÜŞÖÇ", "gusociIGUSOC")
    return str(text).translate(tr_map)

def hp_to_kw_cevir(hp_str):
    if not hp_str or hp_str == "Belirtilmedi": return "Belirtilmedi"
    try:
        temiz_sayi = re.sub(r'[^\d.]', '', str(hp_str).replace(',', '.'))
        if temiz_sayi:
            return f"{(float(temiz_sayi) * 0.7457):.2f}"
    except:
        pass
    return "Belirtilmedi"

def pdf_olustur(dataframe):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(190, 15, txt="ENVANTER DURUM RAPORU", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 8)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(30, 10, " KATEGORI", border=1, fill=True)
    pdf.cell(30, 10, " MARKA", border=1, fill=True)
    pdf.cell(35, 10, " MODEL", border=1, fill=True)
    pdf.cell(30, 10, " GUC(HP/kW)", border=1, fill=True, align='C')
    pdf.cell(25, 10, " KAPASITE", border=1, fill=True, align='C')
    pdf.cell(22, 10, " FIYAT", border=1, fill=True, align='C')
    pdf.cell(18, 10, " STOK", border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font("Arial", size=8)
    pdf.set_text_color(51, 65, 85)
    for index, row in dataframe.iterrows():
        pdf.cell(30, 10, " " + tr_to_eng(row['Kategori'])[:15], border=1)
        pdf.cell(30, 10, " " + tr_to_eng(row['Marka'])[:15], border=1)
        pdf.cell(35, 10, " " + tr_to_eng(row['Model'])[:18], border=1)
        
        guc_metni = f"{row['HP']} HP / {row['Kilovat']} kW" if row['HP'] != "Belirtilmedi" else str(row['Kilovat'])
        pdf.cell(30, 10, tr_to_eng(guc_metni)[:18], border=1, align='C')
        kalori_metni = f"{row['Kalori']} kcal/h" if row['Kalori'] != "Belirtilmedi" else "-"
        pdf.cell(25, 10, tr_to_eng(kalori_metni)[:13], border=1, align='C')
        pdf.cell(22, 10, str(row['Fiyat'])[:10], border=1, align='C')
        pdf.cell(18, 10, str(row['Adet']), border=1, align='C')
        pdf.ln()
    return pdf.output(dest='S').encode('latin1')

# --- DETAYLI CSS TASARIMI ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    h1, h2, h3, h4 { color: #0f172a !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .stTextInput>div>div>input, .stSelectbox>div>div>div { border-radius: 6px !important; border: 1px solid #cbd5e1 !important; background-color: #ffffff !important; }
    .stButton>button { border-radius: 6px !important; font-weight: 500 !important; transition: all 0.2s ease; }
    .streamlit-expanderHeader { background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 6px !important; font-weight: 600 !important; color: #334155 !important; }
    hr { margin: 1.5rem 0; border-top: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# --- SOL MENÜ ---
with st.sidebar:
    st.markdown("<div style='padding: 10px 0;'><h3 style='margin:0;'>Envanter Paneli</h3><span style='color:#64748b; font-size:12px;'>Bulut Sürüm v5.2 (Güvenli)</span></div>", unsafe_allow_html=True)
    st.markdown("---")
    menu = st.radio("Modüller:", ["Mevcut Stok Listesi", "Yeni Ürün Tanımla", "Sistem Raporu & Ayarlar"])
    st.markdown("---")
    
    # YENİLEME BUTONU (Şifreyi sıfırlamadan verileri çeker)
    if st.button("🔄 Verileri Yenile", use_container_width=True):
        st.rerun()
        
    st.markdown("---")
    st.caption("Erişim Yetkisi: Yönetici")
    if st.button("Güvenli Çıkış Yap", use_container_width=True):
        st.session_state.sistem_acik = False
        st.rerun()

mevcut_kategoriler = list(set(DEFAULT_KATEGORILER + list(df["Kategori"].dropna().astype(str).unique())))
mevcut_kategoriler.sort()

# --- ANA SAYFA: MEVCUT STOK LİSTESİ ---
if menu == "Mevcut Stok Listesi":
    st.markdown("## Stok Durum İzleme (Bulut)")
    st.markdown("---")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1: secilen_kat = st.selectbox("📂 Kategori", ["Tüm Kategoriler"] + mevcut_kategoriler)
    temp_df = df if secilen_kat == "Tüm Kategoriler" else df[df["Kategori"].astype(str) == secilen_kat]

    with col_f2: secilen_hp = st.selectbox("⚡ Motor (HP)", ["Tümü"] + list(temp_df["HP"].astype(str).unique()))
    if secilen_hp != "Tümü": temp_df = temp_df[temp_df["HP"].astype(str) == secilen_hp]

    with col_f3: secilen_kal = st.selectbox("❄️ Kapasite", ["Tümü"] + list(temp_df["Kalori"].astype(str).unique()))
    if secilen_kal != "Tümü": temp_df = temp_df[temp_df["Kalori"].astype(str) == secilen_kal]

    with col_f4: secilen_mm = st.selectbox("🔍 Marka / Model", ["Tüm Modeller"] + list((temp_df["Marka"].astype(str) + " - " + temp_df["Model"].astype(str)).unique()))
    filtered_df = temp_df.copy()
    if secilen_mm != "Tüm Modeller": filtered_df = filtered_df[(filtered_df["Marka"].astype(str) + " - " + filtered_df["Model"].astype(str)) == secilen_mm]

    st.markdown("<br>", unsafe_allow_html=True)

    if len(filtered_df) == 0:
        st.info("Kriterlere uygun kayıtlı ürün bulunamadı.")
    else:
        for index, row in filtered_df.iterrows():
            item_id = row["ID"]
            
            with st.container():
                c1, c2, c3 = st.columns([5, 2, 3])
                with c1:
                    st.markdown(f"<div style='font-size: 16px; font-weight: 600; color: #1e293b;'>{row['Marka']} {row['Model']}</div>", unsafe_allow_html=True)
                    guc_txt = f"{row['HP']} HP / {row['Kilovat']} kW" if row['HP'] != "Belirtilmedi" else f"{row['Kilovat']} kW"
                    kal_txt = f" | ❄️ Kapasite: {row['Kalori']} kcal/h" if str(row.get('Kalori', 'Belirtilmedi')) != "Belirtilmedi" else ""
                    st.markdown(f"<div style='font-size: 13px; color: #64748b; margin-top: -3px;'>Kategori: {row['Kategori']} | ⚡ Güç: {guc_txt}{kal_txt} | 💰 Fiyat: {row['Fiyat']}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div style='font-size: 18px; font-weight: 700; color: #0f172a;'>{row['Adet']} Adet</div>", unsafe_allow_html=True)
                with c3:
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("➕ Giriş", key=f"art_{item_id}", use_container_width=True):
                            df.at[index, 'Adet'] = int(df.at[index, 'Adet']) + 1
                            veriyi_kaydet(df)
                            st.rerun()
                    with bc2:
                        if st.button("➖ Çıkış", key=f"az_{item_id}", use_container_width=True):
                            if int(row['Adet']) > 0:
                                df.at[index, 'Adet'] = int(df.at[index, 'Adet']) - 1
                                veriyi_kaydet(df)
                                st.rerun()
                
                with st.expander("Detaylar, Görseller & Düzenleme"):
                    d_c1, d_c2 = st.columns([3, 2])
                    with d_c1:
                        st.markdown("<p style='font-weight: 600; margin-bottom: 5px; color:#475569;'>Bulut Görselleri</p>", unsafe_allow_html=True)
                        
                        gorsel_str = str(row.get("Gorseller", "Belirtilmedi"))
                        gorseller = [g.strip() for g in gorsel_str.split(",")] if gorsel_str and gorsel_str != "Belirtilmedi" else []
                        
                        if gorseller:
                            img_cols = st.columns(3)
                            for idx, img_url in enumerate(gorseller):
                                with img_cols[idx % 3]:
                                    st.image(img_url, use_container_width=True)
                                    if st.button("Sil", key=f"del_img_{item_id}_{idx}", use_container_width=True):
                                        gorseller.pop(idx)
                                        df.at[index, "Gorseller"] = ",".join(gorseller) if gorseller else "Belirtilmedi"
                                        veriyi_kaydet(df)
                                        st.rerun()
                        else:
                            st.caption("Bulutta görsel bulunmuyor.")
                        
                        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
                        yeni_fotolar = st.file_uploader("Buluta Yeni Fotoğraf Yükle", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key=f"upload_more_{item_id}")
                        if st.button("Seçili Fotoğrafları Yükle", key=f"btn_up_{item_id}"):
                            if yeni_fotolar:
                                yeni_linkler = []
                                with st.spinner("Görseller ImgBB sunucusuna aktarılıyor..."):
                                    for f in yeni_fotolar:
                                        link = imgbb_yukle(f)
                                        if link: yeni_linkler.append(link)
                                if yeni_linkler:
                                    mevcut = df.at[index, "Gorseller"]
                                    if mevcut == "Belirtilmedi" or not mevcut:
                                        df.at[index, "Gorseller"] = ",".join(yeni_linkler)
                                    else:
                                        df.at[index, "Gorseller"] = mevcut + "," + ",".join(yeni_linkler)
                                    veriyi_kaydet(df)
                                    st.success("Buluta eklendi!")
                                    st.rerun()
                    
                    with d_c2:
                        st.markdown("<p style='font-weight: 600; margin-bottom: 5px; color:#475569;'>Kart Düzenleme</p>", unsafe_allow_html=True)
                        e_m = st.text_input("Marka", value=str(row["Marka"]), key=f"e_m_{item_id}")
                        e_mod = st.text_input("Model", value=str(row["Model"]), key=f"e_mod_{item_id}")
                        
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1: e_hp = st.text_input("HP", value=str(row["HP"]), key=f"e_hp_{item_id}")
                        with ec2: e_kal = st.text_input("kcal/h", value=str(row.get("Kalori", "Belirtilmedi")), key=f"e_kal_{item_id}")
                        with ec3: e_f = st.text_input("Fiyat", value=str(row["Fiyat"]), key=f"e_f_{item_id}")
                        
                        e_kat_liste = mevcut_kategoriler.copy()
                        if row["Kategori"] not in e_kat_liste: e_kat_liste.append(row["Kategori"])
                        e_kat = st.selectbox("Kategori", e_kat_liste, index=e_kat_liste.index(row["Kategori"]), key=f"e_k_{item_id}")
                        
                        eb1, eb2 = st.columns(2)
                        with eb1:
                            if st.button("Kaydet", key=f"save_e_{item_id}", type="primary", use_container_width=True):
                                df.at[index, "Marka"] = str(e_m)
                                df.at[index, "Model"] = str(e_mod)
                                y_hp = str(e_hp) if e_hp else "Belirtilmedi"
                                df.at[index, "HP"] = y_hp
                                df.at[index, "Kilovat"] = hp_to_kw_cevir(y_hp)
                                df.at[index, "Kalori"] = str(e_kal)
                                df.at[index, "Fiyat"] = str(e_f)
                                df.at[index, "Kategori"] = str(e_kat)
                                veriyi_kaydet(df)
                                st.rerun()
                        with eb2:
                            if st.button("Modeli Sil", key=f"del_p_{item_id}", use_container_width=True):
                                df = df.drop(index)
                                veriyi_kaydet(df)
                                st.rerun()
                st.markdown("<div style='border-bottom: 1px solid #f1f5f9; margin: 15px 0;'></div>", unsafe_allow_html=True)

# --- YENİ ÜRÜN EKLEME MODÜLÜ ---
elif menu == "Yeni Ürün Tanımla":
    st.markdown("## Yeni Ürün Girişi (Bulut)")
    st.markdown("---")
    
    with st.form("yeni_urun_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Kategori Belirleme**")
            kat_sec = st.selectbox("Mevcut Kategorilerden Seçin", ["Listeden Seç"] + mevcut_kategoriler)
            yeni_kat = st.text_input("VEYA Yeni Kategori Yazın")
            
            st.markdown("<br>**Ürün Detayları**", unsafe_allow_html=True)
            marka = st.text_input("Marka (Örn: Danfoss)")
            hp_gir = st.text_input("Motor Gücü (HP) - Rakam Girin")
            kal_gir = st.text_input("Kapasite (kcal/h)")
            
        with col2:
            st.markdown("** **")
            st.markdown("** **")
            st.markdown("** **")
            st.markdown("** **")
            model = st.text_input("Model / Kod")
            fiyat = st.text_input("Alış Fiyatı (Örn: 1500 TL, 250$)")
            adet = st.number_input("Başlangıç Stok Adedi", min_value=0, value=0)
            
        st.markdown("---")
        fotolar = st.file_uploader("Ürün Görselleri", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
            
        st.write("")
        submit = st.form_submit_button("Veritabanına ve Buluta Kaydet", use_container_width=True)
        
        if submit:
            kat_son = yeni_kat.strip() if yeni_kat.strip() else (kat_sec if kat_sec != "Listeden Seç" else "")
            
            if marka and model and kat_son:
                new_id = int(df["ID"].max() + 1) if len(df) > 0 else 1
                
                img_links = []
                if fotolar:
                    with st.spinner("Fotoğraflar buluta yükleniyor, lütfen bekleyin..."):
                        for f in fotolar:
                            link = imgbb_yukle(f)
                            if link: img_links.append(link)
                gorsel_deger = ",".join(img_links) if img_links else "Belirtilmedi"
                
                hp_deg = str(hp_gir) if hp_gir else "Belirtilmedi"
                kw_deg = hp_to_kw_cevir(hp_deg)
                kal_deg = str(kal_gir) if kal_gir else "Belirtilmedi"
                fiy_deg = str(fiyat) if fiyat else "Belirtilmedi"
                
                yeni_veri = pd.DataFrame([{
                    "ID": new_id, "Kategori": str(kat_son), "Marka": str(marka), "Model": str(model),
                    "HP": hp_deg, "Kilovat": kw_deg, "Kalori": kal_deg, "Fiyat": fiy_deg,
                    "Adet": int(adet), "Gorseller": gorsel_deger
                }])
                df = pd.concat([df, yeni_veri], ignore_index=True)
                veriyi_kaydet(df)
                st.success(f"{marka} {model} sisteme başarıyla eklendi!")
            else:
                st.error("Kategori, Marka ve Model alanları zorunludur.")

# --- RAPORLAMA VE AYARLAR ---
elif menu == "Sistem Raporu & Ayarlar":
    st.markdown("## Raporlama ve Ayarlar")
    st.markdown("---")
    
    if len(df) > 0:
        pdf_data = pdf_olustur(df)
        st.download_button(label="📄 Güncel PDF Raporunu İndir", data=pdf_data, file_name="Bulut_Envanter_Raporu.pdf", mime="application/pdf")
    else:
        st.warning("Sistemde raporlanacak kayıtlı envanter bulunmuyor.")

    st.markdown("---")
    st.error("DİKKAT: Veritabanını silmek buluttaki tüm verilerinizi yok eder!")
    if st.button("Veritabanını Komple Sıfırla (Geri Alınamaz)", type="primary"):
        df_bos = pd.DataFrame(columns=["ID", "Kategori", "Marka", "Model", "HP", "Kilovat", "Kalori", "Fiyat", "Adet", "Gorseller"])
        veriyi_kaydet(df_bos)
        st.success("Tüm sistem sıfırlandı. Lütfen sayfayı yenileyin.")
