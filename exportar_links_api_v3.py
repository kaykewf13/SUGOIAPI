import sys
import pandas as pd
import cloudscraper
import time
import random
import re
from pathlib import Path
from bs4 import BeautifulSoup

# 1. CONFIGURAÇÕES DE DIRETÓRIO
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 2. FONTES DE ALTA DISPONIBILIDADE (Diretórios de listas VOD e Sites)
SOURCES = [
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u",
    "https://animeshd.to/animes",
    "https://anizero.org/lista-de-animes"
]

def extrair_links_diretos(scraper, url_alvo):
    """Extrai pares de Nome e Link de vídeo (m3u8, mp4, ts)."""
    resultados = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        res = scraper.get(url_alvo, headers=headers, timeout=20)
        if res.status_code != 200: return []

        # PADRÃO 1: Se for um arquivo M3U (GitHub Raw)
        if ".m3u" in url_alvo:
            # Pega o nome no #EXTINF e o link na linha seguinte
            matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://.*?\.(?:m3u8|mp4|ts|mkv).*)', res.text, re.IGNORECASE)
            for nome, link in matches:
                resultados.append({"Anime": nome.strip(), "URL": link.strip()})
        
        # PADRÃO 2: Se for um site de anime (HTML)
        else:
            # Regex para pescar qualquer link de streaming no código fonte
            video_links = re.findall(r'["\'](https?://[^"\']+\.(?:m3u8|mp4|ts))["\']', res.text, re.IGNORECASE)
            for link in video_links:
                resultados.append({"Anime": "VOD Minerado", "URL": link})
            
            # Tenta capturar títulos e imagens se for HTML
            soup = BeautifulSoup(res.text, 'html.parser')
            for card in soup.select('article, .item, .anime-card'):
                link_tag = card.select_one('a')
                if link_tag and link_tag.get('href'):
                    resultados.append({"Anime": link_tag.get('title', 'Anime'), "URL": link_tag.get('href')})
                    
    except Exception as e:
        print(f"   ⚠️ Erro ao minerar {url_alvo[:30]}: {e}")
    
    return resultados

def main():
    print(f"🚀 INICIANDO HUNTER V2 - FOCO EM VOD DIRETO (.m3u8 / .mp4)")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    acervo_final = []

    for fonte in SOURCES:
        print(f"📡 Minerando: {fonte[:60]}...")
        links = extrair_links_diretos(scraper, fonte)
        if links:
            print(f"   🎯 Encontrados {len(links)} potenciais links.")
            acervo_final.extend(links)
        time.sleep(random.uniform(2, 4))

    if acervo_final:
        df = pd.DataFrame(acervo_final).drop_duplicates(subset=['URL'])
        
        # Filtro: Manter apenas o que realmente parece um link de vídeo para o SmartOne
        df = df[df['URL'].str.contains(r'\.m3u8|\.mp4|\.ts|\.mkv|stream|video', case=False, na=False)]

        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url=""\n\n')
            
            for _, row in df.iterrows():
                # Lógica de Categorização
                txt = (row['Anime'] + " " + row['URL']).lower()
                if "hentai" in txt or "ecchi" in txt: cat = "ADULTO"
                elif "dublado" in txt or "pt-br" in txt: cat = "DUBLADOS"
                elif "filme" in txt or "movie" in txt: cat = "FILMES"
                else: cat = "SÉRIES ANIME"

                # Nome limpo
                nome = re.sub(r'[^\w\s\-\[\]]', '', row['Anime'])
                
                # SINTAXE DE OURO PARA SMART ONE / IBO PLAYER:
                # Link + User-Agent + Referer Genérico
                link_com_bypass = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://google.com/"
                
                f.write(f'#EXTINF:-1 group-title="{cat}", {nome}\n')
                f.write(f"{link_com_bypass}\n\n")
        
        print("-" * 30)
        print(f"✅ SUCESSO! {len(df)} links de vídeo prontos.")
        print(f"📂 Arquivo: {m3u_path.absolute()}")
    else:
        print("❌ Nenhum link de vídeo direto foi encontrado desta vez.")

if __name__ == "__main__":
    main()
