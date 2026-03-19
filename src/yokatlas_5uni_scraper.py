"""
YÖK Atlas — 5 Teknik Üniversite Scraper
========================================
Hedef üniversiteler:
  İTÜ   (1055) — İstanbul Teknik Üniversitesi
  ODTÜ  (1084) — Orta Doğu Teknik Üniversitesi
  YTÜ   (1101) — Yıldız Teknik Üniversitesi
  GTÜ   (1044) — Gebze Teknik Üniversitesi
  İYTE  (1058) — İzmir Yüksek Teknoloji Enstitüsü

Çalıştır : python yokatlas_5uni_scraper.py
Test modu: python yokatlas_5uni_scraper.py --test
Çıktı    : yokatlas_5uni/ klasörü (CSV + Excel)
"""

import requests
import time
import sys
import json
import pandas as pd
from pathlib import Path
from html.parser import HTMLParser

# ─── Üniversite tanımları ──────────────────────────────────────────────────────
UNIVERSITELER = {
    1055: "İTÜ",
    1084: "ODTÜ",
    1101: "YTÜ",
    1044: "GTÜ",
    1058: "İYTE",
}

UNI_TAM_ADI = {
    1055: "İstanbul Teknik Üniversitesi",
    1084: "Orta Doğu Teknik Üniversitesi",
    1101: "Yıldız Teknik Üniversitesi",
    1044: "Gebze Teknik Üniversitesi",
    1058: "İzmir Yüksek Teknoloji Enstitüsü",
}

# ─── Savunma sanayi ilgili bölümler ───────────────────────────────────────────
BOLUMLER = {
    10024: "Bilgisayar Mühendisliği",
    10057: "Elektrik-Elektronik Mühendisliği",
    10058: "Elektronik Mühendisliği",
    10059: "Elektronik ve Haberleşme Mühendisliği",
    10128: "Makine Mühendisliği",
    10073: "Havacılık ve Uzay Mühendisliği",
    10074: "Havacılık Mühendisliği",
    10178: "Uçak Mühendisliği",
    10141: "Mekatronik Mühendisliği",
    10030: "Bilişim Sistemleri Mühendisliği",
    10029: "Bilgisayar ve Yazılım Mühendisliği",
    10146: "Metalurji ve Malzeme Mühendisliği",
    10065: "Gemi İnşaatı ve Gemi Makineleri Mühendisliği",
    10066: "Gemi Makineleri İşletme Mühendisliği",
    10049: "Endüstri Mühendisliği",
    10082: "İmalat Mühendisliği",
    10162: "Savunma Teknolojileri Mühendisliği",
}

YEARS = [2020, 2021, 2022, 2023, 2024]
PAUSE = 0.7   # saniye — rate limiting
BASE  = "https://yokatlas.yok.gov.tr/content/lisans-bolum"

# ─── HTML tablo parser ────────────────────────────────────────────────────────
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self._cur_table = []
        self._cur_row = []
        self._cur_cell = ""
        self._in_cell = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._cur_table = []
        elif tag == "tr":
            self._cur_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cur_cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._cur_row.append(self._cur_cell.strip())
            self._in_cell = False
        elif tag == "tr" and self._cur_row:
            self._cur_table.append(self._cur_row[:])
            self._cur_row = []
        elif tag == "table" and self._depth:
            if self._depth == 1:
                self.tables.append(self._cur_table[:])
                self._cur_table = []
            self._depth -= 1

    def handle_data(self, data):
        if self._in_cell:
            self._cur_cell += data

def parse_tables(html):
    if not html:
        return []
    p = TableParser()
    p.feed(html)
    return p.tables

# ─── HTTP yardımcısı ─────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://yokatlas.yok.gov.tr/",
    "Accept-Language": "tr-TR,tr;q=0.9",
})

def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            if len(r.text) > 50:
                return r.text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
    return None

# ─── Normalize helper ─────────────────────────────────────────────────────────
TR_MAP = str.maketrans("ışçğöüİŞÇĞÖÜ", "iscgouISCGOU")

def norm(s):
    return s.lower().translate(TR_MAP).replace(" ", "_").replace("/", "_").replace("-", "_")

