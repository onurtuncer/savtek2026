"""
YOK Atlas — meslek-lisans.php Tam Scraper
==========================================
Tum panelleri sirayla acip icerik yuklendikten sonra
tablolari ceker, CSV + Excel olarak kaydeder.

Hedef bölümler (meslek kodu → bolum adi):
  13987 → Makine Muhendisligi
  + diger bolumler asagida BOLUMLER sozlugunde

Kurulum  : pip install selenium pandas openpyxl
Chrome debug modunda acik olmali:
  chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\Temp\\chrome-debug"

Calistir : python src/yokatlas_meslek_scraper.py
Test     : python src/yokatlas_meslek_scraper.py --test
"""

import sys
import time
import re
import pandas as pd
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    sys.exit("HATA: pip install selenium pandas openpyxl")

DEBUG_PORT = 9222
DOMAIN     = "https://yokatlas.yok.gov.tr"

# ══════════════════════════════════════════════════════════════════════════════
# Hedef bölümler — meslek kodu : bolum adi
# meslek-lisans.php?b=XXXX  formatında
# ══════════════════════════════════════════════════════════════════════════════
BOLUMLER = {
    13987: "Makine Muhendisligi",
    13965: "Bilgisayar Muhendisligi",
    13969: "Elektrik-Elektronik Muhendisligi",
    13970: "Elektronik Muhendisligi",
    13971: "Elektronik ve Haberlesme Muhendisligi",
    13974: "Havacilik ve Uzay Muhendisligi",
    13988: "Mekatronik Muhendisligi",
    13993: "Metalurji ve Malzeme Muhendisligi",
    13963: "Bilisim Sistemleri Muhendisligi",
    13994: "Endustri Muhendisligi",
    13984: "Makine Muhendisligi (2. ogretim)",  # varsa
}

# ══════════════════════════════════════════════════════════════════════════════
# DRIVER
# ══════════════════════════════════════════════════════════════════════════════

