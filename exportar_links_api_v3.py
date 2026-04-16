import sys
import pandas as pd
import cloudscraper
import time
import re
from pathlib import Path

# CONFIGURAÇÕES
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# FONTES GLOBAIS + LOCAIS
DIRECTORIES = [
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/iptv-org/awesome-iptv/master/README.md",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u"
]

def ultra_hunter():
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    # 1. PROCESSA FONTES ONLINE
    for url in DIRECTORIES:
        print(f"📡 Varrendo: {url[:60]}...")
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                # Regex que pega o nome e o link, aceitando links complexos de vídeo
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://[^\s\n]+)', res.text, re.IGNORECASE)
                for nome, link in matches:
                    acervo.append({"Anime": nome.strip(), "URL": link.strip()})
        except: continue

    # 2. PROCESSA FONTES MANUAIS (Se você subir um .txt com o conteúdo do Scribd)
    caminho_manual = SCRIPT_DIR / "fontes_manuais.txt"
    if caminho_manual.exists():
        print("📁 Lendo fontes manuais (Scribd/PDF)...")
        conteudo = caminho_manual.read_text(encoding="utf-8")
        # Pega qualquer link que pareça vídeo ou streaming no texto colado
        links_txt = re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts|stream|video)[^\s"\'<>]*)', conteudo)
        for l in links_txt:
            acervo.append({"Anime": "VOD Manual", "URL": l})

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        
        # Filtro de Qualidade: Garante que o link tem "cara" de streaming para o SmartOne
        df = df[df['URL'].str.contains(r'\.m3u8|\.mp4|\.ts|/stream|/video|iptv|cdn', case=False, na=False)]

        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url=""\n\n')
            for _, row in df.iterrows():
                # Categorização baseada no nome
                nome = row['Anime']
                cat = "ANIME - GERAL"
                if any(x in nome.lower() for x in ['dub', 'port', 'br']): cat = "ANIME - DUBLADO"
                elif any(x in nome.lower() for x in ['hentai', 'ecchi', '18']): cat = "ANIME - ADULTO"
                
                # SINTAXE DE BYPASS (Essencial para não travar a imagem)
                link_final = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://google.com/"
                f.write(f'#EXTINF:-1 group-title="{cat}", {nome}\n{link_final}\n\n')
        
        print(f"✅ Finalizado! {len(df)} links VOD prontos para o Smart One.")

if __name__ == "__main__":
    ultra_hunter()
