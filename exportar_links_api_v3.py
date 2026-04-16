import sys
import pandas as pd
import cloudscraper
import time
import re
from pathlib import Path

# CONFIGURAÇÕES
OUTPUT_DIR = Path(__file__).parent.absolute() / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# NOVAS FONTES INTEGRADAS (Foco em repositórios e diretórios públicos)
DIRECTORIES = [
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/iptv-org/awesome-iptv/master/README.md",
    "https://sourceforge.net/projects/iptv-free-tv.mirror/files/",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u"
]

def hunter_v3():
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    for url in DIRECTORIES:
        print(f"📡 Varrendo diretório: {url[:50]}...")
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                # 1. Busca padrão M3U (#EXTINF + Link)
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://.*?\.(?:m3u8|mp4|ts).*)', res.text, re.IGNORECASE)
                for nome, link in matches:
                    acervo.append({"Anime": nome.strip(), "URL": link.strip()})
                
                # 2. Busca padrão de Link Solto (Regex para pescar URLs m3u8 escondidas em README ou HTML)
                links_soltos = re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts)[^\s"\'<>]*)', res.text)
                for ls in links_soltos:
                    acervo.append({"Anime": "VOD Minerado", "URL": ls})
        except:
            continue

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        # Filtrar apenas o que tem "anime" no nome ou URL para manter o foco
        df = df[df['Anime'].str.contains('anime|movie|filme|hentai|ecchi', case=False) | 
                df['URL'].str.contains('anime|vod', case=False)]

        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n\n')
            for _, row in df.iterrows():
                # Categorização básica por URL
                cat = "ANIME GERAL"
                if "dublado" in row['URL'].lower(): cat = "ANIME DUBLADO"
                elif "hentai" in row['URL'].lower(): cat = "ADULTO"
                
                # SINTAXE DE COMPATIBILIDADE SMART ONE
                f.write(f'#EXTINF:-1 group-title="{cat}", {row["Anime"]}\n')
                f.write(f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://google.com/\n\n")
        
        print(f"✅ Hunter V3 finalizado com {len(df)} links funcionais.")

if __name__ == "__main__":
    hunter_v3()
