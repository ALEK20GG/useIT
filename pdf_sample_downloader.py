from playwright.sync_api import sync_playwright
import os
import time

BASE_URL = "https://magazine.raspberrypi.com/issues/{}/pdf/download"
OUTPUT_DIR = "raspberrypi_pdfs"
TOTAL = 100

os.makedirs(OUTPUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        accept_downloads=True,
        locale="it-IT"
    )
    page = context.new_page()

    for i in range(1, TOTAL + 1):
        print(f"Scaricando issue {i}...")

        with page.expect_download() as download_info:
            page.goto(BASE_URL.format(i))

        download = download_info.value
        path = os.path.join(OUTPUT_DIR, f"raspberrypi_issue_{i}.pdf")
        download.save_as(path)

        print(f"✓ Salvato {path}")
        time.sleep(3)  # pausa umana

    browser.close()
