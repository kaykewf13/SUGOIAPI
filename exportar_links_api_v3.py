import sys
import pandas as pd
import cloudscraper
import re
import shutil
from pathlib import Path

# LIMPEZA
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = [
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u"
]

def limpar_nome(texto):
    # Remove emojis e caracteres especiais que travam o SmartOne
    return re.sub(r'[^\w\s\-]', '', str(texto)).strip()

def main():
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    for url in SOURCES:
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://[^\s\n]+)', res.text, re.IGNORECASE)
                for nome, link in matches:
                    acervo.append({"Anime": nome.strip(), "URL": link.strip()})
        except: continue

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        
        with open(m3u_path, "w", encoding="utf-8") as f:
            # Cabeçalho simplificado (Sem HTTPS na instrução)
            f.write('#EXTM3U\n\n')
            
            for index, row in df.iterrows():
                nome_bruto = row['Anime']
                nome_clean = limpar_nome(nome_bruto)
                
                # Categorização sem Emojis para não dar erro no player
                if any(x in nome_bruto.lower() for x in ['filme', 'movie']):
                    grupo = "FILMES ANIME"
                    tipo = "movie"
                else:
                    grupo = "SERIES ANIME"
                    tipo = "series"
                
                # O segredo do SmartOne: Link direto + Extensão falsa
                link_vod = f"{row['URL']}|User-Agent=Mozilla/5.0&.mp4"
                
                # Tags simplificadas
                f.write(f'#EXTINF:-1 tvg-name="{nome_clean}" tvg-type="{tipo}" group-title="{grupo}",{nome_clean}\n')
                f.write(f"{link_vod}\n\n")
        
        print(f"✅ Lista higienizada para SmartOne gerada.")

if __name__ == "__main__":
    main()
