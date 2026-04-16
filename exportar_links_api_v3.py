import pandas as pd
import cloudscraper
import re
import shutil
from pathlib import Path

# 1. LIMPEZA TOTAL (Evita que links antigos fiquem na lista)
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 2. FONTES FILTRADAS (Removendo fontes que misturam TV Live)
SOURCES = [
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u",
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u"
]

def main():
    scraper = cloudscraper.create_scraper()
    acervo = []

    for url in SOURCES:
        try:
            res = scraper.get(url, timeout=15)
            if res.status_code == 200:
                # Regex para pegar o par Nome/Link
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://.*)', res.text)
                for nome, link in matches:
                    # FILTRO ANTI-TV: Se o nome tiver "TV" ou "24/7", ignoramos
                    if not any(x in nome.upper() for x in ['TV', 'LIVE', '24/7', 'ONLINE']):
                        acervo.append({"Nome": nome.strip(), "URL": link.strip()})
        except: continue

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        
        with open(m3u_path, "w", encoding="utf-8") as f:
            # CABEÇALHO IDÊNTICO AO XTREAM CODES (m3u_plus)
            f.write('#EXTM3U x-tvg-url="" m3u-type="m3u_plus"\n\n')
            
            for _, row in df.iterrows():
                nome_limpo = re.sub(r'[^\w\s]', '', row['Nome']).strip()
                
                # Forçamos tudo como VOD/Series para o SmartOne habilitar as pastas
                f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{nome_limpo}" tvg-type="series" group-title="ANIMES VOD", {nome_limpo}\n')
                # O segredo: adicionamos o parâmetro de saída no link individual
                f.write(f"{row['URL']}?output=ts\n\n")

if __name__ == "__main__":
    main()