def driver_baglan():
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    try:
        driver = webdriver.Chrome(options=opts)
        print(f"Baglandi: {driver.title}")
        return driver
    except WebDriverException as e:
        print("Chrome debug modunda acik mi?")
        print(r'chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\Temp\chrome-debug"')
        sys.exit(str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TABLO PARSE
# ══════════════════════════════════════════════════════════════════════════════

def dom_tablo_oku(element) -> list:
    """Selenium element'inden tablo satirlarini cek."""
    rows = []
    for tr in element.find_elements(By.TAG_NAME, "tr"):
        hucre = [td.text.strip() for td in tr.find_elements(By.XPATH, "td|th")]
        if any(h for h in hucre):
            rows.append(hucre)
    return rows

# ══════════════════════════════════════════════════════════════════════════════
# PANEL AÇ + VERİ ÇEK
# ══════════════════════════════════════════════════════════════════════════════

def tum_panelleri_cek(driver, bolum_kodu: int, bolum_adi: str) -> list:
    """
    meslek-lisans.php?b=BOLUM_KODU sayfasini ac,
    tum panelleri sirayla tikla, icerik yuklenmesini bekle,
    tablolari cek.
    Donus: [{"panel_id": ..., "panel_baslik": ..., "tablo_no": ...,
              "bolum_kodu": ..., "bolum_adi": ..., "header": [...], "satirlar": [...]}, ...]
    """
    url = f"{DOMAIN}/meslek-lisans.php?b={bolum_kodu}"
    print(f"\n  URL: {url}")
    driver.get(url)
    time.sleep(4)

    src = driver.page_source
    if "access to this page has been blocked" in src.lower():
        print("  ENGELLENDI — atlanıyor")
        return []

    # Tum panel toggle linklerini bul (href="#cmeslek_X")
    panel_links = driver.find_elements(
        By.CSS_SELECTOR, "a[href^='#cmeslek_'], a[data-target^='#cmeslek_']"
    )
    print(f"  {len(panel_links)} panel bulundu")

    sonuclar = []

    for link in panel_links:
        href = link.get_attribute("href") or link.get_attribute("data-target") or ""
        panel_id = href.split("#")[-1]  # cmeslek_1
        panel_no = panel_id.replace("cmeslek_", "")
        baslik   = link.text.strip().replace("\n", " ")[:80]

        print(f"    [{panel_id}] {baslik[:50]} ... ", end="", flush=True)

        # Panel zaten acik mi?
        try:
            collapse_div = driver.find_element(By.ID, panel_id)
            is_open = "in" in (collapse_div.get_attribute("class") or "")
        except Exception:
            is_open = False

        # Tikla (kapaliysa ac)
        if not is_open:
            try:
                driver.execute_script("arguments[0].click();", link)
            except Exception:
                try:
                    link.click()
                except Exception:
                    print("TIKLANAMADI")
                    continue

        # icerik_meslek_X div'inin dolmasini bekle
        icerik_id = f"icerik_meslek_{panel_no}"
        try:
            WebDriverWait(driver, 12).until(
                lambda d: (
                    lambda el: el is not None and len(el.text.strip()) > 20
                )(next(iter(d.find_elements(By.ID, icerik_id)), None))
            )
            time.sleep(0.3)
        except TimeoutException:
            print("TIMEOUT")
            continue

        # Tabloları çek
        try:
            icerik_el = driver.find_element(By.ID, icerik_id)
            tablolar_el = icerik_el.find_elements(By.TAG_NAME, "table")

            if not tablolar_el:
                print("tablo yok")
                continue

            for t_no, tablo_el in enumerate(tablolar_el):
                rows = dom_tablo_oku(tablo_el)
                if len(rows) < 2:
                    continue

                header = rows[0]
                for satir in rows[1:]:
                    if not any(satir):
                        continue
                    kayit = {
                        "bolum_kodu"  : bolum_kodu,
                        "bolum_adi"   : bolum_adi,
                        "panel_id"    : panel_id,
                        "panel_no"    : panel_no,
                        "panel_baslik": baslik,
                        "tablo_no"    : t_no,
                    }
                    for i, col in enumerate(header):
                        col_key = col.strip()[:50] if col.strip() else f"sutun_{i}"
                        kayit[col_key] = satir[i].strip() if i < len(satir) else None
                    sonuclar.append(kayit)

            print(f"{len(tablolar_el)} tablo, {len(rows)-1} satir")

        except Exception as e:
            print(f"HATA: {e}")
            continue

    return sonuclar

# ══════════════════════════════════════════════════════════════════════════════
# KAYDET
# ══════════════════════════════════════════════════════════════════════════════

def kaydet(records: list, out_dir: Path):
    out_dir.mkdir(exist_ok=True)

    if not records:
        print("Kaydedilecek veri yok.")
        return

    df = pd.DataFrame(records)

    # Panel bazinda ayri sekmeler
    csv_path   = out_dir / "meslek_atlas_ham.csv"
    excel_path = out_dir / "meslek_atlas.xlsx"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        # Ham veri — tum paneller
        df.to_excel(writer, sheet_name="Ham Veri", index=False)

        # Her bolum icin ayri sekme
        for bolum_kodu, grp in df.groupby("bolum_kodu"):
            bolum_adi = grp["bolum_adi"].iloc[0][:25]
            sheet_name = f"{bolum_kodu}"
            grp.to_excel(writer, sheet_name=sheet_name, index=False)

        # Panel bazinda pivot — hangi panelde ne var ozet
        ozet = df.groupby(["bolum_kodu","bolum_adi","panel_no","panel_baslik"]).size().reset_index(name="satir_sayisi")
        ozet.to_excel(writer, sheet_name="Panel Ozet", index=False)

    print(f"\n{'='*55}")
    print(f"Kaydedildi: {out_dir}/")
    print(f"  meslek_atlas_ham.csv : {len(df)} satir")
    print(f"  meslek_atlas.xlsx    : {df['bolum_kodu'].nunique()} bolum, "
          f"{df['panel_id'].nunique()} benzersiz panel")
    print(f"\nPanel ozeti:")
    print(df.groupby(["panel_no","panel_baslik"]).size()
           .reset_index(name="satir")
           .to_string(index=False))

# ══════════════════════════════════════════════════════════════════════════════
# TEST — sadece 1 bolum
# ══════════════════════════════════════════════════════════════════════════════

def test_modu():
    print("="*55)
    print("TEST — Makine Muhendisligi (13987)")
    print("="*55)
    driver = driver_baglan()
    records = tum_panelleri_cek(driver, 13987, "Makine Muhendisligi")
    print(f"\nToplam {len(records)} kayit alindi")
    if records:
        df = pd.DataFrame(records)
        print(df[["panel_baslik","tablo_no"]].drop_duplicates().to_string(index=False))
        print("\nIlk 5 kayit:")
        print(df.head().to_string())
    sys.exit(0)

# ══════════════════════════════════════════════════════════════════════════════
# ANA DÖNGÜ
# ══════════════════════════════════════════════════════════════════════════════

def main():
    driver  = driver_baglan()
    out_dir = Path("yokatlas_meslek")
    records = []

    print(f"Basliyor: {len(BOLUMLER)} bolum\n")

    for bolum_kodu, bolum_adi in BOLUMLER.items():
        print(f"\n[{bolum_kodu}] {bolum_adi}")
        try:
            rows = tum_panelleri_cek(driver, bolum_kodu, bolum_adi)
            records.extend(rows)
            print(f"  → {len(rows)} kayit")
        except KeyboardInterrupt:
            print("\nDurduruluyor...")
            break
        except Exception as e:
            print(f"  HATA: {e}")
            continue

        time.sleep(1.5)

    kaydet(records, out_dir)

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--test" in sys.argv:
        test_modu()
    else:
        main()