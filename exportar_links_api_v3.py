import sys
import pandas as pd
import cloudscraper
import time
import random
import re
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# CONFIGURAÇÃO DE DIRETÓRIOS
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer-Dub", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
    {"name": "Goyabu", "url": "https://goyabu.com/lista-de-animes", "suffix": "/page/"}
]

def buscar_video_direto(scraper, url_pagina):
    """Tenta entrar na página e encontrar o link do arquivo de vídeo."""
    try:
        res = scraper.get(url_pagina, timeout=15)
        if res.status_code != 200: return url_pagina
        
        html = res.text
        # Busca padrões de streaming (.m3u8 ou .mp4) em scripts ou iframes
        # Regex para capturar links de vídeo comuns em players piratas
        video_pattern = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4|mkv))', html)
        
        if video_pattern:
            return video_pattern[0] # Retorna o primeiro link de vídeo encontrado
            
        # Se não achar o arquivo, procura por fontes de player (ex: mydrive, player)
        iframe_pattern = re.findall(r'src=["\'](https?://[^"\']*(?:player|vidsrc|drive)[^"\']*)["\']', html)
        if iframe_pattern:
            return iframe_pattern[0]
            
    except:
        pass
    return url_pagina # Se falhar, mantém o link da página como backup

def extrair_universal(scraper, html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    cards = soup.select('article, .item, .element, .ani_it, .vosty, .ep_item, .divCardAnime')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            href = link_tag.get('href')
            titulo = link_tag.get('title') or card.get_text(strip=True).split('\n')[0]
            img_tag = card.select_one('img')
            imagem = img_tag.get('data-src') or img_tag.get('src') or ""

            if titulo and href:
                url_pagina = href if href.startswith('http') else f"https://{provider_name.lower()}.com{href}"
                
                # AQUI ESTÁ O PULO DO GATO: O script tenta buscar o vídeo dentro do link
                print(f"   🔎 Investigando fonte: {titulo[:30]}...")
                url_video = buscar_video_direto(scraper, url_pagina)
                
                items.append({
                    "Anime_Base": titulo.replace("Todos os Episódios", "").strip(),
                    "Titulo_Completo": titulo.strip(),
                    "URL": url_video,
                    "Imagem": imagem,
                    "Tipo": "Dublado" if "dublado" in titulo.lower() else "Legendado",
                    "Provider": provider_name
                })
        except: continue
    return items

def main():
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []
    
    # Reduzi para 3 páginas porque buscar links diretos dentro de cada página é MUITO lento
    PAGINAS_POR_PROVIDER = 3 

    for p in PROVIDERS:
        for pg in range(1, PAGINAS_POR_PROVIDER + 1):
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(2)
                res = scraper.get(url, timeout=20)
                if res.status_code == 200:
                    # Passamos o scraper para a função para ela poder navegar
                    dados = extrair_universal(scraper, res.text, p['name'])
                    if not dados: break
                    todas_listas.extend(dados)
                else: break
            except: break

    if todas_listas:
        df = pd.DataFrame(todas_listas)
        df = df.drop_duplicates(subset=['Titulo_Completo', 'Provider'])
        
        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for _, row in df.iterrows():
                is_movie = any(w in row['Titulo_Completo'].lower() for w in ['filme', 'movie'])
                cat = "Filmes" if is_movie else "Séries"
                grupo = f"{cat} | {row['Anime_Base']} ({row['Tipo']})"
                
                f.write(f'#EXTINF:-1 group-title="{grupo}" tvg-logo="{row["Imagem"]}", {row["Titulo_Completo"]}\n')
                f.write(f"{row['URL']}\n")

if __name__ == "__main__":
    main()
