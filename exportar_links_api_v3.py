import sys
import pandas as pd
import cloudscraper
import re
import shutil
from pathlib import Path

# LIMPEZA E PREPARAÇÃO
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ALVOS DE DIRETÓRIOS E AGREGADORES (Inspirado no ranking e diretórios públicos)
ALVOS = [
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u"
]

def extrair_apenas_video_real(texto):
    """Filtra apenas URLs que apontam para servidores de vídeo/streaming."""
    # Regex para capturar links que contenham extensões de vídeo ou termos de streaming
    return re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts|\.mkv|/stream|/vod/)[^\s"\'<>]*)', texto, re.IGNORECASE)

def main():
    scraper = cloudscraper.create_scraper()
    acervo_bruto = []
    
    print("📡 Iniciando Varredura de Fluxos de Vídeo...")
    
    for url in ALVOS:
        try:
            res = scraper.get(url, timeout=15)
            if res.status_code == 200:
                # Se for um M3U, extrai o par Nome/URL
                if "#EXTM3U" in res.text:
                    matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://.*)', res.text)
                    for nome, link in matches:
                        acervo_bruto.append({"Anime": nome.strip(), "URL": link.strip()})
                else:
                    # Se for uma página, minera qualquer link de vídeo
                    links = extrair_apenas_video_real(res.text)
                    for l in links:
                        acervo_bruto.append({"Anime": "Stream Minerado", "URL": l})
        except: continue

    # Integração com seu garimpo manual (Scribd/Tarsila)
    caminho_manual = SCRIPT_DIR / "fontes_manuais.txt"
    if caminho_manual.exists():
        links_manuais = extrair_apenas_video_real(caminho_manual.read_text(encoding="utf-8"))
        for lm in links_manuais: acervo_bruto.append({"Anime": "Link Manual", "URL": lm})

    if acervo_bruto:
        df = pd.DataFrame(acervo_bruto).drop_duplicates(subset=['URL'])
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url="" m3u-type="vod"\n\n')
            
            for index, row in df.iterrows():
                nome = re.sub(r'[^\w\s]', '', row['Anime']).strip()
                grupo = "FILMES ANIME" if "filme" in nome.lower() else "SÉRIES ANIME"
                
                # SINTAXE DE ALTA COMPATIBILIDADE (Removendo o pipe complexo que deu erro no seu print)
                # Adicionamos a extensão apenas se não houver uma, para não confundir o player
                url_final = row['URL']
                if not any(ext in url_final.lower() for ext in ['.mp4', '.m3u8', '.ts']):
                    url_final += "&format=.mp4"
                
                f.write(f'#EXTINF:-1 tvg-type="movie" group-title="{grupo}",{nome}\n')
                f.write(f"{url_final}\n\n")
        
        print(f"✅ Sucesso! {len(df)} links de vídeo extraídos e prontos.")

if __name__ == "__main__":
    main()
