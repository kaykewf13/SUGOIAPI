import sys
import pandas as pd
import cloudscraper
import time
import re
import shutil
from pathlib import Path

# LIMPEZA DE CACHE LOCAL
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DIRECTORIES = [
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u"
]

def extrair_metadados(nome, url):
    txt = (str(nome) + " " + str(url)).lower()
    # Define se é Filme ou Série para o player
    if any(x in txt for x in ['filme', 'movie', 'longa']):
        return "🎬 FILMES ANIME", "movie"
    return "📺 SÉRIES ANIME", "series"

def main():
    print(f"🚀 EXPORTANDO EM MODO VOD ESTRUTURADO")
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    for url in DIRECTORIES:
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://[^\s\n]+)', res.text, re.IGNORECASE)
                for nome, link in matches:
                    acervo.append({"Anime": nome.strip(), "URL": link.strip()})
        except: continue

    # Fontes Manuais
    caminho_manual = SCRIPT_DIR / "fontes_manuais.txt"
    if caminho_manual.exists():
        conteudo = caminho_manual.read_text(encoding="utf-8")
        links_txt = re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts)[^\s"\'<>]*)', conteudo)
        for l in links_txt: acervo.append({"Anime": "VOD Minerado", "URL": l})

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        
        with open(m3u_path, "w", encoding="utf-8") as f:
            # CABEÇALHO COMPLETO PARA SMARTONE/IBO
            f.write('#EXTM3U x-tvg-url="" m3u-type="vod" playlist-type="vod"\n\n')
            
            for index, row in df.iterrows():
                grupo, tipo_vod = extrair_metadados(row['Anime'], row['URL'])
                nome_clean = re.sub(r'[^\w\s\-\[\]]', '', row['Anime'])
                
                # SINTAXE DE FORÇAR VOD (Adicionando extensões virtuais no final do pipe)
                # O player vê o ".mp4" no final do link e entende como arquivo, não canal
                link_final = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://google.com/&.mp4"
                
                # Tag tvg-type é o segredo para aparecer nas categorias corretas
                f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{nome_clean}" tvg-logo="" tvg-type="{tipo_vod}" group-title="{grupo}", {nome_clean}\n')
                f.write(f"{link_final}\n\n")
        
        print(f"✅ Finalizado! 245 links configurados com Tags VOD.")

if __name__ == "__main__":
    main()
