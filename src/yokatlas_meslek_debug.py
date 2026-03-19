"""
meslek-lisans.php sayfasinin yapisini incele.
Calistir: python src/yokatlas_meslek_debug.py
"""
import sys, time, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=opts)

url = "https://yokatlas.yok.gov.tr/meslek-lisans.php?b=13987"
print(f"Gidiliyor: {url}")
driver.get(url)
print("10 saniye bekleniyor...")
time.sleep(10)

src = driver.page_source
print(f"HTML uzunlugu: {len(src)}")
print(f"Baslik: {driver.title}")

# Tablolar
tables = driver.find_elements(By.TAG_NAME, "table")
print(f"\nTablo sayisi: {len(tables)}")
for i, t in enumerate(tables[:10]):
    rows = t.find_elements(By.TAG_NAME, "tr")
    print(f"  Tablo {i}: {len(rows)} satir, id='{t.get_attribute('id')}', class='{t.get_attribute('class')}'")
    for j, tr in enumerate(rows[:3]):
        cells = [td.text.strip()[:30] for td in tr.find_elements(By.XPATH, "td|th")]
        if cells:
            print(f"    satir {j}: {cells}")

# iframe var mi?
iframes = driver.find_elements(By.TAG_NAME, "iframe")
print(f"\niframe sayisi: {len(iframes)}")
for f in iframes:
    print(f"  src={f.get_attribute('src')}")

# .load() cagrılari
loads = re.findall(r'\$\(["\']([^"\']+)["\']\)\.(load)\s*\(\s*["\']([^"\']+)', src)
print(f"\n.load() cagrılari: {loads}")

# Inline scriptlerde yokatlas URL referanslari
urls_in_scripts = re.findall(r'["\']([^"\']*(?:content|bolum|panel|php)[^"\']*)["\']', src)
print(f"\nPHP/content referanslari ({len(urls_in_scripts)}):")
for u in sorted(set(urls_in_scripts))[:30]:
    print(f"  {u}")

# div id'leri
divs = re.findall(r'<div[^>]+id=["\']([^"\']+)["\']', src)
print(f"\ndiv id'leri: {divs}")

# Sayfa kaynak ilk 4000 char
print(f"\n--- Kaynak ilk 4000 ---")
print(src[:4000])