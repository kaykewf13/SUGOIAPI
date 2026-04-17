import re
import json
import shutil
import cloudscraper
from pathlib import Path

# CONFIGURAÇÕES DE DIRETÓRIO
OUTPUT_DIR = Path('output')
if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def classificar_conteudo(nome):
    """Define a categoria e o tipo de áudio com base no nome do arquivo."""
    nome_up = nome.upper()
    
    # Identificação de Áudio
    audio = " [LEG]"
    if any(x in nome_up for x in ['DUBLADO', 'PT-BR', 'DUAL']):
        audio = " [DUB]"
    
    # Identificação de Categoria (Tipo)
    if any(x in nome_up for x in ['FILME', 'MOVIE', 'MOVIE']):
        return f"ANIMES FILMES{audio}", "movie"
    
    return f"ANIMES SERIES{audio}", "series"

def extrair_episodio(nome):
    """Normaliza o nome para o padrão S01E01 para agrupamento no player."""
    # Remove lixo técnico
    nome_clean = re.sub(r'(?i)(1080p|720p|h264|x264|web-dl|dual|audio|legendado|dublado)', '', nome).strip()
    
    # Busca padrão de episódio (Ex: E01, Ep 01, 01)
    match = re.search(r'(?i)(?:ep|e|cap)\.?\s?(\d+)', nome_clean)
    if match:
        num_ep = match.group(1).zfill(2)
        # Remove o número do título principal para evitar repetição
        titulo_base = re.sub(r'(?i)(?:ep|e|cap)\.?\s?\d+.*', '', nome_clean).strip()
        return f"{titulo_base} S01E{num_ep}", titulo_base
    
    return nome_clean, nome_clean

def main():
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    # Fontes M3U de referência
    SOURCES = [
        "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
        "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u"
    ]

    print("🚀 Iniciando extração e classificação profissional...")

    for url in SOURCES:
        try:
            res = scraper.get(url, timeout=15)
            if res.status_code == 200:
                # Extrai metadados e URL
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://.*)', res.text)
                for nome_original, link in matches:
                    # Filtro Anti-TV Live (Conforme o PDF de guia)
                    if not any(x in nome_original.upper() for x in ['TV', 'LIVE', '24/7', 'AO VIVO']):
                        acervo.append({"nome": nome_original, "url": link})
        except: continue

    if acervo:
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            # Cabeçalho Plus para habilitar abas VOD
            f.write('#EXTM3U x-tvg-url="" m3u-type="m3u_plus"\n\n')
            
            for item in acervo:
                nome_exibicao, titulo_base = extrair_episodio(item['nome'])
                categoria, tipo_vod = classificar_conteudo(item['nome'])
                
                # Tagging profissional para SmartOne/IBO
                f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{titulo_base}" tvg-type="{tipo_vod}" group-title="{categoria}",{nome_exibicao}\n')
                # O parâmetro output=ts garante compatibilidade com os players testados
                f.write(f"{item['url']}?output=ts\n\n")

    print(f"✅ Sucesso! Catálogo classificado e pronto para o SmartOne.")

if __name__ == "__main__":
    main()
