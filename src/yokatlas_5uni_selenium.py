"""
YOK Atlas — 5 Teknik Universite Scraper
========================================
NASIL CALISIR:
  1. Chrome'u debug modunda ac (asagidaki komutu calistir):

     Windows:
     "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Temp\chrome-debug"

  2. Acilan Chrome'da yokatlas.yok.gov.tr'ye gir, sayfanin yuklenmesini bekle.
     (Cloudflare'i elle gecmis olursun)

  3. Bu scripti calistir:
     python src/yokatlas_5uni_selenium.py

  Test modu (sadece 1 bolum):
     python src/yokatlas_5uni_selenium.py --test

Kurulum: pip install selenium pandas openpyxl
(undetected-chromedriver gerekmez — normal selenium yeterli)
"""

import sys
import time
import pandas as pd
from pathlib import Path
from html.parser import HTMLParser

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    sys.exit("HATA: pip install selenium pandas openpyxl")

DEBUG_PORT = 9222   # Chrome'u bu portla baslat

# ══════════════════════════════════════════════════════════════════════════════
# SABİTLER
# ══════════════════════════════════════════════════════════════════════════════

UNIVERSITELER = {
    1055: "ITU",
    1084: "ODTU",
    1101: "YTU",
    1044: "GTU",
    1058: "IYTE",
}
UNI_TAM_ADI = {
    1055: "Istanbul Teknik Universitesi",
    1084: "Orta Dogu Teknik Universitesi",
    1101: "Yildiz Teknik Universitesi",
    1044: "Gebze Teknik Universitesi",
    1058: "Izmir Yuksek Teknoloji Enstitusu",
}
UNI_ANAHTAR = {
    "istanbul teknik"            : 1055,
    "i\u0307stanbul teknik"      : 1055,
    "orta dogu teknik"           : 1084,
    "orta do\u011fu teknik"      : 1084,
    "yildiz teknik"              : 1101,
    "y\u0131ld\u0131z teknik"    : 1101,
    "gebze teknik"               : 1044,
    "izmir yuksek teknoloji"     : 1058,
    "izmir y\u00fcksek teknoloji": 1058,
}
BOLUMLER = {
    10024: "Bilgisayar Muhendisligi",
    10057: "Elektrik-Elektronik Muhendisligi",
    10058: "Elektronik Muhendisligi",
    10059: "Elektronik ve Haberlesme Muhendisligi",
    10128: "Makine Muhendisligi",
    10073: "Havacilik ve Uzay Muhendisligi",
    10074: "Havacilik Muhendisligi",
    10178: "Ucak Muhendisligi",
    10141: "Mekatronik Muhendisligi",
    10030: "Bilisim Sistemleri Muhendisligi",
    10029: "Bilgisayar ve Yazilim Muhendisligi",
    10146: "Metalurji ve Malzeme Muhendisligi",
    10065: "Gemi Insaati ve Gemi Makineleri Muhendisligi",
    10066: "Gemi Makineleri Isletme Muhendisligi",
    10049: "Endustri Muhendisligi",
    10082: "Imalat Muhendisligi",
    10162: "Savunma Teknolojileri Muhendisligi",
}
YEAR_PREFIX = {
    2024: "",
    2023: "2023/",
    2022: "2022/",
    2021: "2021/",
    2020: "2020/",
}
YEARS  = [2024, 2023, 2022, 2021, 2020]
DOMAIN = "https://yokatlas.yok.gov.tr"

# ══════════════════════════════════════════════════════════════════════════════
# DRIVER — mevcut Chrome oturumuna baglan
# ══════════════════════════════════════════════════════════════════════════════

def driver_baglan() -> webdriver.Chrome:
    """
    Hali hazirda acik olan Chrome'a (debug port 9222) baglan.
    Chrome su komutla baslatilmis olmali:
      chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\Temp\\chrome-debug"
    """
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    try:
        driver = webdriver.Chrome(options=opts)
        print(f"Baglandi: {driver.title} ({driver.current_url})")
        return driver
    except WebDriverException as e:
        print(f"\nHATA: Chrome'a baglanılamadi.")
        print(f"Chrome debug modunda acik mi? (port {DEBUG_PORT})")
        print("\nSu komutu calistir:")
        print(r'  "C:\Program Files\Google\Chrome\Application\chrome.exe" '
              r'--remote-debugging-port=9222 --user-data-dir="C:\Temp\chrome-debug"')
        print(f"\nDetay: {e}")
        sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# HTML PARSER
