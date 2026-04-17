import pandas as pd
import cloudscraper
import requests
import re
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# ... (Manter configurações de diretório anteriores) ...

def validar_link(row):
    """Verifica se o link do vídeo está online (Status 200)."""
    try:
        # Fazemos um request rápido (apenas cabeçalho) para não baixar o arquivo
        response = requests.head(row['URL'], timeout=5, allow_redirects=True)
        if response.status_code == 200:
            return row
    except:
        return None
    return None

def main():
    # ... (Parte da mineração anterior) ...
    
    if acervo:
        print(f"🔍 Validando integridade de {len(acervo)} links...")
        df_bruto = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        
        # Usamos múltiplas 'threads' para validar rápido (estilo m3u-editor profissional)
        with ThreadPoolExecutor(max_workers=10) as executor:
            resultados = list(executor.map(validar_link, df_bruto.to_dict('records')))
        
        # Remove os links que falharam (None)
        acervo_validado = [r for r in resultados if r is not None]
        df = pd.DataFrame(acervo_validado)

        # GERAÇÃO DO M3U FINAL
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url="" m3u-type="m3u_plus" playlist-type="vod"\n\n')
            
            for _, row in df.iterrows():
                nome_final = normalizar_nome_serie(row['Nome'])
                # Sintaxe que simula o servidor get.php validado por você
                f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{nome_final}" tvg-type="series" group-title="ANIME VOD", {nome_final}\n')
                f.write(f"{row['URL']}?output=ts&v=2026\n\n")
        
        print(f"✅ Integração completa! {len(df)} links validados e online.")
