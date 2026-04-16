import sys
import pandas as pd
import cloudscraper
import time
import random
import re
import traceback
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# 1. CONFIGURAÇÕES INICIAIS
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
    {"name": "Goyabu", "url": "https://goyabu.com/lista-de-animes", "suffix": "/page/"}
]

def buscar_video_direto(scraper, url_pagina):
    """Tenta extrair o link real do vídeo ou player para evitar o Timeout."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": url_pagina
    }
    try:
        # Aumentamos o timeout para 30s para evitar o erro de 'Time Out'
        res = scraper.get(url_pagina, headers=headers, timeout=30)
        if res.status_code != 200: return url_pagina
        
        # Procura por .m3u8 ou .mp4 (Links diretos)
        video_links = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4))', res.text)
        if video_links: return video_links[0]
            
        # Procura por Iframes de players
        soup = BeautifulSoup(res.text, 'html.parser')
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'):
            return iframe.get('src')
    except:
        pass
    return url_pagina

def main():
    print(f"🚀 SUGOIAPI V3 - Varredura Profunda com Bypass 403/Timeout")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []

    for p in PROVIDERS:
        print(f"📡 Processando Provider: {p['name']}")
        for pg in range(1, 4): # Varredura de 3 páginas para evitar sobrecarga
            url_lista = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                # Delay maior para não ser banido por IP
                time.sleep(random.uniform(4, 7))
                res = scraper.get(url_lista, timeout=30)
                
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    cards = soup.select('article, .item, .element, .divCardAnime')
                    
                    for card in cards:
                        link_tag = card.select_one('a')
                        if not link_tag: continue
                        
                        titulo = link_tag.get('title') or card.get_text(strip=True)
                        url_origem = link_tag.get('href')
                        if not url_origem.startswith('http'): 
                            url_origem = f"{p['url'].split('/animes')[0]}{url_origem}"
                        
                        img_tag = card.select_one('img')
                        capa = img_tag.get('src') or img_tag.get('data-src') if img_tag else ""

                        # BUSCA PROFUNDA DO LINK DO VÍDEO
                        print(f"   🎬 Extraindo fonte de: {titulo[:25]}...")
                        link_final = buscar_video_direto(scraper, url_origem)
                        
                        todas_listas.append({
                            "Anime": titulo.strip(),
                            "URL": link_final,
                            "Imagem": capa,
                            "Provider": p['name']
                        })
                else: break
            except Exception as e:
                print(f"   ⚠️ Timeout ou erro na página {pg}: {str(e)[:50]}")
                break

    if todas_listas:
        df = pd.DataFrame(todas_listas).drop_duplicates(subset=['Anime'])
        
        # GERAÇÃO DA PLAYLIST M3U COM HEADERS DE BYPASS
        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for _, row in df.iterrows():
                # Classificação Filmes vs Séries
                cat = "Filmes" if any(x in row['Anime'].lower() for x in ['filme', 'movie']) else "Séries"
                
                # Definimos o Referer baseado na URL capturada
                ref = row['URL'].split('/')[2] if '://' in row['URL'] else "google.com"
                
                # ADAPTAÇÃO PARA PLAYERS (VLC, Televizo, OTT Navigator)
                # O caractere '|' anexa o User-Agent e o Referer para evitar o 403/Timeout no player
                link_header = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://{ref}/"
                
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{cat} | {row["Provider"]}", {row["Anime"]}\n')
                f.write(f"{link_header}\n")
        
        print(f"✨ Concluído! Playlist gerada com {len(df)} itens.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
