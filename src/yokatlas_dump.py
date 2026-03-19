"""
Sayfa HTML'ini dosyaya yaz — tablo nerede gizli?
Calistir: python src/yokatlas_dump.py
"""
import sys, time
try:
    import undetected_chromedriver as uc
except ImportError:
    sys.exit("pip install undetected-chromedriver")

opts = uc.ChromeOptions()
opts.add_argument("--no-sandbox")
opts.add_argument("--window-size=1440,900")
driver = uc.Chrome(options=opts, use_subprocess=True, version_main=145)

try:
    driver.get("https://yokatlas.yok.gov.tr/lisans-bolum.php?b=10024")
    print("Bekleniyor 15sn...")
    time.sleep(15)
    html = driver.page_source
    with open("yokatlas_dump.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Kaydedildi: yokatlas_dump.html ({len(html)} karakter)")
    print("Baslik:", driver.title)
finally:
    driver.quit()