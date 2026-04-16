import sys
import pandas as pd
import cloudscraper
import time
import random
import re
from pathlib import Path
from bs4 import BeautifulSoup

# CONFIGURAÇÕES
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fontes que costumam ter links diretos m3u8 ou players extraíveis
PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "Anizero", "url": "https://anizero.org/lista-de-animes", "suffix": "?page="},
    {"name": "GitHub-AnimeList", "url": "https://github.com/search?q=anime+m3u8+playlist&type=repositories", "suffix": "&p="}
]

def extrair_link_direto(scraper, url_pagina):
    """Entra na página e tenta encontrar um link .m3u8 ou .mp4 real."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # Busca por links m3u8 escondidos em scripts (padrão de players VOD)
        res = scraper.get(url_pagina, headers=headers, timeout=10)
        if res.status_code == 200:
            # Regex para links de streaming
            match = re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4|ts))["\']', res.text)
            if match:
                return match.group(1)
            
            # Tenta encontrar em iframes de players populares
            soup = BeautifulSoup(res.text, 'html.parser')
            iframe = soup.find('iframe', src=re.compile(r'player|vidsrc|m3u8'))
            if iframe: return iframe['src']
    except:
        pass
    return None

def main():
    print(f"🚀 INICIANDO MINERAÇÃO VOD DIRETA (.m3u8 / .mp4)")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    todas_listas = []

    for p in PROVIDERS:
        print(f"📡 Buscando em: {p['name']}...")
        for pg in range(1, 11): 
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(2)
                res = scraper.get(url, timeout=20)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    # Captura cards
                    cards = soup.select('article, .item, .divCardAnime, .repo-list-item')
                    
                    for card in cards:
                        link_tag = card.select_one('a')
                        if not link_tag: continue
                        
                        url_origem = link_tag.get('href')
                        if not url_origem.startswith('http'): continue
                        
                        # TENTA EXTRAIR O VÍDEO REAL
                        print(f"   🎬 Investigando: {url_origem[:40]}...")
                        link_video = extrair_link_direto(scraper, url_origem)
                        
                        if link_video:
                            todas_listas.append({
                                "Anime": link_tag.get('title') or "Anime Encontrado",
                                "URL": link_video,
                                "Imagem": card.select_one('img').get('src', '') if card.select_one('img') else "",
                                "Provider": p['name']
                            })
                else: break
            except: break

    if todas_listas:
        df = pd.DataFrame(todas_listas).drop_duplicates(subset=['URL'])
        
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n\n')
            for _, row in df.iterrows():
                # Formato compatível com SmartOne/IBO Player
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{row["Provider"]}", {row["Anime"]}\n')
                f.write(f"{row['URL']}|User-Agent=Mozilla/5.0\n\n")
        
        print(f"✅ Sucesso! {len(df)} links VOD diretos encontrados.")

if __name__ == "__main__":
    main()