# ─── Bölüm bazlı endpoint'ler ────────────────────────────────────────────────
# YÖK Atlas bölüm sayfaları üniversite filtresi için "u" parametresi alır:
# b3100_1_1.php?b=BOLUM_KODU&y=YIL  → tüm üniversiteler toplam
# Program seviyesinde: lisans.php?y=UUUUBXXXXX  (5 üniversitenin program kodları)
#
# Bölüm/üniversite kesişimi için doğru endpoint:
# content/lisans-bolum/3100/b3100_1_1.php?b=BOLUM&y=YIL  → tüm üniversiteler listesi
# Buradan üniversite filtresi yapabiliriz.

def fetch_bolum_uni_genel(bolum_kodu, yil):
    """Bölüm genel listesi — tüm üniversiteler, sonra filtrele."""
    url = f"{BASE}/3100/b3100_1_1.php?b={bolum_kodu}&y={yil}"
    return fetch(url)

def fetch_bolum_uni_cinsiyet(bolum_kodu, yil):
    url = f"{BASE}/3100/b3100_1_2.php?b={bolum_kodu}&y={yil}"
    return fetch(url)

def fetch_bolum_uni_puan(bolum_kodu, yil):
    url = f"{BASE}/3100/b3100_2_1.php?b={bolum_kodu}&y={yil}"
    return fetch(url)

# ─── Tablo parse ve üniversite filtresi ──────────────────────────────────────
# YÖK Atlas b3100_1_1 tablosunda genellikle:
# Sütun 0 → Üniversite adı
# Sütun 1 → Kontenjan
# Sütun 2 → Yerleşen
# Sütun 3 → Kayıt yaptıran
# (değişebilir, header satırını kontrol et)

UNI_ANAHTAR_SOZLUGU = {
    "istanbul teknik": 1055,
    "i̇stanbul teknik": 1055,
    "itu": 1055,
    "orta dogu teknik": 1084,
    "orta doğu teknik": 1084,
    "odtu": 1084,
    "metu": 1084,
    "yildiz teknik": 1101,
    "yıldız teknik": 1101,
    "ytu": 1101,
    "gebze teknik": 1044,
    "gtu": 1044,
    "izmir yuksek teknoloji": 1058,
    "i̇zmir yüksek teknoloji": 1058,
    "izmir yüksek teknoloji": 1058,
    "iyte": 1058,
}

def uni_kod_bul(uni_adi):
    """Üniversite adından kod bul."""
    lower = uni_adi.lower().translate(TR_MAP)
    for anahtar, kod in UNI_ANAHTAR_SOZLUGU.items():
        if anahtar.lower().translate(TR_MAP) in lower:
            return kod
    return None

def parse_genel_tablo(html, bolum_kodu, bolum_adi, yil):
    """
    Genel istatistik tablosunu parse et, sadece 5 üniversiteyi döndür.
    Döndürülen: list of dict
    """
    tables = parse_tables(html)
    sonuclar = []

    for tablo in tables:
        if len(tablo) < 2:
            continue
        # Header satırını bul
        header = [norm(h) for h in tablo[0]]
        if not header:
            continue

        for satir in tablo[1:]:
            if not satir or not satir[0]:
                continue
            uni_kodu = uni_kod_bul(satir[0])
            if uni_kodu is None:
                continue

            row = {
                "uni_kodu": uni_kodu,
                "uni_kisa": UNIVERSITELER[uni_kodu],
                "uni_tam_adi": UNI_TAM_ADI[uni_kodu],
                "bolum_kodu": bolum_kodu,
                "bolum_adi": bolum_adi,
                "yil": yil,
            }

            for i, col_name in enumerate(header[1:], start=1):
                if i < len(satir):
                    deger = satir[i].strip().replace(".", "").replace(",", ".")
                    row[col_name] = deger if deger not in ("-", "", "—") else None

            sonuclar.append(row)

    return sonuclar

