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

# SELEÇÃO DOS MELHORES PROVIDERS (Baseado em estabilidade e retorno real)
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
        res = scraper.get(url_pagina, headers=headers, timeout=20)
        if res.status_code != 200: return url_pagina
        
        # Procura m3u8 ou mp4
        video_links = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4))', res.text)
        if video_links: return video_links[0]
            
        # Procura Iframes
        soup = BeautifulSoup(res.text, 'html.parser')
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'): return iframe.get('src')
    except: pass
    return url_pagina

def extrair_universal(scraper, html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    cards = soup.select('article, .item, .element, .divCardAnime, .anime-card')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            # LIMPEZA DE TÍTULO: Remove "9.8", "10", "NOVO", "2026", etc.
            raw_title = link_tag.get('title') or card.get_text(" ", strip=True).split('\n')[0]
            titulo_limpo = re.sub(r'^\d+\.?\d*\s*|NOVO\s*|\d{4}\s*|Assistir\s*', '', raw_title).strip()
            
            url_origem = link_tag.get('href')
            if not url_origem.startswith('http'): 
                url_origem = f"https://{provider_name.lower()}.com{url_origem}"
            
            img_tag = card.select_one('img')
            capa = img_tag.get('src') or img_tag.get('data-src') if img_tag else ""

            print(f"   🎬 Investigando: {titulo_limpo[:25]}...")
            link_final = buscar_video_direto(scraper, url_origem)
            
            items.append({
                "Anime": titulo_limpo,
                "URL": link_final,
                "Imagem": capa,
                "Provider": provider_name,
                "Tipo": "Dublado" if "dublado" in titulo_limpo.lower() or "dublado" in url_origem.lower() else "Legendado"
            })
        except: continue
    return items

def main():
    print(f"🚀 SUGOIAPI V3 - MODO PRODUÇÃO - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []

    for p in PROVIDERS:
        print(f"📡 Varrendo: {p['name']}")
        for pg in range(1, 4): 
            url_lista = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(random.uniform(3, 5))
                res = scraper.get(url_lista, timeout=25)
                if res.status_code == 200:
                    dados = extrair_universal(scraper, res.text, p['name'])
                    if not dados: break
                    todas_listas.extend(dados)
                else: break
            except: break

    if todas_listas:
        df = pd.DataFrame(todas_listas).drop_duplicates(subset=['Anime'])
        df = df.sort_values(by='Anime') # ORDENAÇÃO ALFABÉTICA

        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for _, row in df.iterrows():
                is_movie = any(x in row['Anime'].lower() for x in ['filme', 'movie'])
                cat = "Filmes" if is_movie else "Séries"
                
                # Identifica domínio para o Referer
                try: ref_domain = row['URL'].split('/')[2]
                except: ref_domain = "google.com"
                
                # Header Bypass (UA + Referer)
                link_header = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://{ref_domain}/"
                grupo = f"{cat} | {row['Provider']} ({row['Tipo']})"
                
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{grupo}", {row["Anime"]}\n')
                f.write(f"{link_header}\n")
        
        print("-" * 30)
        print(f"✅ Arquivo salvo: {m3u_path.absolute()}")
        print(f"📊 Total: {len(df)} animes.")
        print("-" * 30)

if __name__ == "__main__":
    main()
