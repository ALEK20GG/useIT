import requests
import os
import time
import random

BASE_URL = "https://magazine.raspberrypi.com/issues/{}/pdf/download"
OUTPUT_DIR = r"D:\source\useIT\frontend\static\pdf-source"
TOTAL_FILES = 100

# Crea la cartella se non esiste
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://magazine.raspberrypi.com/"
})

def is_valid_pdf(content):
    """Verifica se il contenuto è un vero PDF"""
    # Un PDF valido inizia con "%PDF"
    return len(content) > 4 and content[:4] == b'%PDF'

def download_issue(num):
    url = BASE_URL.format(num)
    path = os.path.join(OUTPUT_DIR, f"raspberrypi_issue_{num:03d}.pdf")
    
    # Salta se già esiste
    if os.path.exists(path):
        print(f"⚠ Issue {num:03d}: Già presente, salto")
        return True
    
    for attempt in range(3):  # Massimo 3 tentativi
        try:
            print(f"Issue {num:03d} (tentativo {attempt + 1})...", end=" ")
            
            # Prima richiesta per ottenere l'URL reale del PDF
            initial_response = session.get(url, allow_redirects=True, timeout=30)
            
            if initial_response.status_code == 429:
                wait = 10 + attempt * 5
                print(f"Rate limit, attendo {wait}s...")
                time.sleep(wait)
                continue
            
            if initial_response.status_code != 200:
                print(f"HTTP {initial_response.status_code}")
                return False
            
            # Controlla se è un PDF
            content_type = initial_response.headers.get('content-type', '').lower()
            
            if 'pdf' in content_type:
                # È un PDF, scaricalo
                if is_valid_pdf(initial_response.content[:100]):
                    with open(path, 'wb') as f:
                        f.write(initial_response.content)
                    
                    file_size = len(initial_response.content) // 1024
                    print(f"✓ Scaricato ({file_size} KB)")
                    return True
                else:
                    print(f"✗ Non è un PDF valido")
                    return False
            elif 'html' in content_type:
                # È una pagina HTML, probabilmente il numero non è disponibile
                print("✗ Non disponibile (pagina HTML)")
                
                # Salva la pagina HTML per debug (rinomina con .html)
                html_path = os.path.join(OUTPUT_DIR, f"debug_issue_{num:03d}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(initial_response.text[:2000])  # Salva solo primi 2000 caratteri
                
                # Elimina il file se è troppo piccolo (probabilmente errore)
                if os.path.exists(path):
                    os.remove(path)
                    
                return False
            else:
                # Altro tipo di contenuto
                print(f"✗ Tipo sconosciuto: {content_type[:30]}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"Timeout")
            time.sleep(5)
        except requests.exceptions.ConnectionError:
            print(f"Errore connessione")
            time.sleep(10)
        except Exception as e:
            print(f"Errore: {type(e).__name__}")
            time.sleep(5)
    
    print(f"✗ Fallito dopo 3 tentativi")
    return False

def main():
    print("=" * 60)
    print("SCARICA RASPBERRY PI MAGAZINE")
    print(f"Cartella output: {OUTPUT_DIR}")
    print("=" * 60)
    
    successi = 0
    falliti = 0
    
    # Suggerimento: parti da numeri alti che hanno più probabilità di essere gratuiti
    for i in range(1, TOTAL_FILES + 1):
        if download_issue(i):
            successi += 1
        else:
            falliti += 1
        
        # Pausa random più breve per non sovraccaricare il server
        if i < TOTAL_FILES:  # Nessuna pausa dopo l'ultimo
            pause_time = random.uniform(2, 4)
            time.sleep(pause_time)
    
    print("\n" + "=" * 60)
    print("RIASSUNTO FINALE:")
    print(f"Successi: {successi}")
    print(f"Falliti: {falliti}")
    
    if successi == 0:
        print("\n💡 SUGGERIMENTO: Probabilmente nessun numero è disponibile gratuitamente.")
        print("   Prova con numeri più recenti (150-159):")
        print("   Modifica TOTAL_FILES = 159 e parti da 150")
    
    # Mostra i file scaricati
    print("\n📁 Contenuto della cartella:")
    print("-" * 40)
    
    pdf_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.pdf')]
    html_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.html')]
    
    if pdf_files:
        for pdf in sorted(pdf_files)[:10]:  # Mostra solo primi 10
            size_kb = os.path.getsize(os.path.join(OUTPUT_DIR, pdf)) // 1024
            print(f"• {pdf} ({size_kb} KB)")
        
        if len(pdf_files) > 10:
            print(f"  ... e altri {len(pdf_files) - 10} file PDF")
    else:
        print("Nessun PDF trovato!")
    
    if html_files:
        print(f"\n⚠  File di debug HTML: {len(html_files)}")
        print("   (questi sono numeri non disponibili)")

if __name__ == "__main__":
    main()