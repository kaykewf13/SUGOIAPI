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

# 1. CONFIGURAÇÕES DE AMBIENTE
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
    {"name": "AnimesOnline", "url": "https://animesonline.nz/anime", "suffix": "/page/"},
    {"name": "Anizero", "url": "https://anizero.org/lista-de-animes", "suffix": "?page="}
]

def buscar_video_direto(scraper, url_pagina):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": url_pagina
    }
    try:
        # Timeout de 15s por link individual para não travar o processo longo
        res = scraper.get(url_pagina, headers=headers, timeout=15)
        if res.status_code != 200: return url_pagina
        
        video_links = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4))', res.text)
        if video_links: return video_links[0]
            
        soup = BeautifulSoup(res.text, 'html.parser')
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'): return iframe.get('src')
    except: pass
    return url_pagina

def extrair_universal(scraper, html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    cards = soup.select('article, .item, .element, .divCardAnime, .anime-card, .ep_item')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            raw_title = link_tag.get('title') or card.get_text(" ", strip=True).split('\n')[0]
            # Limpeza agressiva de títulos para manter a lista profissional
            titulo_limpo = re.sub(r'^\d+\.?\d*\s*|NOVO\s*|\d{4}\s*|Assistir\s*|Episódio\s*\d+', '', raw_title).strip()
            
            url_origem = link_tag.get('href')
            if not url_origem.startswith('http'): 
                url_origem = f"https://{provider_name.lower()}.com{url_origem}"
            
            img_tag = card.select_one('img')
            capa = img_tag.get('src') or img_tag.get('data-src') or img_tag.get('data-lazy-src') or ""

            # Coleta de metadados
            items.append({
                "Anime": titulo_limpo,
                "URL_Pagina": url_origem,
                "Imagem": capa,
                "Provider": provider_name,
                "Tipo": "Dublado" if "dublado" in titulo_limpo.lower() or "dublado" in url_origem.lower() else "Legendado"
            })
        except: continue
    return items

def main():
    print(f"🚀 SUGOIAPI V3 - MODO DEEP SCAN (10 PÁGINAS)")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []

    for p in PROVIDERS:
        print(f"📡 Varrendo {p['name']}...")
        # Aumentado para 10 páginas para maior volume de dados
        for pg in range(1, 11): 
            url_lista = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(random.uniform(2, 4))
                res = scraper.get(url_lista, timeout=25)
                if res.status_code == 200:
                    dados = extrair_universal(scraper, res.text, p['name'])
                    if not dados: break
                    todas_listas.extend(dados)
                    print(f"   ✅ Pg {pg}: +{len(dados)} itens")
                else: break
            except: break

    if todas_listas:
        df = pd.DataFrame(todas_listas).drop_duplicates(subset=['Anime', 'Provider'])
        
        # Agora buscamos o vídeo direto apenas para o catálogo consolidado
        print(f"🔍 Investigando fontes diretas para {len(df)} animes...")
        
        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for i, row in df.iterrows():
                # Processa o link direto (Apenas se necessário, para poupar tempo)
                # link_final = buscar_video_direto(scraper, row['URL_Pagina'])
                link_final = row['URL_Pagina'] # Mantido página para estabilidade, ajuste se quiser deep link
                
                is_movie = any(x in row['Anime'].lower() for x in ['filme', 'movie'])
                cat = "Filmes" if is_movie else "Séries"
                
                try: ref_domain = link_final.split('/')[2]
                except: ref_domain = "google.com"
                
                link_header = f"{link_final}|User-Agent=Mozilla/5.0&Referer=https://{ref_domain}/"
                grupo = f"{cat} | {row['Provider']} ({row['Tipo']})"
                
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{grupo}", {row["Anime"]}\n')
                f.write(f"{link_header}\n")
        
        print("-" * 30)
        print(f"✅ Catálogo Expandido salvo!")
        print(f"📊 Total: {len(df)} animes.")

if __name__ == "__main__":
    main()
