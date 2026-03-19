"""
YOK Atlas — JS Inspect
mamut-js.js icindeki AJAX URL'lerini bul.
Calistir: python yokatlas_inspect.py
"""

import sys
import time
import re

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
except ImportError:
    sys.exit("pip install undetected-chromedriver")

def driver_baslat():
    opts = uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--lang=tr-TR")
    return uc.Chrome(options=opts, use_subprocess=True, version_main=145)

driver = driver_baslat()

try:
    # 1. mamut-js.js dosyasini oku
    print("mamut-js.js okunuyor...")
    driver.get("https://yokatlas.yok.gov.tr/assets/js/mamut-js.js")
    time.sleep(3)
    js_content = driver.find_element(By.TAG_NAME, "body").text

    # PHP/content URL'lerini bul
    urls = re.findall(r'["\']([^"\']*(?:content|bolum|panel|lisans)[^"\']*\.php[^"\']*)["\']', js_content)
    print(f"\n--- PHP URL'leri ({len(urls)} adet) ---")
    for u in sorted(set(urls)):
        print(f"  {u}")

    # $.ajax veya $.load cagrilarini bul
    ajax_calls = re.findall(r'(?:load|ajax|get|post)\s*\(\s*["\']([^"\']+)["\']', js_content)
    print(f"\n--- AJAX/load cagrılari ({len(ajax_calls)} adet) ---")
    for u in sorted(set(ajax_calls)):
        print(f"  {u}")

    # Tum 'b3100' referanslarini bul
    b3100 = re.findall(r'["\'][^"\']*b3100[^"\']*["\']', js_content)
    print(f"\n--- b3100 referanslari ---")
    for u in sorted(set(b3100)):
        print(f"  {u}")

    # JS ilk 3000 karakter
    print(f"\n--- JS ilk 3000 char ---")
    print(js_content[:3000])

    # 2. Ana bolum sayfasini ac, JS calistiktan sonra network isteklerini goster
    print("\n\nAna bolum sayfasi aciliyor...")
    driver.get("https://yokatlas.yok.gov.tr/lisans-bolum.php?b=10024")
    time.sleep(12)
    print(f"Baslik: {driver.title}")

    # Sayfa HTML'inin tamamini goster
    src = driver.page_source
    print(f"\nSayfa HTML uzunlugu: {len(src)} karakter")

    # div id'leri bul (tablonun render edilecegi yeri bulmak icin)
    divs = re.findall(r'<div[^>]+id=["\']([^"\']+)["\']', src)
    print(f"\n--- div id'leri ---")
    for d in divs[:30]:
        print(f"  #{d}")

    # iframe var mi?
    iframes = re.findall(r'<iframe[^>]*src=["\']([^"\']+)["\']', src)
    print(f"\n--- iframe'ler ---")
    for i in iframes:
        print(f"  {i}")

    # Tum script src'leri
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', src)
    print(f"\n--- Script src'leri ---")
    for s in scripts:
        print(f"  {s}")

    # load() cagrilari inline JS'de
    loads = re.findall(r'\.load\s*\(\s*["\']([^"\']+)["\']', src)
    print(f"\n--- .load() cagrılari ---")
    for l in loads:
        print(f"  {l}")

finally:
    try:
        driver.quit()
    except Exception:
        pass