def parse_cinsiyet_tablo(html, bolum_kodu, bolum_adi, yil):
    """Cinsiyet tablosunu parse et — üniversite bazlı."""
    tables = parse_tables(html)
    sonuclar = []

    for tablo in tables:
        if len(tablo) < 2:
            continue
        header = [norm(h) for h in tablo[0]]

        for satir in tablo[1:]:
            if not satir or not satir[0]:
                continue
            uni_kodu = uni_kod_bul(satir[0])
            if uni_kodu is None:
                continue

            row = {
                "uni_kodu": uni_kodu,
                "uni_kisa": UNIVERSITELER[uni_kodu],
                "bolum_kodu": bolum_kodu,
                "bolum_adi": bolum_adi,
                "yil": yil,
            }
            for i, col_name in enumerate(header[1:], start=1):
                if i < len(satir):
                    deger = satir[i].strip().replace(",", ".")
                    row[col_name] = deger if deger not in ("-", "", "—") else None

            sonuclar.append(row)

    return sonuclar

def parse_puan_tablo(html, bolum_kodu, bolum_adi, yil):
    """Taban puan ve başarı sırası tablosunu parse et."""
    tables = parse_tables(html)
    sonuclar = []

    for tablo in tables:
        if len(tablo) < 2:
            continue
        header = [norm(h) for h in tablo[0]]

        for satir in tablo[1:]:
            if not satir or not satir[0]:
                continue
            uni_kodu = uni_kod_bul(satir[0])
            if uni_kodu is None:
                continue

            row = {
                "uni_kodu": uni_kodu,
                "uni_kisa": UNIVERSITELER[uni_kodu],
                "bolum_kodu": bolum_kodu,
                "bolum_adi": bolum_adi,
                "yil": yil,
            }
            for i, col_name in enumerate(header[1:], start=1):
                if i < len(satir):
                    deger = satir[i].strip().replace(".", "").replace(",", ".")
                    row[col_name] = deger if deger not in ("-", "", "—") else None

            sonuclar.append(row)

    return sonuclar

# ─── Test modu ────────────────────────────────────────────────────────────────
def test_modu():
    print("=" * 60)
    print("TEST MODU — Bilgisayar Mühendisliği 2024")
    print("=" * 60)
    bolum_kodu, bolum_adi, yil = 10024, "Bilgisayar Mühendisliği", 2024

    # Genel
    html = fetch_bolum_uni_genel(bolum_kodu, yil)
    if html:
        print(f"\n[genel] {len(html)} byte alındı")
        sonuclar = parse_genel_tablo(html, bolum_kodu, bolum_adi, yil)
        print(f"  → {len(sonuclar)} üniversite eşleşti (hedef: 5)")
        for s in sonuclar:
            print(f"     {s['uni_kisa']:6} | {s}")
    else:
        print("[genel] HATA — yanıt alınamadı")
        print("  Ham HTML (ilk 500 karakter):", html[:500] if html else "None")

    time.sleep(1)

    # Puan
    html3 = fetch_bolum_uni_puan(bolum_kodu, yil)
    if html3:
        print(f"\n[puan]  {len(html3)} byte alındı")
        sonuclar3 = parse_puan_tablo(html3, bolum_kodu, bolum_adi, yil)
        print(f"  → {len(sonuclar3)} üniversite eşleşti")
        for s in sonuclar3:
            print(f"     {s['uni_kisa']:6} | {s}")
    else:
        print("[puan]  HATA")

    # Ham tablo yapısını göster (debug)
    if html:
        tables = parse_tables(html)
        print(f"\n[debug] Toplam {len(tables)} tablo bulundu")
        for ti, tablo in enumerate(tables[:2]):
            print(f"  Tablo {ti}: {len(tablo)} satır")
            for satir in tablo[:5]:
                print(f"    {satir}")

    sys.exit(0)

