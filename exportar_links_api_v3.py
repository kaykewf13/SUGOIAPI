import sys
import pandas as pd
import cloudscraper
import time
import random
import re
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Lista reduzida para focar em providers que costumam liberar o player
PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"}
]

def buscar_fonte_video(scraper, url_pagina):
    """Entra na página do anime e busca o link do player ou do arquivo m3u8/mp4."""
    try:
        # Simula o acesso à página do episódio/anime
        res = scraper.get(url_pagina, timeout=15)
        if res.status_code != 200: return url_pagina
        
        # 1. Tenta buscar links de streaming diretos no código (Regex)
        video_links = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4))', res.text)
        if video_links:
            return video_links[0]
            
        # 2. Busca por iframes (onde o vídeo geralmente está escondido)
        soup = BeautifulSoup(res.text, 'html.parser')
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'):
            return iframe.get('src')
            
    except:
        pass
    return url_pagina

def main():
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []
    
    # Reduzido para 2 páginas devido ao tempo de varredura profunda
    for p in PROVIDERS:
        print(f"📡 Investigando: {p['name']}")
        for pg in range(1, 3):
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(3)
                res = scraper.get(url, timeout=20)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    cards = soup.select('article, .item, .element, .divCardAnime')
                    
                    for card in cards:
                        link_tag = card.select_one('a')
                        if not link_tag: continue
                        
                        titulo = link_tag.get('title') or card.get_text(strip=True)
                        url_pag = link_tag.get('href')
                        if not url_pag.startswith('http'): url_pag = f"{p['url'].split('/animes')[0]}{url_pag}"
                        
                        img = card.select_one('img')
                        capa = img.get('src') or img.get('data-src') if img else ""

                        # BUSCA O LINK REAL DO VÍDEO
                        print(f"   🎬 Buscando vídeo para: {titulo[:20]}...")
                        link_direto = buscar_fonte_video(scraper, url_pag)
                        
                        todas_listas.append({
                            "Anime": titulo.strip(),
                            "URL": link_direto,
                            "Imagem": capa,
                            "Provider": p['name']
                        })
                else: break
            except: break

    if todas_listas:
        df = pd.DataFrame(todas_listas)
        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for _, row in df.iterrows():
                # ADICIONAMOS UM USER-AGENT NO LINK PARA O PLAYER TENTAR BURLAR O BLOQUEIO
                # Isso funciona em players como o VLC e OTT Navigator
                link_com_header = f"{row['URL']}|User-Agent=Mozilla/5.0"
                
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{row["Provider"]}", {row["Anime"]}\n')
                f.write(f"{link_com_header}\n")
        print("✅ Playlist atualizada.")

if __name__ == "__main__":
    main()
