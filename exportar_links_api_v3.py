import sys
import pandas as pd
import cloudscraper
import re
import shutil
from pathlib import Path

# LIMPEZA DE AMBIENTE
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# FONTES CONFIÁVEIS
SOURCES = [
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u"
]

def limpar_texto(texto):
    # Remove TUDO que não for letra ou número (essencial para evitar o erro de 'undefined')
    return re.sub(r'[^\w\s]', '', str(texto)).strip()

def main():
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    for url in SOURCES:
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
        for l in links_txt: acervo.append({"Anime": "Anime Minerado", "URL": l})

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        
        with open(m3u_path, "w", encoding="utf-8") as f:
            # Cabeçalho ultra-simples para evitar erro de protocolo
            f.write('#EXTM3U\n\n')
            
            for index, row in df.iterrows():
                nome_bruto = row['Anime']
                nome_clean = limpar_texto(nome_bruto)
                
                # Categorias sem caracteres especiais (Texto puro)
                if any(x in nome_bruto.lower() for x in ['filme', 'movie']):
                    grupo = "FILMES ANIME"
                    tipo = "movie"
                else:
                    grupo = "SERIES ANIME"
                    tipo = "series"
                
                # Extensão MP4 virtual ajuda o SmartOne a reconhecer como VOD
                link_vod = f"{row['URL']}|User-Agent=Mozilla/5.0&.mp4"
                
                # Estrutura de metadados sem aspas desnecessárias
                f.write(f'#EXTINF:-1 tvg-name={nome_clean} tvg-type={tipo} group-title="{grupo}",{nome_clean}\n')
                f.write(f"{link_vod}\n\n")
        
        print(f"✅ Lista higienizada para SmartOne gerada com sucesso.")

if __name__ == "__main__":
    main()