# ─── Ana scrape döngüsü ───────────────────────────────────────────────────────
def main():
    records_genel    = []
    records_cinsiyet = []
    records_puan     = []

    total = len(BOLUMLER) * len(YEARS)
    done  = 0

    print(f"Hedef: {len(UNIVERSITELER)} üniversite × {len(BOLUMLER)} bölüm × {len(YEARS)} yıl")
    print(f"Toplam istek: {total * 3} (3 endpoint/kombinasyon)\n")

    for bolum_kodu, bolum_adi in BOLUMLER.items():
        for yil in YEARS:
            done += 1
            print(f"[{done:3}/{total}] {bolum_adi[:35]:35} {yil} ... ", end="", flush=True)

            # 1. Genel
            html = fetch_bolum_uni_genel(bolum_kodu, yil)
            sonuclar = parse_genel_tablo(html, bolum_kodu, bolum_adi, yil)
            records_genel.extend(sonuclar)
            time.sleep(PAUSE / 3)

            # 2. Cinsiyet
            html2 = fetch_bolum_uni_cinsiyet(bolum_kodu, yil)
            sonuclar2 = parse_cinsiyet_tablo(html2, bolum_kodu, bolum_adi, yil)
            records_cinsiyet.extend(sonuclar2)
            time.sleep(PAUSE / 3)

            # 3. Puan
            html3 = fetch_bolum_uni_puan(bolum_kodu, yil)
            sonuclar3 = parse_puan_tablo(html3, bolum_kodu, bolum_adi, yil)
            records_puan.extend(sonuclar3)

            uni_sayisi = len(sonuclar)
            print(f"OK ({uni_sayisi}/5 üniv.)")
            time.sleep(PAUSE)

    # ─── Kaydet ──────────────────────────────────────────────────────────────
    out_dir = Path("yokatlas_5uni")
    out_dir.mkdir(exist_ok=True)

    df_genel    = pd.DataFrame(records_genel)
    df_cinsiyet = pd.DataFrame(records_cinsiyet)
    df_puan     = pd.DataFrame(records_puan)

    # Sıralama: üniversite > bölüm > yıl
    for df in [df_genel, df_cinsiyet, df_puan]:
        if "uni_kodu" in df.columns and "bolum_kodu" in df.columns:
            df.sort_values(["uni_kodu", "bolum_kodu", "yil"], inplace=True)
            df.reset_index(drop=True, inplace=True)

    df_genel.to_csv(out_dir / "genel_istatistik.csv",    index=False, encoding="utf-8-sig")
    df_cinsiyet.to_csv(out_dir / "cinsiyet_dagilimi.csv", index=False, encoding="utf-8-sig")
    df_puan.to_csv(out_dir / "taban_puan_siralama.csv",   index=False, encoding="utf-8-sig")

    # Referans tabloları
    pd.DataFrame([
        {"uni_kodu": k, "uni_kisa": v, "uni_tam_adi": UNI_TAM_ADI[k]}
        for k, v in UNIVERSITELER.items()
    ]).to_csv(out_dir / "uni_kodlari.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame([
        {"bolum_kodu": k, "bolum_adi": v} for k, v in BOLUMLER.items()
    ]).to_csv(out_dir / "bolum_kodlari.csv", index=False, encoding="utf-8-sig")

    # Excel — tek dosya, çok sekme
    excel_path = out_dir / "yokatlas_5uni.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_genel.to_excel(writer,    sheet_name="Genel İstatistik",   index=False)
        df_cinsiyet.to_excel(writer, sheet_name="Cinsiyet Dağılımı",  index=False)
        df_puan.to_excel(writer,     sheet_name="Taban Puan & Sıra",  index=False)

    # Özet rapor
    print("\n" + "=" * 60)
    print("ÖZET")
    print("=" * 60)
    print(f"Genel istatistik : {len(df_genel):4} satır")
    print(f"Cinsiyet dağılımı: {len(df_cinsiyet):4} satır")
    print(f"Taban puan/sıra  : {len(df_puan):4} satır")
    if not df_genel.empty and "uni_kisa" in df_genel.columns:
        print("\nÜniversite başına kayıt (genel):")
        print(df_genel.groupby("uni_kisa").size().to_string())
    print(f"\n✓ Dosyalar: {out_dir}/")
    print(f"  - genel_istatistik.csv")
    print(f"  - cinsiyet_dagilimi.csv")
    print(f"  - taban_puan_siralama.csv")
    print(f"  - yokatlas_5uni.xlsx")

# ─── Giriş noktası ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_modu()
    else:
        main()