# ══════════════════════════════════════════════════════════════════════════════

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables     = []
        self._cur_table = []
        self._cur_row   = []
        self._cur_cell  = ""
        self._in_cell   = False
        self._depth     = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._cur_table = []
        elif tag == "tr":
            self._cur_row = []
        elif tag in ("td", "th"):
            self._in_cell  = True
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

def parse_tables_from_html(html: str) -> list:
    p = TableParser()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.tables

# ══════════════════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ══════════════════════════════════════════════════════════════════════════════

_TR = str.maketrans(
    "\u0131\u015f\u00e7\u011f\u00f6\u00fc\u0130\u015e\u00c7\u011e\u00d6\u00dc",
    "iscgouISCGOU"
)

def norm(s: str) -> str:
    return s.lower().translate(_TR).strip().replace(" ","_").replace("/","_").replace("-","_")

def uni_kod_bul(adi: str):
    low = adi.lower().translate(_TR)
    for anahtar, kod in UNI_ANAHTAR.items():
        if anahtar.lower().translate(_TR) in low:
            return kod
    return None

def temizle(s: str):
    v = s.strip()
    return None if v in ("-","—","","\u2013") else v.replace(".","").replace(",",".")

def bolum_url(bolum_kodu: int, yil: int) -> str:
    prefix = YEAR_PREFIX.get(yil, f"{yil}/")
    return f"{DOMAIN}/{prefix}lisans-bolum.php?b={bolum_kodu}"

def engellendi_mi(driver) -> bool:
    try:
        src = driver.page_source.lower()
        return "access to this page has been blocked" in src
    except Exception:
        return False

# ══════════════════════════════════════════════════════════════════════════════
# SAYFA YUKLEand TABLO OKU
# ══════════════════════════════════════════════════════════════════════════════

def sayfayi_yukle_ve_oku(driver, url: str) -> list:
    """
    URL'i ac, #bs-collapse ve #bs-collapse2 div'lerinin dolmasini bekle,
    tablolari DOM'dan oku.
    """
    driver.get(url)

    # #bs-collapse div'i dolana kadar bekle (max 20sn)
    try:
        WebDriverWait(driver, 20).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#bs-collapse .panel")) > 0
                   or len(d.find_elements(By.CSS_SELECTOR, "table tr")) > 2
        )
        time.sleep(0.5)
    except TimeoutException:
        time.sleep(3)  # yine de bekle

    if engellendi_mi(driver):
        return []

    # DOM'dan tablolari oku
    tablolar = []
    try:
        for tablo_el in driver.find_elements(By.TAG_NAME, "table"):
            rows = []
            for tr in tablo_el.find_elements(By.TAG_NAME, "tr"):
                hucre = [td.text.strip() for td in tr.find_elements(By.XPATH, "td|th")]
                if any(hucre):
                    rows.append(hucre)
            if len(rows) > 1:
                tablolar.append(rows)
    except Exception as e:
        print(f"\n  [!] DOM okuma hatasi: {e}")

    # Tablo yoksa sayfa kaynagından parse et
    if not tablolar:
        tablolar = parse_tables_from_html(driver.page_source)
        tablolar = [t for t in tablolar if len(t) > 1]

    return tablolar

# ══════════════════════════════════════════════════════════════════════════════
# PARSE + FİLTRELE
# ══════════════════════════════════════════════════════════════════════════════

def tablolari_isle(tablolar: list, bolum_kodu: int, bolum_adi: str, yil: int) -> dict:
    sonuc = {"genel": [], "cinsiyet": [], "puan": []}
    for tablo in tablolar:
        if len(tablo) < 2:
            continue
        header = [norm(h) for h in tablo[0]]
        if not header or not header[0]:
            continue
        header_str = " ".join(header)
        if "kadin" in header_str or "erkek" in header_str:
            tip = "cinsiyet"
        elif "puan" in header_str or "sira" in header_str or "basari" in header_str:
            tip = "puan"
        else:
            tip = "genel"
        for satir in tablo[1:]:
            if not satir or not satir[0].strip():
                continue
            uni_kodu = uni_kod_bul(satir[0])
            if uni_kodu is None:
                continue
            row = {
                "uni_kodu"   : uni_kodu,
                "uni_kisa"   : UNIVERSITELER[uni_kodu],
                "uni_tam_adi": UNI_TAM_ADI[uni_kodu],
                "bolum_kodu" : bolum_kodu,
                "bolum_adi"  : bolum_adi,
                "yil"        : yil,
            }
            for i, col in enumerate(header[1:], start=1):
                if i < len(satir):
                    row[col] = temizle(satir[i])
            sonuc[tip].append(row)
    return sonuc

