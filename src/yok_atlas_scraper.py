"""
YÖK Atlas — Savunma Sanayi İlgili Mühendislik Bölümleri Scraper
Çalıştır: pip install requests pandas openpyxl && python yokatlas_scraper.py
Çıktı   : yokatlas_muhendislik_verileri.xlsx + 5 ayrı CSV
"""

import requests
import json
import time
import pandas as pd
from pathlib import Path

# ─── Hedef bölümler (savunma sanayi ile ilgili) ───────────────────────────────
BOLUMLER = {
    # Kod  : Bölüm adı
    10024  : "Bilgisayar Mühendisliği",
    10057  : "Elektrik-Elektronik Mühendisliği",
    10058  : "Elektronik Mühendisliği",
    10059  : "Elektronik ve Haberleşme Mühendisliği",
    10128  : "Makine Mühendisliği",
    10073  : "Havacılık ve Uzay Mühendisliği",
    10074  : "Havacılık Mühendisliği",
    10072  : "Hava Trafik Kontrolü",
    10178  : "Uçak Mühendisliği",   # bazı üniversitelerde ayrı kod
    10141  : "Mekatronik Mühendisliği",
    10030  : "Bilişim Sistemleri Mühendisliği",
    10029  : "Bilgisayar ve Yazılım Mühendisliği",
    10146  : "Metalurji ve Malzeme Mühendisliği",
    10065  : "Gemi İnşaatı ve Gemi Makineleri Mühendisliği",
    10066  : "Gemi Makineleri İşletme Mühendisliği",
    10049  : "Endüstri Mühendisliği",
    10082  : "İmalat Mühendisliği",
    10162  : "Savunma Teknolojileri Mühendisliği",
    10904  : "Mühendislik Programları (genel)",
}

BASE  = "https://yokatlas.yok.gov.tr/content/lisans-bolum"
YEARS = [2020, 2021, 2022, 2023, 2024]
PAUSE = 0.8   # saniye — sunucuyu yormamak için

# ─── YÖK Atlas endpoint'leri ─────────────────────────────────────────────────
# Her bölüm sayfasının alt endpoint'leri (HTML fragment, JSON değil)
# b3100_1_1 → genel istatistikler (kontenjan, yerleşen, kayıt)
# b3100_1_2 → cinsiyet dağılımı
# b3100_2_1 → taban/tavan puan ve başarı sırası

def fetch_genel(bolum_kodu, yil):
    """Kontenjan, yerleşen, kayıt yaptıran sayıları."""
    url = f"{BASE}/3100/b3100_1_1.php?b={bolum_kodu}&y={yil}"
    try:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0 (research)"})
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None

def fetch_cinsiyet(bolum_kodu, yil):
    """Cinsiyet dağılımı."""
    url = f"{BASE}/3100/b3100_1_2.php?b={bolum_kodu}&y={yil}"
    try:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0 (research)"})
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None

def fetch_puan(bolum_kodu, yil):
    """Taban puan ve başarı sırası."""
    url = f"{BASE}/3100/b3100_2_1.php?b={bolum_kodu}&y={yil}"
    try:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0 (research)"})
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None

# ─── HTML parse helpers ───────────────────────────────────────────────────────
from html.parser import HTMLParser

class TableParser(HTMLParser):
    """Basit tablo parser — <table> içindeki satır/hücre verilerini çeker."""
    def __init__(self):
        super().__init__()
        self.tables = []
        self._current_table = []
        self._current_row = []
        self._current_cell = ""
        self._in_td = self._in_th = False
        self._in_table = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table += 1
            self._current_table = []
        elif tag in ("tr",):
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_td = True
            self._current_cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_td:
            self._current_row.append(self._current_cell.strip())
            self._in_td = False
        elif tag == "tr" and self._current_row:
            self._current_table.append(self._current_row)
            self._current_row = []
        elif tag == "table" and self._in_table:
            self.tables.append(self._current_table)
            self._current_table = []
            self._in_table -= 1

    def handle_data(self, data):
        if self._in_td:
            self._current_cell += data

def parse_tables(html):
    if not html:
        return []
    p = TableParser()
    p.feed(html)
    return p.tables

# ─── Ana scrape döngüsü ───────────────────────────────────────────────────────
records_genel   = []
records_cinsiyet = []
records_puan    = []

total = len(BOLUMLER) * len(YEARS)
done  = 0

