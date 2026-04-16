import sys
import pandas as pd
import cloudscraper
import time
import re
import shutil
from pathlib import Path

# 1. AUTO-LIMPEZA: Remove tudo o que existia antes
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR) # Deleta a pasta antiga e tudo dentro dela
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# FONTES
DIRECTORIES = [
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u"
]

def categorizar_anime_profissional(nome, url):
    txt = (str(nome) + " " + str(url)).lower()
    if any(x in txt for x in ['filme', 'movie', 'longa']): return "🎬 FILMES"
    if any(x in txt for x in ['dublado', 'pt-br', 'dub']): return "🇧🇷 DUBLADOS"
    return "📺 SÉRIES ANIME"

def main():
    print(f"🚀 INICIANDO MODO VOD PROFISSIONAL (LIMPEZA TOTAL)")
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    # Processa Online
    for url in DIRECTORIES:
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://[^\s\n]+)', res.text, re.IGNORECASE)
                for nome, link in matches:
                    acervo.append({"Anime": nome.strip(), "URL": link.strip()})
        except: continue

    # Processa Fontes Manuais
    caminho_manual = SCRIPT_DIR / "fontes_manuais.txt"
    if caminho_manual.exists():
        conteudo = caminho_manual.read_text(encoding="utf-8")
        links_txt = re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts)[^\s"\'<>]*)', conteudo)
        for l in links_txt:
            acervo.append({"Anime": "VOD Minerado", "URL": l})

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        df = df[df['URL'].str.contains(r'\.m3u8|\.mp4|\.ts', case=False, na=False)]

        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            # CABEÇALHO PARA FORÇAR MODO VOD
            f.write('#EXTM3U url-tvg="" m3u-type="vod"\n\n')
            
            for index, row in df.iterrows():
                grupo = categorizar_anime_profissional(row['Anime'], row['URL'])
                nome_clean = re.sub(r'[^\w\s\-\[\]]', '', row['Anime'])
                
                # SINTAXE VOD: O player entende melhor se o link terminar "limpo" após os pipes
                link_final = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://google.com/"
                
                # Adicionamos tags que players como IBO e SmartOne usam para separar VOD de TV
                f.write(f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{grupo}", {nome_clean}\n')
                f.write(f"{link_final}\n\n")
        
        print(f"✅ Sucesso! {len(df)} links limpos e configurados como VOD.")

if __name__ == "__main__":
    main()