# ══════════════════════════════════════════════════════════════════════════════
# KAYDET
# ══════════════════════════════════════════════════════════════════════════════

def kaydet(records: dict, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    df_g = pd.DataFrame(records["genel"])
    df_c = pd.DataFrame(records["cinsiyet"])
    df_p = pd.DataFrame(records["puan"])
    for df in [df_g, df_c, df_p]:
        cols = [c for c in ["uni_kodu","bolum_kodu","yil"] if c in df.columns]
        if cols:
            df.sort_values(cols, inplace=True)
            df.reset_index(drop=True, inplace=True)
    df_g.to_csv(out_dir / "genel_istatistik.csv",   index=False, encoding="utf-8-sig")
    df_c.to_csv(out_dir / "cinsiyet_dagilimi.csv",   index=False, encoding="utf-8-sig")
    df_p.to_csv(out_dir / "taban_puan_siralama.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(out_dir / "yokatlas_5uni.xlsx", engine="openpyxl") as writer:
        df_g.to_excel(writer, sheet_name="Genel",    index=False)
        df_c.to_excel(writer, sheet_name="Cinsiyet", index=False)
        df_p.to_excel(writer, sheet_name="Puan",     index=False)
    print(f"\n{'='*55}")
    print(f"Kaydedildi: {out_dir}/")
    print(f"  genel    : {len(df_g):4} satir")
    print(f"  cinsiyet : {len(df_c):4} satir")
    print(f"  puan     : {len(df_p):4} satir")
    if not df_g.empty and "uni_kisa" in df_g.columns:
        print("\nUniversite basina kayit:")
        print(df_g.groupby("uni_kisa").size().rename("satir").to_string())

# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

def test_modu():
    print("=" * 55)
    print("TEST — Bilgisayar Muhendisligi 2024")
    print("Mevcut Chrome oturumuna baglaniliyor...")
    print("=" * 55)
    driver = driver_baglan()

    url = bolum_url(10024, 2024)
    print(f"\nURL: {url}")
    tablolar = sayfayi_yukle_ve_oku(driver, url)

    print(f"Baslik: {driver.title}")
    print(f"{len(tablolar)} tablo bulundu")

    for ti, tablo in enumerate(tablolar[:5]):
        print(f"\nTablo {ti} ({len(tablo)} satir):")
        for satir in tablo[:5]:
            print(f"  {satir}")

    sonuc = tablolari_isle(tablolar, 10024, "Bilgisayar Muhendisligi", 2024)
    for tip, rows in sonuc.items():
        print(f"\n[{tip}] {len(rows)} eslesme")
        for r in rows:
            print(f"  {r['uni_kisa']:6} {r}")

    # Driver'i kapatma — mevcut oturum korunsin
    sys.exit(0)

# ══════════════════════════════════════════════════════════════════════════════
# ANA DÖNGÜ
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("Mevcut Chrome oturumuna baglaniliyor...")
    driver  = driver_baglan()
    records = {"genel": [], "cinsiyet": [], "puan": []}
    out_dir = Path("yokatlas_5uni")
    total   = len(BOLUMLER) * len(YEARS)
    done    = 0
    print(f"Basliyor: {len(BOLUMLER)} bolum x {len(YEARS)} yil = {total} kombo\n")
    try:
        for yil in YEARS:
            for bolum_kodu, bolum_adi in BOLUMLER.items():
                done += 1
                print(f"[{done:3}/{total}] {bolum_adi[:30]:30} {yil}", end="  ", flush=True)
                url      = bolum_url(bolum_kodu, yil)
                tablolar = sayfayi_yukle_ve_oku(driver, url)
                sonuc    = tablolari_isle(tablolar, bolum_kodu, bolum_adi, yil)
                for tip in ["genel", "cinsiyet", "puan"]:
                    records[tip].extend(sonuc[tip])
                print(f"{len(tablolar)} tablo  {len(sonuc['genel'])}/5")
                time.sleep(1.0)
                if done % 30 == 0:
                    print(f"\n  [ara kayit @ {done}/{total}]")
                    kaydet(records, out_dir)
    except KeyboardInterrupt:
        print("\nDurduruluyor...")
    # Driver'i kapatma — kullanicinin oturumu korunsin

    kaydet(records, out_dir)

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--test" in sys.argv:
        test_modu()
    else:
        main()