import pandas as pd
import cloudscraper
import re
import shutil
from pathlib import Path

# Limpeza de diretórios
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

def formatar_para_smartone(nome, url):
    nome_limpo = re.sub(r'[^\w\s]', '', str(nome)).strip()
    url_final = str(url).strip()
    
    # Identifica se é Filme ou Série para forçar a aba correta
    if any(x in nome.lower() for x in ['filme', 'movie', 'longa']):
        categoria = "ANIMES FILMES"
        tipo = "movie"
    else:
        categoria = "ANIMES SERIES"
        tipo = "series"
    
    # Adiciona extensão fake se necessário para o player reconhecer como arquivo
    if not any(ext in url_final.lower() for ext in ['.mp4', '.m3u8', '.ts', '.mkv']):
        url_final += "&format=ts"
        
    return f'#EXTINF:-1 tvg-id="" tvg-name="{nome_limpo}" tvg-logo="" tvg-type="{tipo}" group-title="{categoria}",{nome_limpo}\n{url_final}\n'

def main():
    scraper = cloudscraper.create_scraper()
    print("🚀 Gerando Lista Padrão Xtream Compatibility...")
    acervo = []

    for url in SOURCES:
        try:
            res = scraper.get(url, timeout=15)
            if res.status_code == 200:
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://.*)', res.text)
                for nome, link in matches:
                    acervo.append((nome, link))
        except: continue

    # Fontes Manuais
    manual = SCRIPT_DIR / "fontes_manuais.txt"
    if manual.exists():
        links_m = re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts|\.mkv)[^\s"\'<>]*)', manual.read_text(encoding="utf-8"))
        for l in links_m: acervo.append(("Anime Minerado", l))

    if acervo:
        df = pd.DataFrame(acervo, columns=['Nome', 'URL']).drop_duplicates(subset=['URL'])
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        
        with open(m3u_path, "w", encoding="utf-8") as f:
            # O SmartOne exige esse cabeçalho específico para habilitar as abas VOD
            f.write('#EXTM3U x-tvg-url="" m3u-type="vod" playlist-type="vod"\n\n')
            for _, row in df.iterrows():
                f.write(formatar_para_smartone(row['Nome'], row['URL']))
        
        print(f"✅ Lista criada com {len(df)} itens em formato VOD.")

if __name__ == "__main__":
    main()