for kodu, isim in BOLUMLER.items():
    for yil in YEARS:
        done += 1
        print(f"[{done}/{total}] {isim} ({kodu}) — {yil} ... ", end="", flush=True)

        # 1. Genel istatistikler
        html = fetch_genel(kodu, yil)
        tables = parse_tables(html)
        genel_row = {"bolum_kodu": kodu, "bolum_adi": isim, "yil": yil}
        if tables:
            for tablo in tables:
                for satir in tablo:
                    if len(satir) >= 2:
                        anahtar = satir[0].lower().replace(" ", "_").replace("ı","i").replace("ş","s").replace("ç","c").replace("ğ","g").replace("ö","o").replace("ü","u")
                        deger   = satir[1].replace(".", "").replace(",", ".").strip()
                        genel_row[anahtar] = deger
        records_genel.append(genel_row)

        time.sleep(PAUSE / 2)

        # 2. Cinsiyet dağılımı
        html2 = fetch_cinsiyet(kodu, yil)
        tables2 = parse_tables(html2)
        cin_row = {"bolum_kodu": kodu, "bolum_adi": isim, "yil": yil}
        if tables2:
            for tablo in tables2:
                for satir in tablo:
                    if len(satir) >= 2:
                        anahtar = satir[0].lower().replace(" ", "_")
                        for ch in "ışçğöü":
                            rep = {"ı":"i","ş":"s","ç":"c","ğ":"g","ö":"o","ü":"u"}
                            anahtar = anahtar.replace(ch, rep.get(ch, ch))
                        cin_row[anahtar] = satir[1].strip()
        records_cinsiyet.append(cin_row)

        time.sleep(PAUSE / 2)

        # 3. Taban puan
        html3 = fetch_puan(kodu, yil)
        tables3 = parse_tables(html3)
        puan_row = {"bolum_kodu": kodu, "bolum_adi": isim, "yil": yil}
        if tables3:
            for tablo in tables3:
                for satir in tablo:
                    if len(satir) >= 2:
                        anahtar = "puan_" + satir[0].lower().replace(" ", "_")
                        for ch in "ışçğöü":
                            rep = {"ı":"i","ş":"s","ç":"c","ğ":"g","ö":"o","ü":"u"}
                            anahtar = anahtar.replace(ch, rep.get(ch, ch))
                        puan_row[anahtar] = satir[1].strip()
        records_puan.append(puan_row)

        print("OK")
        time.sleep(PAUSE)

# ─── DataFrame'e çevir ve kaydet ─────────────────────────────────────────────
out_dir = Path("yokatlas_cikti")
out_dir.mkdir(exist_ok=True)

df_genel    = pd.DataFrame(records_genel)
df_cinsiyet = pd.DataFrame(records_cinsiyet)
df_puan     = pd.DataFrame(records_puan)

# CSV'ler
df_genel.to_csv(out_dir / "genel_istatistik.csv", index=False, encoding="utf-8-sig")
df_cinsiyet.to_csv(out_dir / "cinsiyet_dagilimi.csv", index=False, encoding="utf-8-sig")
df_puan.to_csv(out_dir / "taban_puan_siralama.csv", index=False, encoding="utf-8-sig")

# Bölüm kodu referans tablosu
df_bolumler = pd.DataFrame([
    {"bolum_kodu": k, "bolum_adi": v} for k, v in BOLUMLER.items()
])
df_bolumler.to_csv(out_dir / "bolum_kodlari.csv", index=False, encoding="utf-8-sig")

# Excel — tek dosyada tüm sekmeler
with pd.ExcelWriter(out_dir / "yokatlas_muhendislik.xlsx", engine="openpyxl") as writer:
    df_genel.to_excel(writer,    sheet_name="Genel İstatistik", index=False)
    df_cinsiyet.to_excel(writer, sheet_name="Cinsiyet Dağılımı", index=False)
    df_puan.to_excel(writer,     sheet_name="Taban Puan & Sıra", index=False)
    df_bolumler.to_excel(writer, sheet_name="Bölüm Kodları", index=False)

print("\n✓ Tamamlandı. Dosyalar: yokatlas_cikti/")


# ─── Hızlı test (sadece 1 bölüm, 1 yıl) ─────────────────────────────────────
# Çalıştırmak için: python yokatlas_scraper.py --test
if __name__ == "__main__" and len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "--test":
    import sys
    print("=== TEST MODU: Bilgisayar Mühendisliği 2024 ===")
    kodu, isim, yil = 10024, "Bilgisayar Mühendisliği", 2024
    for ep_name, fn in [("genel", fetch_genel), ("cinsiyet", fetch_cinsiyet), ("puan", fetch_puan)]:
        html = fn(kodu, yil)
        if html and len(html) > 100:
            tables = parse_tables(html)
            print(f"  [{ep_name}] OK — {len(html)} byte, {len(tables)} tablo")
            if tables and tables[0]:
                for row in tables[0][:4]:
                    print(f"    {row}")
        else:
            print(f"  [{ep_name}] HATA — boş veya kısa yanıt: {html[:80] if html else 'None'}")
        time.sleep(0.5)
    sys.exit(0)